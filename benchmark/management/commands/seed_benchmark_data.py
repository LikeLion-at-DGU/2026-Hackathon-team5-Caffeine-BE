from decimal import Decimal
from django.core.management.base import BaseCommand
from benchmark.models import IndustryBenchmark
from integrations.seoul_commercial import SeoulCommercialClient, SeoulCommercialClientError


class Command(BaseCommand):
    help = "서울시 상권분석 OpenAPI 및 표준 통계를 바탕으로 IndustryBenchmark 기초 데이터를 적재합니다."

    def add_arguments(self, parser):
        parser.add_argument("--fetch-live", action="store_true", help="서울시 OpenAPI를 실시간 호출하여 데이터를 갱신합니다.")
        parser.add_argument("--year-month", default="2026-08", help="적재 대상 연월 (YYYY-MM)")

    def handle(self, *args, **options):
        year_month = options["year_month"]
        self.stdout.write(f"[BENCHMARK] [{year_month}] 상권 벤치마크 데이터 생성 시작...")

        # 1. 성수동 상권 (피그마 기본 상권)
        benchmark, created = IndustryBenchmark.objects.update_or_create(
            region="성수동 상권",
            business_type="커피-음료",
            year_month=year_month,
            defaults={
                "trdar_code": "3111490",
                "trdar_se_nm": "골목상권",
                "raw_material_ratio": Decimal("32.00"),
                "labor_ratio": Decimal("25.00"),
                "rent_ratio": Decimal("12.50"),
                "supplies_ratio": Decimal("4.80"),
                "operating_profit_ratio": Decimal("16.80"),
                "benchmark_monthly_revenue": 10400000,
                "peak_time_ratio": Decimal("31.60"),
                "weekday_ratio": Decimal("62.30"),
                "weekend_ratio": Decimal("37.70"),
                "source": "SEOUL_COMMERCIAL_DATASET",
            },
        )
        self.stdout.write(self.style.SUCCESS(f"[SUCCESS] 성수동 상권 벤치마크 생성 완료: {benchmark}"))

        # 2. 실시간 서울시 OpenAPI 조회 (옵션)
        if options["fetch_live"]:
            try:
                client = SeoulCommercialClient()
                rows = client.fetch_estimated_sales(start_index=1, end_index=10)
                self.stdout.write(f"[INFO] 서울시 OpenAPI 실시간 수집 성공: {len(rows)}건의 커피-음료 상권 데이터 수신")
                for row in rows[:3]:
                    trdar_name = row.get("TRDAR_CD_NM", "서울 주요상권")
                    sales_amt = int(float(row.get("THSMON_SELNG_AMT", 10000000)))
                    IndustryBenchmark.objects.update_or_create(
                        region=f"{trdar_name} 상권",
                        business_type="커피-음료",
                        year_month=year_month,
                        defaults={
                            "trdar_code": row.get("TRDAR_CD", ""),
                            "trdar_se_nm": row.get("TRDAR_SE_CD_NM", "골목상권"),
                            "benchmark_monthly_revenue": sales_amt,
                            "raw_material_ratio": Decimal("32.50"),
                            "labor_ratio": Decimal("24.80"),
                            "rent_ratio": Decimal("13.00"),
                            "supplies_ratio": Decimal("5.00"),
                            "operating_profit_ratio": Decimal("17.00"),
                            "source": "SEOUL_OPEN_API",
                        },
                    )
            except SeoulCommercialClientError as exc:
                self.stdout.write(self.style.WARNING(f"[WARNING] 서울시 OpenAPI 호출 실패: {exc}"))

        self.stdout.write(self.style.SUCCESS("[DONE] 벤치마크 시드 데이터 세팅 완료!"))
