from transactions.models import Transaction
from payroll.models import Payment
from tax.models import DeductionReview
from tax.services.periods import month_range
from tax.services.querysets import effective_purchase_transactions, effective_transactions


def _parse_year_month(year_month):
    year, month = year_month.split("-")
    return int(year), int(month)


def get_sales_invoices(business, year_month):
    """매출 세금계산서 목록"""
    year, month = _parse_year_month(year_month)
    start_date, end_date = month_range(year, month)
    return effective_transactions(
        business=business,
        start_date=start_date,
        end_date=end_date,
    ).filter(
        transaction_type=Transaction.TransactionType.SALE,
        source_type=Transaction.SourceType.TAX_INVOICE,
    )


def get_purchase_evidences(business, year_month):
    """매입 증빙 서류 (카드/현금영수증/전자세금계산서)"""
    year, month = _parse_year_month(year_month)
    start_date, end_date = month_range(year, month)
    return effective_purchase_transactions(
        business=business,
        start_date=start_date,
        end_date=end_date,
    ).filter(
        source_type__in=[
            Transaction.SourceType.CARD_PURCHASE,
            Transaction.SourceType.CASH_RECEIPT_PURCHASE,
            Transaction.SourceType.TAX_INVOICE,
        ],
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
    """현재 규칙상 의제매입 검토 후보인 면세 원재료 목록."""
    year, month = _parse_year_month(year_month)
    start_date, end_date = month_range(year, month)
    purchases = effective_purchase_transactions(
        business=business,
        start_date=start_date,
        end_date=end_date,
    ).filter(
        expense_purpose=Transaction.ExpensePurpose.BUSINESS,
        vat_amount=0,
        category=Transaction.Category.RAW_MATERIAL,
    )
    return DeductionReview.objects.select_related("transaction").filter(
        transaction__in=purchases,
        confirmed_status=DeductionReview.ConfirmedStatus.DEDUCTIBLE,
    )
