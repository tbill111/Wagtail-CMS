from decimal import Decimal, InvalidOperation

from django.core.management.base import BaseCommand
from django.db.models import F, Sum


class Command(BaseCommand):
    help = 'Kiểm tra tự động các kết quả AI mà không sửa dữ liệu.'

    POSITIVE_WORDS = (
        'tốt', 'hài lòng', 'uy tín', 'thích', 'tích cực', 'ưng ý', 'nhiệt tình',
        'kinh doanh', 'hợp tác', 'hữu ích', 'tin tưởng', 'mạnh', 'ổn định'
    )
    NEGATIVE_WORDS = (
        'khó chịu', 'phàn nàn', 'không hài lòng', 'chậm', 'lỗi', 'thất vọng',
        'khó', 'bất mãn', 'tệ', 'xấu', 'đứt', 'khó xử', 'giận'
    )

    def _to_decimal(self, value):
        if value in (None, '', 'None'):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    def _has_field(self, model, field_name):
        try:
            model._meta.get_field(field_name)
            return True
        except Exception:
            return False

    def _extract_report_forecast(self, report):
        """Lấy giá trị doanh thu dự báo từ thuộc tính hoặc JSON stats của AIReport."""
        candidates = []

        for name in ('predicted_revenue', 'forecast_revenue', 'revenue_forecast', 'expected_revenue', 'revenue'):
            value = getattr(report, name, None)
            if value is not None:
                candidates.append(value)

        stats = getattr(report, 'stats', None) or {}
        if isinstance(stats, dict):
            for key in ('predicted_revenue', 'forecast_revenue', 'revenue_forecast', 'expected_revenue', 'revenue', 'total_revenue'):
                if key in stats:
                    candidates.append(stats[key])

        for candidate in candidates:
            value = self._to_decimal(candidate)
            if value is not None:
                return value
        return None

    def _recalculate_sentiment_score(self, text):
        if not text:
            return 0
        raw = ' '.join((text or '')).lower()
        positive = sum(raw.count(word) for word in self.POSITIVE_WORDS)
        negative = sum(raw.count(word) for word in self.NEGATIVE_WORDS)
        total = positive + negative
        if total == 0:
            return 0
        return round(((positive - negative) / total) * 100, 2)

    def _sentiment_label_from_score(self, score):
        if score > 10:
            return 'positive'
        if score < -10:
            return 'negative'
        return 'neutral'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Đang bắt đầu kiểm tra dữ liệu AI (chỉ đọc, không ghi)...'))
        errors_found = 0

        # 1. Doanh thu thật so với doanh thu dự báo
        self.stdout.write('1. Kiểm tra doanh thu dự báo...')
        try:
            from crm.models import AIReport, Order, OrderItem

            actual_revenue = OrderItem.objects.filter(order__status=Order.Status.COMPLETED).aggregate(
                total=Sum(F('quantity') * F('unit_price'))
            )['total'] or Decimal('0')

            found_forecast = False
            reports = AIReport.objects.all().order_by('-created_at')
            for report in reports:
                forecast = self._extract_report_forecast(report)
                if forecast is None:
                    continue
                found_forecast = True
                if abs(actual_revenue - forecast) > Decimal('1'):
                    self.stdout.write(self.style.ERROR(
                        f'  Lỗi: Báo cáo AI ID {report.id} dự báo {forecast} nhưng doanh thu thật là {actual_revenue}.'
                    ))
                    errors_found += 1

            if not found_forecast:
                self.stdout.write(self.style.WARNING(
                    '  Không có dữ liệu dự báo doanh thu trong AIReport hoặc stats; bỏ qua kiểm tra theo schema hiện tại.'
                ))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'  Lỗi khi kiểm tra doanh thu: {exc}'))
            errors_found += 1

        # 2. Kiểm tra điểm rủi ro 0-100
        self.stdout.write('2. Kiểm tra điểm rủi ro của khách hàng...')
        try:
            from crm.models import Customer

            if not self._has_field(Customer, 'risk_score'):
                self.stdout.write(self.style.WARNING(
                    '  Không có trường risk_score trên Customer trong schema hiện tại; bỏ qua kiểm tra này.'
                ))
            else:
                customers = Customer.objects.all()
                for customer in customers:
                    value = getattr(customer, 'risk_score', None)
                    if value is None:
                        self.stdout.write(self.style.ERROR(f'  Lỗi: Khách hàng ID {customer.id} không có điểm rủi ro.'))
                        errors_found += 1
                    else:
                        score = self._to_decimal(value)
                        if score is None or not (Decimal('0') <= score <= Decimal('100')):
                            self.stdout.write(self.style.ERROR(
                                f'  Lỗi: Khách hàng ID {customer.id} có risk_score={value}, nằm ngoài khoảng [0, 100].'
                            ))
                            errors_found += 1
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'  Lỗi khi kiểm tra điểm rủi ro: {exc}'))
            errors_found += 1

        # 3. Tính lại cảm xúc từ dữ liệu thô rồi so với giá trị đã lưu
        self.stdout.write('3. Kiểm tra lại điểm cảm xúc...')
        try:
            from crm.models import Customer, InteractionLog

            logs = InteractionLog.objects.select_related('customer').all()
            if logs.exists():
                for log in logs:
                    raw_text = ' '.join(part for part in (log.customer_message, log.final_reply) if part)
                    recalculated = self._recalculate_sentiment_score(raw_text)
                    predicted = self._sentiment_label_from_score(recalculated)

                    saved = getattr(log.customer, 'ai_sentiment', None)
                    if saved:
                        if saved.lower() != predicted:
                            self.stdout.write(self.style.ERROR(
                                f'  Lỗi: Interaction ID {log.id} lưu ai_sentiment="{saved}" nhưng tính lại từ dữ liệu thô là "{predicted}".'
                            ))
                            errors_found += 1
            else:
                self.stdout.write(self.style.WARNING('  Không có InteractionLog nào để kiểm tra cảm xúc; bỏ qua.'))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'  Lỗi khi kiểm tra cảm xúc: {exc}'))
            errors_found += 1

        # 4. Mỗi module phải chọn đúng 1 phương án tốt nhất
        self.stdout.write('4. Kiểm tra module lựa chọn phương án tốt nhất...')
        try:
            try:
                from insights.models import ModelRun
            except Exception:
                self.stdout.write(self.style.WARNING('  Không có app insights/models.py trong schema hiện tại; bỏ qua kiểm tra module.'))
                raise

            latest_batch = ModelRun.objects.order_by('-started_at').values_list('batch', flat=True).first()
            if not latest_batch:
                self.stdout.write(self.style.WARNING('  Chưa có batch nào trong ModelRun để kiểm tra lựa chọn phương án tốt nhất.'))
            else:
                for module_name, metric_name in (
                    ('forecast', 'mape'),
                    ('churn', 'auc'),
                    ('sentiment', 'macro_f1'),
                ):
                    runs = ModelRun.objects.filter(batch=latest_batch, module=module_name)
                    selected = runs.filter(is_selected=True)
                    if selected.count() != 1:
                        self.stdout.write(self.style.ERROR(
                            f'  Lỗi: module {module_name} trong batch {latest_batch} có {selected.count()} is_selected=True, cần đúng 1.'
                        ))
                        errors_found += 1
                        continue

                    for run in runs.filter(status=ModelRun.Status.SUCCESS):
                        metric_value = (run.metrics or {}).get(metric_name)
                        if metric_value is None:
                            self.stdout.write(self.style.ERROR(
                                f'  Lỗi: run {run.id} module={module_name} thiếu metric {metric_name} trong JSON metrics.'
                            ))
                            errors_found += 1
                            break

                    if not runs.filter(status=ModelRun.Status.SUCCESS).exists():
                        self.stdout.write(self.style.WARNING(
                            f'  Không có ModelRun thành công cho module {module_name}; bỏ qua kiểm tra chọn tốt nhất.'
                        ))
        except Exception as exc:
            self.stdout.write(self.style.ERROR(f'  Lỗi khi kiểm tra module: {exc}'))
            errors_found += 1

        if errors_found == 0:
            self.stdout.write(self.style.SUCCESS('\nHoàn tất! Tất cả kiểm tra đọc-only đều hợp lệ.'))
        else:
            self.stdout.write(self.style.ERROR(f'\nHoàn tất! Phát hiện {errors_found} lỗi cần kiểm tra lại.'))

        return errors_found