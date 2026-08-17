import csv
import io

from payroll.models import Employee

from .data_aggregation_service import (
    get_deemed_purchase_deductions,
    get_labor_cost_statements,
    get_purchase_evidences,
    get_sales_invoices,
)


def generate_report_csv(business, year_month):
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

    deemed_candidates = list(get_deemed_purchase_deductions(business, year_month))
    if deemed_candidates:
        writer.writerow(["[의제매입 검토 후보]"])
        writer.writerow(["일자", "거래처", "면세 원재료 금액", "상태"])
        for review in deemed_candidates:
            tx = review.transaction
            writer.writerow([
                tx.transaction_date,
                tx.merchant_name,
                tx.total_amount,
                "공제율 적용 전 후보",
            ])
        writer.writerow([])

    return buffer.getvalue()
