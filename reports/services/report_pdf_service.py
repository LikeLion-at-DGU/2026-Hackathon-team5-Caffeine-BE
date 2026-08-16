import io
from pathlib import Path

from django.apps import apps
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from payroll.models import Employee

from .data_aggregation_service import (
    get_labor_cost_statements,
    get_purchase_evidences,
    get_sales_invoices,
)

# payroll/fonts의 나눔고딕 재사용 - reportlab 기본 폰트는 한글 미지원
_FONT_DIR = Path(apps.get_app_config("payroll").path) / "fonts"
pdfmetrics.registerFont(TTFont("NanumGothic", str(_FONT_DIR / "NanumGothic.ttf")))
FONT_NAME = "NanumGothic"


def generate_report_pdf(business, year_month):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    y = 800

    c.setFont(FONT_NAME, 14)
    c.drawString(50, y, f"{year_month} 세무사 전달용 자료 - {business.business_name}")
    y -= 30
    c.setFont(FONT_NAME, 11)

    c.drawString(50, y, "[매출 세금계산서]")
    y -= 15
    for tx in get_sales_invoices(business, year_month):
        c.drawString(60, y, f"{tx.transaction_date} {tx.merchant_name} {tx.total_amount}원")
        y -= 15
    y -= 10

    c.drawString(50, y, "[매입 증빙]")
    y -= 15
    for tx in get_purchase_evidences(business, year_month):
        c.drawString(60, y, f"{tx.transaction_date} {tx.merchant_name} {tx.total_amount}원")
        y -= 15
    y -= 10

    payments = list(get_labor_cost_statements(business, year_month))
    for emp_type, label in Employee.EMPLOYMENT_TYPE_CHOICES:
        rows = [p for p in payments if p.employee.employment_type == emp_type]
        if not rows:
            continue
        c.drawString(50, y, f"[인건비 - {label}]")
        y -= 15
        for p in rows:
            c.drawString(60, y, f"{p.employee.name} 지급액 {p.gross_pay}원 / 원천징수 {p.withholding_tax}원")
            y -= 15
        y -= 10

    c.showPage()
    c.save()
    return buffer.getvalue()