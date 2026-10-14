import json
from unittest import mock

from django.test import TestCase, override_settings

from crm.models import Customer, InteractionLog
from crm.services import AIServiceError
from crm.services.ai_service import GeminiCRMService
from insights.models import ModelRun, SentimentLabel, SentimentResult
from insights.pipeline import sentiment
from insights.pipeline.sentiment import evaluate, evaluation_set, keyword_label

SAMPLES = [
    ("Máy rất tốt, pin trâu, rất hài lòng", "positive"),
    ("Giao hàng nhanh, nhân viên nhiệt tình", "positive"),
    ("Pin hao quá, máy nóng, thất vọng", "negative"),
    ("Không tốt chút nào, lag liên tục", "negative"),
    ("Đẹp nhưng hơi lag", "neutral"),
    ("Mua cho mẹ dùng", "neutral"),
]


class KeywordTests(TestCase):
    def test_labels_and_negation(self):
        self.assertEqual(keyword_label("Máy rất tốt, pin trâu"), "positive")
        self.assertEqual(keyword_label("Không tốt chút nào"), "negative")
        self.assertEqual(keyword_label("Không lag, chơi game mượt"), "positive")
        self.assertEqual(keyword_label("Pin nhanh hết pin, máy nóng"), "negative")  # cụm dài khớp trước "nhanh"
        self.assertEqual(keyword_label("Đẹp nhưng hơi lag"), "neutral")
        self.assertEqual(keyword_label("Mua cho mẹ dùng"), "neutral")

    def test_evaluate_metrics(self):
        metrics = evaluate(["positive", "negative", "neutral", "positive"],
                           ["positive", "negative", "positive", "positive"], [10, 20, 30, 40])
        self.assertEqual(metrics["accuracy"], 0.75)
        self.assertEqual(metrics["n_eval"], 4)
        self.assertEqual(metrics["avg_latency_ms"], 25)
        self.assertEqual(metrics["confusion_matrix"], [[2, 0, 0], [1, 0, 0], [0, 0, 1]])
        self.assertEqual(set(metrics["f1_by_class"]), {"positive", "neutral", "negative"})


class SentimentModuleTests(TestCase):
    def setUp(self):
        customer = Customer.objects.create(name="Khách", email="k@example.com")
        for text, label in SAMPLES:
            log = InteractionLog.objects.create(customer=customer, customer_message=text)
            SentimentLabel.objects.create(interaction=log, label=label, source="test")

    def test_evaluation_set_is_stratified_and_stable(self):
        first = evaluation_set(3)
        self.assertEqual(len(first), 3)
        self.assertEqual(sorted(first["true"]), ["negative", "neutral", "positive"])
        self.assertEqual(list(evaluation_set(3)["interaction_id"]), list(first["interaction_id"]))
        self.assertEqual(len(evaluation_set(0)), len(SAMPLES))

    def fake_gemini(self, prompt, json_schema=None, temperature=0.7):
        self.assertEqual(temperature, 0)
        count = prompt.count("\n[")
        return json.dumps({"results": [{"id": i, "label": "positive", "confidence": 0.9} for i in range(count)]})

    @override_settings(AI_MOCK=False, GEMINI_API_KEY="test-key")
    def test_run_both_methods_same_sample_and_selects_best(self):
        with mock.patch.object(sentiment, "SENTIMENT_SAMPLE", 0), \
                mock.patch.object(GeminiCRMService, "_generate", side_effect=self.fake_gemini):
            runs = sentiment.run("b1")
        self.assertEqual([r.method for r in runs], ["keyword", "gemini"])
        self.assertTrue(all(r.status == ModelRun.Status.SUCCESS for r in runs))
        for run in runs:
            self.assertEqual(run.sentiments.count(), len(SAMPLES))
            for key in ("accuracy", "macro_f1", "f1_by_class", "confusion_matrix", "n_eval", "avg_latency_ms"):
                self.assertIn(key, run.metrics)
        keyword, gemini = runs
        self.assertEqual(set(keyword.sentiments.values_list("interaction_id", flat=True)),
                         set(gemini.sentiments.values_list("interaction_id", flat=True)))
        self.assertEqual(ModelRun.objects.filter(batch="b1", is_selected=True).count(), 1)
        self.assertTrue(keyword.is_selected)  # từ điển đúng 6/6, "Gemini giả" chỉ đúng 2/6

    @override_settings(AI_MOCK=False, GEMINI_API_KEY="test-key")
    def test_bad_json_from_ai_counts_as_neutral_not_crash(self):
        with mock.patch.object(sentiment, "SENTIMENT_SAMPLE", 0), \
                mock.patch.object(GeminiCRMService, "_generate", return_value='{"results": [{"id": "x"}]}'):
            runs = sentiment.run("b2")
        gemini = runs[1]
        self.assertEqual(gemini.status, ModelRun.Status.SUCCESS)
        self.assertIn("không trả lời", gemini.notes)
        self.assertEqual(set(gemini.sentiments.values_list("label", flat=True)), {"neutral"})

    @override_settings(AI_MOCK=False, GEMINI_API_KEY="test-key")
    def test_ai_error_marks_gemini_failed_but_keyword_still_selected(self):
        with mock.patch.object(sentiment, "SENTIMENT_SAMPLE", 0), mock.patch.object(sentiment, "GEMINI_RETRIES", 1), \
                mock.patch.object(GeminiCRMService, "_generate", side_effect=AIServiceError("hết hạn mức")), \
                self.assertLogs("insights", "ERROR"):
            runs = sentiment.run("b3")
        self.assertEqual(runs[1].status, ModelRun.Status.FAILED)
        self.assertFalse(SentimentResult.objects.filter(run=runs[1]).exists())
        runs[0].refresh_from_db()
        self.assertTrue(runs[0].is_selected)

    @override_settings(AI_MOCK=True)
    def test_mock_mode_is_never_selected(self):
        with mock.patch.object(sentiment, "SENTIMENT_SAMPLE", 0):
            runs = sentiment.run("b4")
        self.assertTrue(runs[1].notes.startswith("[mô phỏng]"))
        self.assertFalse(runs[1].is_selected)
        self.assertTrue(runs[0].is_selected)
