from django.db import models
from businesses.models import Business


class IndustryBenchmark(models.Model):
    """서울시 상권분석 및 공공 통계 기반의 업종별 표준 벤치마크 지표."""

    region = models.CharField(max_length=100, default="성수동 상권", help_text="상권명")
    trdar_code = models.CharField(max_length=50, blank=True, help_text="서울시 상권코드")
    trdar_se_nm = models.CharField(max_length=50, default="골목상권", help_text="상권구분명")
    business_type = models.CharField(max_length=50, default="커피-음료", help_text="서비스 업종명")
    year_month = models.CharField(max_length=7, help_text="기준 연월 (YYYY-MM)")

    # 사업장 비용 구조와 같은 단위로 비교하는 상권 재무 비율.
    raw_material_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=32.00, help_text="식자재·원두 비중 (%)")
    labor_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=25.00, help_text="인건비 비중 (%)")
    rent_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=12.50, help_text="임차료·관리비 비중 (%)")
    supplies_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=4.80, help_text="포장재·소모품 비중 (%)")
    operating_profit_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=16.80, help_text="영업이익률 (%)")

    # 서울시 상권 데이터에서 가져오는 매출 패턴 지표.
    benchmark_monthly_revenue = models.BigIntegerField(default=10400000, help_text="상권 점포당 월평균 추정 매출액(원)")
    peak_time_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=31.60, help_text="14~17시 피크 매출 비중 (%)")
    weekday_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=62.30, help_text="주중 매출 비중 (%)")
    weekend_ratio = models.DecimalField(max_digits=5, decimal_places=2, default=37.70, help_text="주말 매출 비중 (%)")

    source = models.CharField(max_length=50, default="SEOUL_OPEN_API", help_text="데이터 출처")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year_month", "region"]
        constraints = [
            models.UniqueConstraint(
                fields=["region", "business_type", "year_month"],
                name="uniq_region_induty_year_month",
            )
        ]

    def __str__(self):
        return f"{self.region} ({self.business_type}) - {self.year_month}"


class AIDiagnosisHistory(models.Model):
    """사업장별 AI 경영 진단 및 원포인트 처방 이력 캐시."""

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="benchmark_diagnoses",
    )
    year_month = models.CharField(max_length=7, help_text="진단 대상 연월 (YYYY-MM)")

    score = models.IntegerField(default=85, help_text="종합 경영 건강도 점수 (0~100)")
    grade_label = models.CharField(max_length=100, default="분석 중...", help_text="등급 라벨")

    # 화면이 추가 가공 없이 표시할 수 있는 구조화 진단 결과.
    prescriptions = models.JSONField(default=list, help_text="AI 비서의 한 줄 처방 3가지")
    summary_points = models.JSONField(default=list, help_text="종합 경영 진단 3대 요약")
    raw_response = models.JSONField(null=True, blank=True, help_text="OpenAI 원본 응답")

    is_fallback = models.BooleanField(default=False, help_text="규칙 기반 Fallback 생성 여부")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year_month", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "year_month"],
                name="uniq_business_benchmark_diagnosis_month",
            )
        ]

    def __str__(self):
        return f"Business {self.business_id} AI Diagnosis ({self.year_month}) - {self.score}점"
