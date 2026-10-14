"""Module phân tích cảm xúc tin nhắn khách hàng (TH2 · checklist 02, 06) – Tùng.

Hai phương pháp, chấm CÙNG một tập mẫu phân tầng (SENTIMENT_SAMPLE câu có nhãn đúng):
  - keyword: từ điển từ khoá tiếng Việt + xử lý phủ định (không tốn tiền, chạy tức thì);
  - gemini : LLM Gemini qua GeminiCRMService (có AI dự phòng), theo lô 20 câu, temperature 0.
Đánh giá bằng accuracy, macro F1, F1 từng nhãn, ma trận nhầm lẫn; chọn phương pháp có macro F1 cao nhất.
"""

import logging
import re
import time

import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from crm.services import AIServiceError, get_ai_service
from insights.conf import RANDOM_STATE, SENTIMENT_SAMPLE
from insights.models import ModelRun, SentimentLabel, SentimentResult

from .base import MethodResult, run_method, select_best
from .lexicon_vi import MAX_PHRASE, NEGATIONS, NEGATIVE, POSITIVE

logger = logging.getLogger("insights")

LABELS = ["positive", "neutral", "negative"]
GEMINI_BATCH = 20
GEMINI_RETRIES = 4
MOCK_NOTE = "[mô phỏng] Chưa cấu hình AI thật (AI_MOCK hoặc thiếu API key) – nhãn lấy theo từ điển, không được chọn."
GEMINI_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "results": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "id": {"type": "INTEGER"},
                    "label": {"type": "STRING", "enum": LABELS},
                    "confidence": {"type": "NUMBER"},
                },
                "required": ["id", "label", "confidence"],
            },
        },
    },
    "required": ["results"],
}
PROMPT = """Bạn là chuyên gia phân tích phản hồi khách hàng của một cửa hàng. Với MỖI nhận xét dưới đây, xác định cảm xúc
của khách đối với sản phẩm / dịch vụ:
- positive: hài lòng, khen là chính.
- neutral: trung tính, hoặc khen chê ngang nhau, hoặc chỉ mô tả / hỏi.
- negative: không hài lòng, phàn nàn, chê là chính.
confidence: độ chắc chắn từ 0 đến 1.
Trả về JSON {{"results": [{{"id": <id>, "label": "...", "confidence": ...}}]}} – đủ {n} phần tử, giữ đúng id.

NHẬN XÉT:
{items}"""


# ------------------------------------------------------------------ tập đánh giá
def evaluation_set(sample_size=None):
    """DataFrame (interaction_id, text, true) – mẫu phân tầng theo nhãn, cố định theo RANDOM_STATE."""
    sample_size = SENTIMENT_SAMPLE if sample_size is None else sample_size
    rows = SentimentLabel.objects.order_by("interaction_id").values_list(
        "interaction_id", "interaction__customer_message", "label")
    data = pd.DataFrame(list(rows), columns=["interaction_id", "text", "true"])
    if data.empty or not sample_size or sample_size >= len(data):
        return data
    frac = sample_size / len(data)
    sample = data.groupby("true").sample(frac=frac, random_state=RANDOM_STATE)
    return sample.sort_values("interaction_id").reset_index(drop=True)


def evaluate(true, pred, latencies=None):
    true, pred = list(true), list(pred)
    by_class = f1_score(true, pred, labels=LABELS, average=None, zero_division=0)
    metrics = {
        "accuracy": accuracy_score(true, pred),
        "macro_f1": f1_score(true, pred, labels=LABELS, average="macro", zero_division=0),
        "f1_by_class": {label: float(score) for label, score in zip(LABELS, by_class)},
        "confusion_matrix": confusion_matrix(true, pred, labels=LABELS).tolist(),
        "n_eval": len(true),
    }
    if latencies:
        metrics["avg_latency_ms"] = sum(latencies) / len(latencies)
    return metrics


# ------------------------------------------------------------------ phương pháp 1: từ điển
def normalize(text):
    text = (text or "").lower()
    text = re.sub(r"[^\w\s]", " ", text)
    return text.split()


def keyword_score(text):
    """Điểm = số cụm tích cực − số cụm tiêu cực; từ phủ định ngay trước (≤ 2 từ) đảo chiều cụm đó."""
    tokens = normalize(text)
    positive = negative = 0
    negate_until = -1
    i = 0
    while i < len(tokens):
        for size in range(min(MAX_PHRASE, len(tokens) - i), 0, -1):
            phrase = " ".join(tokens[i:i + size])
            if phrase in NEGATIONS:
                negate_until = i + size + 2
                break
            if phrase in POSITIVE or phrase in NEGATIVE:
                is_positive = (phrase in POSITIVE) != (i < negate_until)
                if is_positive:
                    positive += 1
                else:
                    negative += 1
                negate_until = -1
                break
        else:
            size = 1
        i += size
    return positive, negative


