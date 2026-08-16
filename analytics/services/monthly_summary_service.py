"""월별 세무 현황 결산 조합 서비스.

원칙: analytics는 세법 판단을 하지 않는다. payroll/tax의 계산 결과는 그대로 참조하고,
transactions 데이터는 단순 합산·그룹핑만 한다 (이건 "계산"이 아니라 "집계"라 analytics
안에서 직접 해도 원칙에 안 어긋남 — 세율 적용이나 공제 판정 같은 진짜 세법 로직만 tax 담당).

2026-08-14: 원래 별도 endpoint였던 /api/analytics/cost-ratio/를 흡수 — expense_breakdown이
3개 그룹 요약이 아니라 transactions.Transaction.Category 그대로 세분화해서 보여줌.
"""

from decimal import Decimal

from django.db.models import Sum

from payroll.services.payment_service import get_monthly_summary as get_payroll_summary
from transactions.models import MonthlySalesSummary, Transaction

_LABOR_CATEGORY_CODE = "LABOR"
_LABOR_CATEGORY_LABEL = "인건비"


def _get_total_sales(business_id: int, year: int, month: int) -> Decimal:
    individual_sales = Transaction.objects.filter(
        business_id=business_id,
        transaction_type=Transaction.TransactionType.SALE,
        transaction_date__year=year,
        transaction_date__month=month,
        cancel_status=Transaction.CancelStatus.NORMAL,
    ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

    card_sales = MonthlySalesSummary.objects.filter(
        business_id=business_id, year=year, month=month,
    ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

    return individual_sales + card_sales


def _get_expense_breakdown(business_id: int, year: int, month: int) -> tuple[list[dict], Decimal]:
    purchase_qs = Transaction.objects.filter(
        business_id=business_id,
        transaction_type=Transaction.TransactionType.PURCHASE,
        expense_purpose=Transaction.ExpensePurpose.BUSINESS,
        transaction_date__year=year,
        transaction_date__month=month,
        cancel_status=Transaction.CancelStatus.NORMAL,
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
            "ratio": None,  # 인건비까지 합산한 뒤 재계산
        })

    return breakdown, total_expense


def get_monthly_tax_summary(business_id: int, year: int, month: int) -> dict:
    payroll_summary = get_payroll_summary(business_id, year, month)
    total_sales = _get_total_sales(business_id, year, month)
    expense_breakdown, total_expense_excluding_payroll = _get_expense_breakdown(business_id, year, month)

    expense_breakdown.append({
        "category": _LABOR_CATEGORY_CODE,
        "label": _LABOR_CATEGORY_LABEL,
        "amount": payroll_summary["total_labor_cost"],
        "ratio": None,
    })

    total_expense = total_expense_excluding_payroll + payroll_summary["total_labor_cost"]
    if total_expense:
        for item in expense_breakdown:
            item["ratio"] = round(item["amount"] / float(total_expense) * 100, 1)

    net_profit = float(total_sales) - float(total_expense)
    profit_margin = round(net_profit / float(total_sales) * 100, 1) if total_sales else None

    return {
        "year": year,
        "month": month,
        "vat_reserve_amount": None,
        "vat_breakdown": None,
        "vat_filing_due_date": None,
        "tax_type": None,
        "total_sales": int(total_sales),
        "total_expense": int(total_expense),
        "net_profit": int(net_profit),
        "profit_margin": profit_margin,
        "sales_change_rate": None,
        "expense_change_rate": None,
        "top_increasing_category": None,
        "expense_breakdown": expense_breakdown,
        "payroll_withholding_tax": payroll_summary["withholding_tax"],
        "payroll_employee_count": payroll_summary["employee_count"],
    }