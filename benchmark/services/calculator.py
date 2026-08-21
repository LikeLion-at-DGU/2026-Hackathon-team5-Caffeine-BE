from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from django.db.models import Sum

from businesses.models import Business
from transactions.models import Transaction, MonthlySalesSummary
from payroll.services.payment_service import get_monthly_summary as get_payroll_summary
from benchmark.models import IndustryBenchmark
from tax.services.vat_service import VatForecastService, UnsupportedTaxType
from tax.services.periods import month_range
from transactions.services.querysets import effective_transactions


@dataclass
class CategoryComparisonItem:
    category: str
    name: str
    my_ratio: float
    benchmark_ratio: float
    diff_ratio: float
    status_badge: str
    status_type: str  # "GOOD" | "WARNING" | "CAUTION"


@dataclass
class MonthlyTrendItem:
    month: str
    my_profit_ratio: float
    benchmark_profit_ratio: float
    revenue: int
    expense: int
    profit: int
    my_raw_material_ratio: float
    benchmark_raw_material_ratio: float
    my_labor_ratio: float
    benchmark_labor_ratio: float


@dataclass
class BenchmarkCalculationResult:
    business_id: int
    business_name: str
    year_month: str
    region_name: str
    total_revenue: int
    total_expense: int
    cost_status: str
    revenue_diff_pct: float
    raw_material_ratio: float
    benchmark_raw_material_ratio: float
    raw_material_diff_pct: float
    category_comparison: list[CategoryComparisonItem]
    monthly_trends: list[MonthlyTrendItem]
    mom_profit_improvement: float
    vat_deduction_estimate: int


