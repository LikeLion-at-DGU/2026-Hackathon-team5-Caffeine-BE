"""근로자 임금명세서와 프리랜서 지급명세서 PDF를 생성한다.

근로기준법 시행령 제27조의2에 따른 임금명세서 필수 기재사항 반영:
- 근로자 특정 정보(성명), 임금 총액, 임금 구성항목별 금액, 계산방법(근무시간),
  공제 항목별 금액 및 계산방법, 임금지급일

프리랜서는 근로기준법상 근로자가 아니므로 지급명세서 서식을 사용한다.
"""

import io
from datetime import date
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from payroll.services.payment_service import get_payslip_data

# 서버 환경에서도 한글이 깨지지 않도록 폰트를 직접 등록한다.
_FONT_DIR = Path(__file__).resolve().parent.parent / "fonts"
pdfmetrics.registerFont(TTFont("NanumGothic", str(_FONT_DIR / "NanumGothic.ttf")))
pdfmetrics.registerFont(TTFont("NanumGothicBold", str(_FONT_DIR / "NanumGothicBold.ttf")))
FONT_NAME = "NanumGothic"
FONT_NAME_BOLD = "NanumGothicBold"


def _draw_row(c: canvas.Canvas, x: int, y: int, label: str, value: str, label_size=10, value_size=11):
    c.setFont(FONT_NAME, label_size)
    c.drawString(x, y, label)
    c.setFont(FONT_NAME, value_size)
    c.drawRightString(x + 400, y, value)


def _format_won(amount: int) -> str:
    return f"{amount:,}원"


def _draw_payslip_page(c: canvas.Canvas, payment) -> None:
    data = get_payslip_data(payment)
    width, height = A4
    x_margin = 20 * mm
    y = height - 25 * mm

    is_freelancer = data["employment_type"] == "FREELANCER"
    title = "지급명세서 (사업소득)" if is_freelancer else "임금명세서"

    c.setFont(FONT_NAME, 18)
    c.drawCentredString(width / 2, y, title)
    y -= 15 * mm

    c.setFont(FONT_NAME, 11)
    c.drawString(x_margin, y, f"성명: {data['employee_name']}")
    y -= 7 * mm
    c.drawString(x_margin, y, f"사원번호: {data['employee_id']:04d}")
    y -= 7 * mm
    c.drawString(x_margin, y, f"귀속연월: {data['year']}년 {data['month']}월")
    y -= 7 * mm
    c.drawString(x_margin, y, f"지급일: {date.today().isoformat()}")
    y -= 12 * mm

    c.setFont(FONT_NAME, 13)
    c.drawString(x_margin, y, "■ 임금 구성항목" if not is_freelancer else "■ 지급 내역")
    y -= 8 * mm

    _draw_row(c, x_margin, y, f"기본급 (시급 {_format_won(data['hourly_wage'])} × {data['work_hours']}시간)", _format_won(data["gross_pay"]))
    y -= 7 * mm
    c.setFont(FONT_NAME, 11)
    c.drawRightString(x_margin + 400, y, "지급액 합계")
    c.drawRightString(x_margin + 500, y, _format_won(data["gross_pay"]))
    y -= 12 * mm

    c.setFont(FONT_NAME, 13)
    c.drawString(x_margin, y, "■ 공제 내역")
    y -= 8 * mm

    _draw_row(c, x_margin, y, "소득세", _format_won(data["income_tax"]))
    y -= 6 * mm
    _draw_row(c, x_margin, y, "지방소득세", _format_won(data["local_income_tax"]))
    y -= 6 * mm

    if not is_freelancer:
        _draw_row(c, x_margin, y, "국민연금", _format_won(data["national_pension"]))
        y -= 6 * mm
        _draw_row(c, x_margin, y, "건강보험", _format_won(data["health_insurance"]))
        y -= 6 * mm
        _draw_row(c, x_margin, y, "장기요양보험", _format_won(data["long_term_care"]))
        y -= 6 * mm
        _draw_row(c, x_margin, y, "고용보험", _format_won(data["employment_insurance"]))
        y -= 6 * mm

    c.setFont(FONT_NAME, 11)
    c.drawRightString(x_margin + 400, y, "공제액 합계")
    c.drawRightString(x_margin + 500, y, _format_won(data["deductions_total"]))
    y -= 15 * mm

    c.setLineWidth(0.5)
    c.line(x_margin, y, x_margin + 500, y)
    y -= 10 * mm

    c.setFont(FONT_NAME, 14)
    c.drawString(x_margin, y, "실수령액")
    c.drawRightString(x_margin + 500, y, _format_won(data["net_pay"]))


def generate_payslip_pdf(payments: list) -> bytes:
    """직원별 명세서를 페이지로 나누어 하나의 PDF로 반환한다."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    for payment in payments:
        _draw_payslip_page(c, payment)
        c.showPage()

    c.save()
    buffer.seek(0)
    return buffer.read()
