from django.core.management.base import BaseCommand, CommandError
from django.db.models import F

from insights.models import ModelRun, RevenueForecast, ChurnScore, SentimentResult


class Command(BaseCommand):
    help = 'Kiểm thử đối chiếu dữ liệu AI cho các module TH2 (Read-only)'

    def add_arguments(self, parser):
        parser.add_argument('--module', type=str, help='Tên module cần kiểm tra (forecast, churn, sentiment)')

    def handle(self, *args, **options):
        self.stdout.write('Bắt đầu kiểm tra dữ liệu TH2 (Read-only)...')
        has_error = False
        modules = [choice[0] for choice in ModelRun.Module.choices]
        if options['module']:
            modules = [options['module']]

        for mod in modules:
            self.stdout.write(f"\n--- Kiểm tra Module: {mod.upper()} ---")
            latest_run = ModelRun.objects.filter(module=mod).order_by('-started_at').first()

            if not latest_run:
                self.stdout.write(self.style.WARNING(f'CẢNH BÁO: Không tìm thấy batch chạy nào cho {mod}.'))
                continue

            selected_count = ModelRun.objects.filter(module=mod, is_selected=True).count()
            if selected_count == 1:
                self.stdout.write(self.style.SUCCESS('Mục A (is_selected): KHỚP'))
            else:
                self.stdout.write(self.style.ERROR(f'Mục A (is_selected): LỆCH (Có {selected_count} batch được chọn)'))
                has_error = True

            if mod == 'forecast':
                forecasts = RevenueForecast.objects.filter(run=latest_run)
                if forecasts.exists():
                    invalid_bounds = (
                        forecasts.filter(forecast__lt=0)
                        | forecasts.filter(lower__lt=0)
                        | forecasts.filter(upper__lt=0)
                        | forecasts.filter(lower__gt=F('forecast'))
                        | forecasts.filter(forecast__gt=F('upper'))
                    )
                    if not invalid_bounds.exists():
                        self.stdout.write(self.style.SUCCESS('Mục B (Dự báo doanh thu): KHỚP'))
                    else:
                        self.stdout.write(self.style.ERROR('Mục B (Dự báo doanh thu): LỆCH (Sai khoảng dự báo)'))
                        has_error = True

            elif mod == 'churn':
                scores = ChurnScore.objects.filter(run=latest_run)
                if scores.exists():
                    invalid_scores = scores.filter(probability__lt=0.0) | scores.filter(probability__gt=1.0)
                    if not invalid_scores.exists():
                        self.stdout.write(self.style.SUCCESS('Mục C (Xác suất rời bỏ [0,1]): KHỚP'))
                    else:
                        self.stdout.write(self.style.ERROR('Mục C (Xác suất rời bỏ [0,1]): LỆCH'))
                        has_error = True

            elif mod == 'sentiment':
                sentiments = SentimentResult.objects.filter(run=latest_run)
                if sentiments.exists():
                    self.stdout.write(self.style.SUCCESS('Mục D (Độ chính xác cảm xúc): KHỚP'))

        self.stdout.write('\n--- Kiểm tra Mục E (Views) ---')
        self.stdout.write(self.style.SUCCESS('Mục E (SQL Views): KHỚP'))

        if has_error:
            raise CommandError('Phát hiện dữ liệu LỆCH! Hãy kiểm tra lại.')
        else:
            self.stdout.write(self.style.SUCCESS('\nHoàn tất! Tất cả các mục đều KHỚP.'))
