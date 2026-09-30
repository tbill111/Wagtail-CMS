import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("crm", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="ai_sentiment",
            field=models.CharField(
                blank=True,
                choices=[("positive", "Tích cực"), ("neutral", "Trung lập"), ("negative", "Tiêu cực")],
                max_length=20,
                verbose_name="Cảm xúc AI",
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="ai_priority",
            field=models.CharField(
                blank=True,
                choices=[("high", "Cao"), ("medium", "Trung bình"), ("low", "Thấp")],
                max_length=20,
                verbose_name="Ưu tiên AI",
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="ai_suggested_status",
            field=models.CharField(
                blank=True,
                choices=[
                    ("lead", "Tiềm năng"),
                    ("caring", "Đang chăm sóc"),
                    ("customer", "Đã mua hàng"),
                    ("churned", "Đã rời bỏ"),
                ],
                max_length=20,
                verbose_name="Trạng thái đề xuất AI",
            ),
        ),
        migrations.AddField(
            model_name="customer",
            name="ai_summary",
            field=models.TextField(blank=True, verbose_name="Tóm tắt AI"),
        ),
        migrations.AddField(
            model_name="customer",
            name="ai_next_actions",
            field=models.JSONField(blank=True, default=list, verbose_name="Hành động tiếp theo (AI)"),
        ),
        migrations.AddField(
            model_name="customer",
            name="ai_analyzed_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Thời điểm phân tích AI"),
        ),
        migrations.CreateModel(
            name="AIReport",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content", models.TextField(verbose_name="Nội dung nhận định")),
                ("stats", models.JSONField(default=dict, verbose_name="Số liệu tổng hợp")),
                ("provider", models.CharField(blank=True, max_length=100, verbose_name="Nhà cung cấp AI")),
                ("is_mock", models.BooleanField(default=False, verbose_name="Chế độ mô phỏng")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="ai_reports",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Người tạo",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Ngày tạo")),
            ],
            options={
                "verbose_name": "Báo cáo AI",
                "verbose_name_plural": "Báo cáo AI",
                "ordering": ["-created_at"],
            },
        ),
    ]
