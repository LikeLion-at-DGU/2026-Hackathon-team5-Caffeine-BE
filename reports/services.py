import csv
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from transactions.models import Transaction
from payroll.models import Employee, Payment


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
        # 세무사에게 넘길 자료라 개인 지출은 제외 - 다 포함하려면 이 줄 삭제
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


def generate_csv(business, year_month):
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    writer.writerow(["[매출 세금계산서]"])
    writer.writerow(["일자", "거래처", "금액"])
    for tx in get_sales_invoices(business, year_month):
        writer.writerow([tx.transaction_date, tx.merchant_name, tx.total_amount])
    writer.writerow([])

    writer.writerow(["[매입 증빙]"])
    writer.writerow(["일자", "거래처", "금액"])
    for tx in get_purchase_evidences(business, year_month):
        writer.writerow([tx.transaction_date, tx.merchant_name, tx.total_amount])
    writer.writerow([])

    # 4대보험/3.3% 프리랜서는 신고 방식이 달라서 employment_type별로 섹션을 나눔
    payments = list(get_labor_cost_statements(business, year_month))
    for emp_type, label in Employee.EMPLOYMENT_TYPE_CHOICES:
        rows = [p for p in payments if p.employee.employment_type == emp_type]
        if not rows:
            continue
        writer.writerow([f"[인건비 - {label}]"])
        writer.writerow(["이름", "지급액", "원천징수세액"])
        for p in rows:
            writer.writerow([p.employee.name, p.gross_pay, p.withholding_tax])
        writer.writerow([])

    for d in get_deemed_purchase_deductions(business, year_month):  # 지금은 항상 빈 리스트
        pass

    return buffer.getvalue()


def generate_pdf(business, year_month):
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    p.drawString(50, y, f"{year_month} 세무사 전달용 자료 - {business.business_name}")
    y -= 30

    p.drawString(50, y, "[매출 세금계산서]")
    y -= 15
    for tx in get_sales_invoices(business, year_month):
        p.drawString(60, y, f"{tx.transaction_date} {tx.merchant_name} {tx.total_amount}원")
        y -= 15
    y -= 10

    p.drawString(50, y, "[매입 증빙]")
    y -= 15
    for tx in get_purchase_evidences(business, year_month):
        p.drawString(60, y, f"{tx.transaction_date} {tx.merchant_name} {tx.total_amount}원")
        y -= 15
    y -= 10

    payments = list(get_labor_cost_statements(business, year_month))
    for emp_type, label in Employee.EMPLOYMENT_TYPE_CHOICES:
        rows = [pay for pay in payments if pay.employee.employment_type == emp_type]
        if not rows:
            continue
        p.drawString(50, y, f"[인건비 - {label}]")
        y -= 15
        for pay in rows:
            p.drawString(60, y, f"{pay.employee.name} 지급액 {pay.gross_pay}원 / 원천징수 {pay.withholding_tax}원")
            y -= 15
        y -= 10

    p.showPage()
    p.save()
    return buffer.getvalue()