def keyword_label(text):
    positive, negative = keyword_score(text)
    if positive and negative and abs(positive - negative) <= 1:
        return "neutral"
    if positive > negative:
        return "positive"
    if negative > positive:
        return "negative"
    return "neutral"


def run_keyword(run, data):
    started = time.perf_counter()
    preds = [keyword_label(text) for text in data["text"]]
    latency = int((time.perf_counter() - started) * 1000 / max(len(preds), 1))
    SentimentResult.objects.bulk_create([
        SentimentResult(run=run, interaction_id=pk, label=label, latency_ms=latency)
        for pk, label in zip(data["interaction_id"], preds)
    ], batch_size=2000)
    return MethodResult(
        metrics=evaluate(data["true"], preds, [latency] * len(preds)), n_rows=len(preds),
        params={"positive_terms": len(POSITIVE), "negative_terms": len(NEGATIVE), "negations": len(NEGATIONS),
                "negation_window": 2},
    )


# ------------------------------------------------------------------ phương pháp 2: Gemini
def call_gemini(service, batch):
    """Gửi một lô câu; trả về {id: (label, confidence)}. Thử lại khi quá hạn mức (429) hoặc lỗi tạm thời."""
    items = "\n".join(f"[{i}] {text.strip()[:600]}" for i, text in enumerate(batch))
    prompt = PROMPT.format(n=len(batch), items=items)
    for attempt in range(GEMINI_RETRIES):
        try:
            raw = service._generate(prompt, json_schema=GEMINI_SCHEMA, temperature=0)
            data = service._parse_json_safe(raw)
            break
        except AIServiceError as exc:
            if attempt + 1 == GEMINI_RETRIES:
                raise
            wait = 20 * (attempt + 1)
            logger.warning("Gemini lỗi (%s), thử lại sau %ss", exc, wait)
            time.sleep(wait)
    results = {}
    for item in data.get("results") or []:
        try:
            index = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        label = str(item.get("label", "")).strip().lower()
        if 0 <= index < len(batch) and label in LABELS:
            confidence = item.get("confidence")
            results[index] = (label, float(confidence) if isinstance(confidence, (int, float)) else None)
    return results


def run_gemini(run, data):
    service = get_ai_service()
    if service.is_mock:
        preds = [keyword_label(text) for text in data["text"]]
        SentimentResult.objects.bulk_create([
            SentimentResult(run=run, interaction_id=pk, label=label)
            for pk, label in zip(data["interaction_id"], preds)])
        return MethodResult(metrics=evaluate(data["true"], preds), n_rows=len(preds), notes=MOCK_NOTE)

    texts = list(data["text"])
    preds, confidences, latencies, providers, missing = [], [], [], {}, 0
    for start in range(0, len(texts), GEMINI_BATCH):
        batch = texts[start:start + GEMINI_BATCH]
        began = time.perf_counter()
        answer = call_gemini(service, batch)
        per_item = int((time.perf_counter() - began) * 1000 / len(batch))
        provider = service.last_provider_label
        providers[provider] = providers.get(provider, 0) + 1  # số lô mỗi nhà cung cấp đã trả lời
        for index in range(len(batch)):
            label, confidence = answer.get(index, ("neutral", None))
            missing += index not in answer
            preds.append(label)
            confidences.append(confidence)
            latencies.append(per_item)

    SentimentResult.objects.bulk_create([
        SentimentResult(run=run, interaction_id=pk, label=label, confidence=conf, latency_ms=ms)
        for pk, label, conf, ms in zip(data["interaction_id"], preds, confidences, latencies)
    ], batch_size=2000)
    notes = f"{missing} câu AI không trả lời, tính là trung lập." if missing else ""
    return MethodResult(
        metrics=evaluate(data["true"], preds, latencies), n_rows=len(preds),
        params={"model": service.model_name, "batches_by_provider": providers, "batch_size": GEMINI_BATCH,
                "temperature": 0, "requests": -(-len(texts) // GEMINI_BATCH)},
        notes=notes,
    )


# ------------------------------------------------------------------ điểm vào của module
def run(batch):
    data = evaluation_set()
    if data.empty:
        raise RuntimeError("Chưa có tin nhắn nào có nhãn cảm xúc (SentimentLabel). Chạy import_th2_data trước.")
    runs = [
        run_method(batch, ModelRun.Module.SENTIMENT, "keyword", lambda r: run_keyword(r, data)),
        run_method(batch, ModelRun.Module.SENTIMENT, "gemini", lambda r: run_gemini(r, data)),
    ]
    select_best(runs, "macro_f1", higher_is_better=True)
    return runs
