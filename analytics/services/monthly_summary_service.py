"""월별 세무 현황 결산 및 부가세 공제 구조 분석 서비스."""

from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from businesses.models import Business
from payroll.services.payment_service import get_monthly_summary as get_payroll_summary
from tax.services.deduction_breakdown_service import build_deduction_breakdown
from tax.services.vat_service import VatForecastService
from transactions.models import MonthlySalesSummary, Transaction
from transactions.services.querysets import effective_transactions

_LABOR_CATEGORY_CODE = "LABOR"
_LABOR_CATEGORY_LABEL = "인건비"


def _get_vat_filing_due_date(year: int, month: int) -> str:
    """해당 월에 대한 부가세 신고 납부 기한."""
    if 1 <= month <= 3:
        return f"{year}-04-25"
    elif 4 <= month <= 6:
        return f"{year}-07-25"
    elif 7 <= month <= 9:
        return f"{year}-10-25"
    else:
        return f"{year + 1}-01-25"


def _get_total_sales(business_id: int, year: int, month: int) -> Decimal:
    business = Business.objects.get(pk=business_id)
    individual_sales = effective_transactions(
        business=business,
        start_date=date(year, month, 1),
        end_date=date(year, month, monthrange(year, month)[1]),
    ).filter(
        transaction_type=Transaction.TransactionType.SALE,
    ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

    card_sales = MonthlySalesSummary.objects.filter(
        business_id=business_id, year=year, month=month,
    ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

    return individual_sales + card_sales


def _get_expense_breakdown(business_id: int, year: int, month: int) -> tuple[list[dict], Decimal]:
    business = Business.objects.get(pk=business_id)
    purchase_qs = effective_transactions(
        business=business,
        start_date=date(year, month, 1),
        end_date=date(year, month, monthrange(year, month)[1]),
    ).filter(
        transaction_type=Transaction.TransactionType.PURCHASE,
        expense_purpose=Transaction.ExpensePurpose.BUSINESS,
    )

    category_labels = dict(Transaction.Category.choices)

    breakdown = []
    total_expense = Decimal("0")
    for row in purchase_qs.values("category").annotate(amount=Sum("total_amount")):
        amount = row["amount"] or Decimal("0")
        total_expense += amount
        breakdown.append({
            "category": row["category"],
            "label": category_labels.get(row["category"], row["category"]),
            "amount": int(amount),
            "ratio": None,
        })

    return breakdown, total_expense


def _get_figma_grouped_expense_breakdown(business_id: int, year: int, month: int, labor_amount: int) -> list[dict]:
    """피그마 디자인 4대 카테고리(재료비, 인건비, 임차료·관리비, 기타 경비)."""
    business = Business.objects.get(pk=business_id)
    purchase_qs = effective_transactions(
        business=business,
        start_date=date(year, month, 1),
        end_date=date(year, month, monthrange(year, month)[1]),
    ).filter(
        transaction_type=Transaction.TransactionType.PURCHASE,
        expense_purpose=Transaction.ExpensePurpose.BUSINESS,
    )

    mat_sum = Decimal("0")
    rent_sum = Decimal("0")
    other_sum = Decimal("0")

    for tx in purchase_qs:
        amt = tx.total_amount or Decimal("0")
        cat = tx.category
        if cat == Transaction.Category.RAW_MATERIAL:
            mat_sum += amt
        elif cat in (Transaction.Category.RENT, Transaction.Category.UTILITIES):
            rent_sum += amt
        else:
            other_sum += amt

    labor_dec = Decimal(str(labor_amount)) if labor_amount else Decimal("0")
    total = mat_sum + labor_dec + rent_sum + other_sum

    def _calc_ratio(val):
        return round(float(val / total * 100)) if total else 0

    return [
        {"category": "재료비", "amount": int(mat_sum), "ratio": _calc_ratio(mat_sum)},
        {"category": "인건비", "amount": int(labor_dec), "ratio": _calc_ratio(labor_dec)},
        {"category": "임차료·관리비", "amount": int(rent_sum), "ratio": _calc_ratio(rent_sum)},
        {"category": "기타 경비", "amount": int(other_sum), "ratio": _calc_ratio(other_sum)},
    ]


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _change_rate(current, previous):
    if not previous:
        return None
    return round((float(current) - float(previous)) / float(previous) * 100, 1)


def _expense_totals_by_category(business_id: int, year: int, month: int) -> dict[str, Decimal]:
    breakdown, _ = _get_expense_breakdown(business_id, year, month)
    payroll = get_payroll_summary(business_id, year, month)
    result = {item["category"]: Decimal(str(item["amount"])) for item in breakdown}
    result[_LABOR_CATEGORY_CODE] = Decimal(str(payroll["total_labor_cost"]))
    return result


def get_monthly_tax_summary(business_id: int, year: int, month: int) -> dict:
    """홈 화면 상단 결산 및 부가세 적립금 종합 요약."""
    business = Business.objects.get(pk=business_id)
    payroll_summary = get_payroll_summary(business_id, year, month)
    total_sales = _get_total_sales(business_id, year, month)

    raw_expense_breakdown, total_expense_excluding_payroll = _get_expense_breakdown(business_id, year, month)
    total_expense = total_expense_excluding_payroll + payroll_summary["total_labor_cost"]

    # 피그마 4대 카테고리
    expense_breakdown = _get_figma_grouped_expense_breakdown(
        business_id, year, month, payroll_summary["total_labor_cost"]
    )

    net_profit = int(total_sales) - int(total_expense)
    profit_margin = round(float(net_profit) / float(total_sales) * 100, 1) if total_sales else None

    # 전월 대비 증감률
    previous_year, previous_month = _previous_month(year, month)
    previous_sales = _get_total_sales(business_id, previous_year, previous_month)
    previous_categories = _expense_totals_by_category(business_id, previous_year, previous_month)
    previous_expense = sum(previous_categories.values(), Decimal("0"))

    top_category = "LABOR" if payroll_summary["total_labor_cost"] > 0 else None

    # 부가세 및 공제액 계산
    vat_reserve_amount = None
    vat_breakdown = None
    vat_warnings = []

    if business.tax_type == "GENERAL":
        forecast = VatForecastService.calculate(business=business, year=year, month=month)
        # Tax 앱을 부가세 계산의 단일 진실 공급원으로 사용한다. 이전 구현은
        # Analytics가 raw Transaction을 다시 합산하면서 개인 지출/중복 거래까지
        # 의제매입 후보로 포함해 Tax API와 서로 다른 금액을 반환할 수 있었다.
        sales_tax = int(forecast["output_vat"])
        purchase_tax = int(forecast["deductible_input_vat"])
        deemed_deduction = int(forecast["deemed_purchase_deduction"])
        vat_reserve_amount = int(forecast["payable_vat"])
        vat_breakdown = {
            "sales_tax": sales_tax,
            "purchase_tax": purchase_tax,
            "deemed_purchase_deduction": deemed_deduction,
        }
        vat_warnings = forecast.get("warnings", [])
    elif business.tax_type in ("SIMPLIFIED", "EXEMPT"):
        vat_reserve_amount = None
        vat_breakdown = None

    return {
        "year": year,
        "month": month,
        "vat_reserve_amount": vat_reserve_amount,
        "vat_breakdown": vat_breakdown,
        "vat_filing_due_date": _get_vat_filing_due_date(year, month),
        "tax_type": business.tax_type,
        "total_sales": int(total_sales),
        "total_expense": int(total_expense),
        "net_profit": int(net_profit),
        "profit_margin": profit_margin,
        "sales_change_rate": _change_rate(total_sales, previous_sales),
        "expense_change_rate": _change_rate(total_expense, previous_expense),
        "top_increasing_category": top_category,
        "expense_breakdown": expense_breakdown,
        "raw_expense_breakdown": raw_expense_breakdown,
        "payroll_withholding_tax": payroll_summary["withholding_tax"],
        "payroll_employee_count": payroll_summary["employee_count"],
        "warnings": vat_warnings,
    }


def get_deduction_breakdown(business_id: int, year: int, month: int) -> dict:
    """Tax 앱의 공제 구조 계산 결과를 홈 화면 응답으로 그대로 사용한다."""
    business = Business.objects.get(pk=business_id)
    return build_deduction_breakdown(
        business=business,
        year=year,
        month=month,
    )
