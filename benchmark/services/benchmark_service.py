from dataclasses import asdict
from businesses.models import Business
from benchmark.models import AIDiagnosisHistory
from benchmark.services.calculator import BenchmarkCalculator
from benchmark.services.ai_diagnostician import AIDiagnostician


class BenchmarkService:
    """AI 경영 진단 및 상권 벤치마크 통합 오케스트레이션 서비스."""

    @classmethod
    def get_dashboard_data(cls, business: Business, year: int, month: int) -> dict:
        year_month_str = f"{year:04d}-{month:02d}"

        # 1. 정량 지표 및 상권 비교 계산
        calc = BenchmarkCalculator.calculate(business=business, year=year, month=month)

        # 2. AI 진단 캐시 조회. 장부/급여가 바뀌었으면 같은 연월 캐시라도
        # 폐기하고 다시 생성해 정량 지표와 AI 문장이 서로 어긋나지 않게 한다.
        fingerprint = cls._calculation_fingerprint(calc)
        history = AIDiagnosisHistory.objects.filter(
            business=business,
            year_month=year_month_str,
        ).first()

        cached_fingerprint = (
            (history.raw_response or {}).get("_calculation_fingerprint")
            if history and isinstance(history.raw_response, dict)
            else None
        )
        if not history or cached_fingerprint != fingerprint:
            ai_res = AIDiagnostician().diagnose(calc)
            raw_response = dict(ai_res.raw_response or {})
            raw_response["_calculation_fingerprint"] = fingerprint
            history, _ = AIDiagnosisHistory.objects.update_or_create(
                business=business,
                year_month=year_month_str,
                defaults={
                    "score": ai_res.score,
                    "grade_label": ai_res.grade_label,
                    "prescriptions": ai_res.prescriptions,
                    "summary_points": ai_res.summary_points,
                    "is_fallback": ai_res.is_fallback,
                    "raw_response": raw_response,
                },
            )

        # 3. 피그마 화면 100% 매칭 응답 구조 조립
        return {
            "business_id": calc.business_id,
            "business_name": calc.business_name,
            "year_month": calc.year_month,
            "region_name": calc.region_name,
            "data_source": "서울시 상권분석서비스 (외식업·커피음료 표준)",
            "overview": {
                "total_revenue": calc.total_revenue,
                "total_expense": calc.total_expense,
                "cost_status": calc.cost_status,
                "revenue_diff_pct": calc.revenue_diff_pct,
                "raw_material_ratio": calc.raw_material_ratio,
                "benchmark_raw_material_ratio": calc.benchmark_raw_material_ratio,
                "raw_material_diff_pct": calc.raw_material_diff_pct,
                "vat_deduction_estimate": calc.vat_deduction_estimate,
            },
            "ai_prescriptions": history.prescriptions,
            "overall_health": {
                "score": history.score,
                "grade_label": history.grade_label,
                "summary_points": history.summary_points,
            },
            "category_comparison": [asdict(item) for item in calc.category_comparison],
            "monthly_trends": [asdict(item) for item in calc.monthly_trends],
            "mom_profit_improvement": calc.mom_profit_improvement,
        }

    @classmethod
    def refresh_diagnosis(cls, business: Business, year: int, month: int) -> dict:
        year_month_str = f"{year:04d}-{month:02d}"

        # 1. 정량 지표 계산
        calc = BenchmarkCalculator.calculate(business=business, year=year, month=month)

        # 2. AI 진단 강제 재실행
        ai_res = AIDiagnostician().diagnose(calc)

        raw_response = dict(ai_res.raw_response or {})
        raw_response["_calculation_fingerprint"] = cls._calculation_fingerprint(calc)
        history, _ = AIDiagnosisHistory.objects.update_or_create(
            business=business,
            year_month=year_month_str,
            defaults={
                "score": ai_res.score,
                "grade_label": ai_res.grade_label,
                "prescriptions": ai_res.prescriptions,
                "summary_points": ai_res.summary_points,
                "is_fallback": ai_res.is_fallback,
                "raw_response": raw_response,
            },
        )

        return {
            "business_id": business.id,
            "year_month": year_month_str,
            "overall_health": {
                "score": history.score,
                "grade_label": history.grade_label,
                "summary_points": history.summary_points,
            },
            "ai_prescriptions": history.prescriptions,
            "is_fallback": history.is_fallback,
        }

    @staticmethod
    def _calculation_fingerprint(calc) -> dict:
        """AI 문장을 무효화해야 하는 핵심 정량값의 직렬화 가능한 스냅샷."""
        return {
            "total_revenue": calc.total_revenue,
            "total_expense": calc.total_expense,
            "cost_status": calc.cost_status,
            "raw_material_ratio": calc.raw_material_ratio,
            "category_comparison": [
                {
                    "category": item.category,
                    "my_ratio": item.my_ratio,
                    "diff_ratio": item.diff_ratio,
                }
                for item in calc.category_comparison
            ],
        }
