"""월별 세무 현황 결산 조합 서비스.

원칙: analytics는 세법 판단을 하지 않는다. payroll/tax의 계산 결과는 그대로 참조하고,
transactions 데이터는 단순 합산·그룹핑만 한다 (이건 "계산"이 아니라 "집계"라 analytics
안에서 직접 해도 원칙에 안 어긋남 — 세율 적용이나 공제 판정 같은 진짜 세법 로직만 tax 담당).
"""

from decimal import Decimal

from django.db.models import Sum

from payroll.services.payment_service import get_monthly_summary as get_payroll_summary
from transactions.models import MonthlySalesSummary, Transaction

# 우리 쪽 4개 카테고리를 Figma 화면의 3개 그룹으로 묶는 매핑.
# transactions.Transaction.Category는 더 세분화되어 있어서(원재료/공과금/소모품 등),
# 화면 표시용으로만 단순화함 — 원본 카테고리 자체는 손대지 않음.
_EXPENSE_GROUP_MAP = {
    "RAW_MATERIAL": "재료비",
    "RENT": "임차료·관리비",
    "UTILITIES": "임차료·관리비",
}
_DEFAULT_GROUP = "기타 경비"


def _get_total_sales(business_id: int, year: int, month: int) -> Decimal:
    # 현금영수증 매출 + 세금계산서 매출: Transaction에 개별 건으로 있음
    individual_sales = Transaction.objects.filter(
        business_id=business_id,
        transaction_type=Transaction.TransactionType.SALE,
        transaction_date__year=year,
        transaction_date__month=month,
        cancel_status=Transaction.CancelStatus.NORMAL,
    ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

    # 신용카드 매출: 개별 건이 아니라 월별 집계(MonthlySalesSummary)로만 존재 — 별도로 더해야 함
    card_sales = MonthlySalesSummary.objects.filter(
        business_id=business_id, year=year, month=month,
    ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")

    return individual_sales + card_sales


def _get_expense_breakdown(business_id: int, year: int, month: int) -> list[dict]:
    purchase_qs = Transaction.objects.filter(
        business_id=business_id,
        transaction_type=Transaction.TransactionType.PURCHASE,
        expense_purpose=Transaction.ExpensePurpose.BUSINESS,
        transaction_date__year=year,
        transaction_date__month=month,
        cancel_status=Transaction.CancelStatus.NORMAL,
    )

    grouped = {}
    for row in purchase_qs.values("category").annotate(amount=Sum("total_amount")):
        group_name = _EXPENSE_GROUP_MAP.get(row["category"], _DEFAULT_GROUP)
        grouped[group_name] = grouped.get(group_name, Decimal("0")) + (row["amount"] or Decimal("0"))

    total_expense = sum(grouped.values(), Decimal("0"))

    breakdown = [
        {
            "category": name,
            "amount": int(amount),
            "ratio": round(float(amount / total_expense * 100), 1) if total_expense else 0,
        }
        for name, amount in grouped.items()
    ]
    return breakdown, total_expense


def get_monthly_tax_summary(business_id: int, year: int, month: int) -> dict:
    payroll_summary = get_payroll_summary(business_id, year, month)
    total_sales = _get_total_sales(business_id, year, month)
    expense_breakdown, total_expense_excluding_payroll = _get_expense_breakdown(business_id, year, month)

    # 인건비 항목을 지출 분류에 합류 (payroll 참조, transactions에는 인건비 거래가 없음)
    expense_breakdown.append({
        "category": "인건비",
        "amount": payroll_summary["total_labor_cost"],
        "ratio": None,  # 아래에서 total_expense 확정 후 재계산
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
        # TODO: tax 완료되면 채움
        "vat_reserve_amount": None,
        "vat_breakdown": None,
        "vat_filing_due_date": None,
        "tax_type": None,
        "total_sales": int(total_sales),
        "total_expense": int(total_expense),
        "net_profit": int(net_profit),
        "profit_margin": profit_margin,
        # TODO: 전월 대비 증감률 — 전월 데이터도 같은 방식으로 구해서 비교 필요
        "sales_change_rate": None,
        "expense_change_rate": None,
        "top_increasing_category": None,
        "expense_breakdown": expense_breakdown,
        "payroll_withholding_tax": payroll_summary["withholding_tax"],
        "payroll_employee_count": payroll_summary["employee_count"],
    }