class BenchmarkCalculator:
    """사업장의 거래·매출·급여를 같은 기간의 상권 지표와 비교한다."""

    @staticmethod
    def _to_pct(val, base):
        """비교 기준이 없을 때 0으로 처리해 비율 계산을 안정화한다."""
        if base is None or base <= 0:
            return 0.0
        return float((val / base * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))

    @staticmethod
    def _get_or_create_benchmark(year_month_str: str) -> IndustryBenchmark:
        """해당 월의 상권 지표를 조회하고 없으면 데모 기본값을 생성한다."""
        benchmark = IndustryBenchmark.objects.filter(year_month=year_month_str).first()
        if not benchmark:
            benchmark = IndustryBenchmark.objects.create(
                region="성수동 상권",
                business_type="커피-음료",
                year_month=year_month_str,
                raw_material_ratio=Decimal("32.00"),
                labor_ratio=Decimal("25.00"),
                rent_ratio=Decimal("12.50"),
                supplies_ratio=Decimal("4.80"),
                operating_profit_ratio=Decimal("16.80"),
                benchmark_monthly_revenue=10400000,
                peak_time_ratio=Decimal("31.60"),
            )
        return benchmark

    @staticmethod
    def _shift_month(year: int, month: int, delta: int):
        """연도 경계를 포함해 지정한 개월 수만큼 이동한다."""
        total = year * 12 + (month - 1) + delta
        return total // 12, total % 12 + 1

    @classmethod
    def _calculate_month_metrics(cls, business: Business, year: int, month: int) -> dict:
        """특정 월의 실제 장부에서 매출과 지출 비율을 집계한다."""
        start_date, end_date = month_range(year, month)
        transactions = effective_transactions(
            business=business,
            start_date=start_date,
            end_date=end_date,
        )

        # 서로 다른 매출 채널인 카드 집계와 건별 증빙 매출을 함께 반영한다.
        sales_summary = MonthlySalesSummary.objects.filter(
            business=business,
            year=year,
            month=month,
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

        tx_sales = transactions.filter(
            transaction_type=Transaction.TransactionType.SALE,
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

        total_revenue = sales_summary + tx_sales

        # 대시보드와 금액이 어긋나지 않도록 유효한 사업 지출만 사용한다.
        purchases = transactions.filter(
            transaction_type=Transaction.TransactionType.PURCHASE,
            expense_purpose=Transaction.ExpensePurpose.BUSINESS,
        )

        raw_mat_sum = purchases.filter(
            category=Transaction.Category.RAW_MATERIAL
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")
        supplies_sum = purchases.filter(
            category=Transaction.Category.SUPPLIES
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")
        rent_sum = purchases.filter(
            category__in=[Transaction.Category.RENT, Transaction.Category.UTILITIES]
        ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")
        purchase_sum = purchases.aggregate(total=Sum("total_amount"))["total"] or Decimal("0")
        payroll_summary = get_payroll_summary(business.id, year, month)
        payroll_sum = Decimal(str(payroll_summary["total_labor_cost"]))
        total_expense = purchase_sum + payroll_sum

        return {
            "total_revenue": total_revenue,
            "total_expense": total_expense,
            "raw_mat_sum": raw_mat_sum,
            "supplies_sum": supplies_sum,
            "rent_sum": rent_sum,
            "payroll_sum": payroll_sum,
            "purchase_sum": purchase_sum,
            "my_raw_mat_pct": cls._to_pct(raw_mat_sum, total_revenue),
            "my_labor_pct": cls._to_pct(payroll_sum, total_revenue),
            "my_rent_pct": cls._to_pct(rent_sum, total_revenue),
            "my_supplies_pct": cls._to_pct(supplies_sum, total_revenue),
        }

    @staticmethod
    def _calculate_vat_deduction_estimate(business: Business, year: int, month: int) -> int:
        """해당 월의 예상 매입세액 공제액을 반환한다.

        VatForecastService는 일반과세자(GENERAL)만 지원하므로, 그 외 과세유형이거나
        계산에 필요한 데이터가 없어 실패하는 경우 0으로 안전하게 폴백한다.
        """
        try:
            result = VatForecastService.calculate(business=business, year=year, month=month)
            return int(result["total_deductible_input_vat"])
        except UnsupportedTaxType:
            return 0
        except Exception:
            return 0

    @classmethod
    def calculate(cls, business: Business, year: int, month: int) -> BenchmarkCalculationResult:
        year_month_str = f"{year:04d}-{month:02d}"

        # 상권과 사업장 지표를 같은 연월 기준으로 맞춘다.
        benchmark = cls._get_or_create_benchmark(year_month_str)
        metrics = cls._calculate_month_metrics(business, year, month)

        total_revenue = metrics["total_revenue"]
        total_expense = metrics["total_expense"]
        my_raw_mat_pct = metrics["my_raw_mat_pct"]
        my_labor_pct = metrics["my_labor_pct"]
        my_rent_pct = metrics["my_rent_pct"]
        my_supplies_pct = metrics["my_supplies_pct"]

        bm_raw_mat = float(benchmark.raw_material_ratio)
        bm_labor = float(benchmark.labor_ratio)
        bm_rent = float(benchmark.rent_ratio)
        bm_supplies = float(benchmark.supplies_ratio)

        # 화면에서 비교할 비용 항목을 동일한 단위로 구성한다.
        diff_raw = round(my_raw_mat_pct - bm_raw_mat, 1)
        diff_labor = round(my_labor_pct - bm_labor, 1)
        diff_rent = round(my_rent_pct - bm_rent, 1)
        diff_supplies = round(my_supplies_pct - bm_supplies, 1)

        category_comparison = [
            CategoryComparisonItem(
                category="RAW_MATERIAL",
                name="식자재·원두",
                my_ratio=my_raw_mat_pct,
                benchmark_ratio=bm_raw_mat,
                diff_ratio=diff_raw,
                status_badge=f"평균 대비 {'+' if diff_raw > 0 else ''}{diff_raw}%",
                status_type="WARNING" if diff_raw > 2.0 else "GOOD",
            ),
            CategoryComparisonItem(
                category="PAYROLL",
                name="인건비",
                my_ratio=my_labor_pct,
                benchmark_ratio=bm_labor,
                diff_ratio=diff_labor,
                status_badge=f"적정 ({diff_labor:+.1f}%)" if abs(diff_labor) <= 3.0 else f"{diff_labor:+.1f}%",
                status_type="GOOD" if diff_labor <= 1.0 else "CAUTION",
            ),
            CategoryComparisonItem(
                category="RENT",
                name="임차료·관리비",
                my_ratio=my_rent_pct,
                benchmark_ratio=bm_rent,
                diff_ratio=diff_rent,
                status_badge=f"양호 ({diff_rent:+.1f}%)" if diff_rent < 0 else f"{diff_rent:+.1f}%",
                status_type="GOOD" if diff_rent <= 0 else "WARNING",
            ),
            CategoryComparisonItem(
                category="SUPPLIES",
                name="포장재·소모품",
                my_ratio=my_supplies_pct,
                benchmark_ratio=bm_supplies,
                diff_ratio=diff_supplies,
                status_badge=f"절감 권장 (+{diff_supplies}%)" if diff_supplies > 0 else f"{diff_supplies:+.1f}%",
                status_type="CAUTION" if diff_supplies > 1.0 else "GOOD",
            ),
        ]

        # 현재 월을 포함한 6개월 추이를 실제 장부로 생성한다.
        monthly_trends = []
        for delta in range(-5, 1):
            t_year, t_month = cls._shift_month(year, month, delta)
            t_year_month_str = f"{t_year:04d}-{t_month:02d}"

            if delta == 0:
                # 현재 월은 앞서 계산한 결과를 재사용한다.
                t_metrics = metrics
                t_benchmark = benchmark
            else:
                t_benchmark = cls._get_or_create_benchmark(t_year_month_str)
                t_metrics = cls._calculate_month_metrics(business, t_year, t_month)

            t_revenue = t_metrics["total_revenue"]
            t_expense = t_metrics["total_expense"]
            t_profit = t_revenue - t_expense

            monthly_trends.append(
                MonthlyTrendItem(
                    month=t_year_month_str,
                    my_profit_ratio=cls._to_pct(t_profit, t_revenue),
                    benchmark_profit_ratio=float(t_benchmark.operating_profit_ratio),
                    revenue=int(t_revenue),
                    expense=int(t_expense),
                    profit=int(t_profit),
                    my_raw_material_ratio=t_metrics["my_raw_mat_pct"],
                    benchmark_raw_material_ratio=float(t_benchmark.raw_material_ratio),
                    my_labor_ratio=t_metrics["my_labor_pct"],
                    benchmark_labor_ratio=float(t_benchmark.labor_ratio),
                )
            )

        # 최근 두 달의 실제 이익률 차이로 전월 대비 개선폭을 계산한다.
        mom_profit_improvement = (
            round(monthly_trends[-1].my_profit_ratio - monthly_trends[-2].my_profit_ratio, 1)
            if len(monthly_trends) >= 2
            else 0.0
        )

        # 상권 평균 매출과의 차이를 비율로 비교한다.
        bm_rev = float(benchmark.benchmark_monthly_revenue)
        rev_diff_pct = round(((float(total_revenue) - bm_rev) / bm_rev) * 100, 1) if bm_rev else 0.0

        # 지원하지 않는 과세유형은 공제 추정치를 0으로 유지한다.
        vat_deduction_estimate = cls._calculate_vat_deduction_estimate(business, year, month)

        return BenchmarkCalculationResult(
            business_id=business.id,
            business_name=business.business_name,
            year_month=year_month_str,
            region_name=benchmark.region,
            total_revenue=int(total_revenue),
            total_expense=int(total_expense),
            cost_status="양호" if total_expense < total_revenue * Decimal("0.75") else "주의",
            revenue_diff_pct=rev_diff_pct,
            raw_material_ratio=my_raw_mat_pct,
            benchmark_raw_material_ratio=bm_raw_mat,
            raw_material_diff_pct=diff_raw,
            category_comparison=category_comparison,
            monthly_trends=monthly_trends,
            mom_profit_improvement=mom_profit_improvement,
            vat_deduction_estimate=vat_deduction_estimate,
        )
