from transactions.models import Transaction
from payroll.models import Payment


def _parse_year_month(year_month):
    year, month = year_month.split("-")
    return int(year), int(month)


def get_sales_invoices(business, year_month):
    """매출 세금계산서 목록"""
    year, month = _parse_year_month(year_month)
    return Transaction.objects.filter(
        business=business,
        transaction_type=Transaction.TransactionType.SALE,
        source_type=Transaction.SourceType.TAX_INVOICE,
        transaction_date__year=year,
        transaction_date__month=month,
        cancel_status=Transaction.CancelStatus.NORMAL,
    )


def get_purchase_evidences(business, year_month):
    """매입 증빙 서류 (카드/현금영수증)"""
    year, month = _parse_year_month(year_month)
    return Transaction.objects.filter(
        business=business,
        transaction_type=Transaction.TransactionType.PURCHASE,
        source_type__in=[
            Transaction.SourceType.CARD_PURCHASE,
            Transaction.SourceType.CASH_RECEIPT_PURCHASE,
        ],
        transaction_date__year=year,
        transaction_date__month=month,
        cancel_status=Transaction.CancelStatus.NORMAL,
        expense_purpose=Transaction.ExpensePurpose.BUSINESS,
    )


def get_labor_cost_statements(business, year_month):
    """인건비 지급 명세서"""
    year, month = _parse_year_month(year_month)
    return Payment.objects.filter(
        employee__business=business,
        year=year,
        month=month,
    ).select_related("employee")


def get_deemed_purchase_deductions(business, year_month):
    """의제매입 공제 내역"""
    # TODO: tax 앱 아직 구현 전. Deduction 모델 나오면 실제 조회로 교체.
    return []