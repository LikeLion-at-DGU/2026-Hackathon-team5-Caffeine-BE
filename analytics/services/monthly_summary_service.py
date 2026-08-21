"""홈 화면에 필요한 월별 손익과 부가세 현황을 집계한다."""

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
    """조회 월이 속한 과세기간의 부가세 신고 기한을 반환한다."""
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
    """지출을 재료비·인건비·임차관리비·기타 경비로 묶는다."""
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
    """홈 화면에 표시할 월간 손익과 부가세 적립 정보를 반환한다."""
    business = Business.objects.get(pk=business_id)
    payroll_summary = get_payroll_summary(business_id, year, month)
    total_sales = _get_total_sales(business_id, year, month)

    raw_expense_breakdown, total_expense_excluding_payroll = _get_expense_breakdown(business_id, year, month)
    total_expense = total_expense_excluding_payroll + payroll_summary["total_labor_cost"]

    # 화면에서 비교하기 쉬운 네 가지 지출군으로 다시 묶는다.
    expense_breakdown = _get_figma_grouped_expense_breakdown(
        business_id, year, month, payroll_summary["total_labor_cost"]
    )

    net_profit = int(total_sales) - int(total_expense)
    profit_margin = round(float(net_profit) / float(total_sales) * 100, 1) if total_sales else None

    # 직전 월을 같은 기준으로 집계해 증감률을 계산한다.
    previous_year, previous_month = _previous_month(year, month)
    previous_sales = _get_total_sales(business_id, previous_year, previous_month)
    previous_categories = _expense_totals_by_category(business_id, previous_year, previous_month)
    previous_expense = sum(previous_categories.values(), Decimal("0"))

    top_category = "LABOR" if payroll_summary["total_labor_cost"] > 0 else None

    # 간이·면세 사업자는 일반과세자와 계산 근거가 달라 별도 안내한다.
    vat_reserve_amount = None
    vat_breakdown = None
    vat_warnings = []

    if business.tax_type == "GENERAL":
        forecast = VatForecastService.calculate(business=business, year=year, month=month)
        # 개인·중복 거래의 제외 기준이 달라지지 않도록 Tax 계산 결과를 재사용한다.
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
    """Tax 앱과 동일한 기준의 공제 구조를 홈 화면에 전달한다."""
    business = Business.objects.get(pk=business_id)
    return build_deduction_breakdown(
        business=business,
        year=year,
        month=month,
    )
