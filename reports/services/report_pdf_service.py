import io
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.apps import apps
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from payroll.models import Employee
from transactions.models import Transaction

from .data_aggregation_service import (
    get_deemed_purchase_deductions,
    get_labor_cost_statements,
    get_purchase_evidences,
    get_sales_invoices,
)

# 서버 환경에서도 한글이 깨지지 않도록 급여 앱의 폰트를 재사용한다.
_FONT_DIR = Path(apps.get_app_config("payroll").path) / "fonts"
pdfmetrics.registerFont(TTFont("NanumGothic", str(_FONT_DIR / "NanumGothic.ttf")))
FONT_NAME = "NanumGothic"


class NumberedCanvas(object):
    """두 번 렌더링해 각 페이지에 전체 페이지 수를 표시한다."""

    def __init__(self, *args, **kwargs):
        pass


def _fmt_amt(value):
    """금액을 천 단위 구분이 있는 원화 문자열로 변환한다."""
    if value is None:
        return "0원"
    try:
        val = int(Decimal(str(value)))
        return f"{val:,}원"
    except Exception:
        return f"{value}원"


def _fmt_date(d):
    """날짜를 `YYYY-MM-DD` 형식으로 통일한다."""
    if isinstance(d, date):
        return d.strftime("%Y-%m-%d")
    return str(d) if d else ""


def _get_source_label(source_type):
    labels = {
        Transaction.SourceType.CARD_PURCHASE: "신용카드",
        Transaction.SourceType.CASH_RECEIPT_PURCHASE: "현금영수증",
        Transaction.SourceType.CASH_RECEIPT_SALE: "현금영수증",
        Transaction.SourceType.TAX_INVOICE: "세금계산서",
    }
    return labels.get(source_type, str(source_type))


def generate_report_pdf(business, year_month):
    """세무사에게 전달할 월별 기장자료 PDF를 생성한다."""
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()

    # 문서 전체에서 같은 글꼴과 간격을 사용하도록 스타일을 공유한다.
    title_style = ParagraphStyle(
        "DocTitle",
        fontName=FONT_NAME,
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1A202C"),
        alignment=0,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        fontName=FONT_NAME,
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#718096"),
        alignment=0,
    )
    section_title_style = ParagraphStyle(
        "SectionTitle",
        fontName=FONT_NAME,
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#2D3748"),
        spaceAfter=6,
    )
    cell_style = ParagraphStyle(
        "CellText",
        fontName=FONT_NAME,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#2D3748"),
    )
    cell_header_style = ParagraphStyle(
        "CellHeader",
        fontName=FONT_NAME,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#FFFFFF"),
        alignment=1,
    )
    cell_right_style = ParagraphStyle(
        "CellRight",
        fontName=FONT_NAME,
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#2D3748"),
        alignment=2,
    )
    cell_right_bold = ParagraphStyle(
        "CellRightBold",
        fontName=FONT_NAME,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1A202C"),
        alignment=2,
    )

    elements = []

    # 1. 문서 헤더 및 사업장 기본 정보
    y_str, m_str = year_month.split("-")
    period_label = f"{y_str}년 {int(m_str)}월"
    today_str = timezone.localdate().strftime("%Y년 %m월 %d일")

    elements.append(Paragraph(f"월별 세무 기장자료 ({period_label})", title_style))
    elements.append(Paragraph(f"카페비서 자동 집계 보고서 | 발급일자: {today_str}", subtitle_style))
    elements.append(Spacer(1, 10))

    # 사업장 기본정보 카드 테이블
    info_data = [
        [
            Paragraph("<b>사업장명</b>", cell_style),
            Paragraph(business.business_name, cell_style),
            Paragraph("<b>대표자명</b>", cell_style),
            Paragraph(business.representative_name or "-", cell_style),
        ],
        [
            Paragraph("<b>사업자등록번호</b>", cell_style),
            Paragraph(business.business_number or "-", cell_style),
            Paragraph("<b>과세유형</b>", cell_style),
            Paragraph("일반과세자" if business.tax_type == "GENERAL" else "간이과세자", cell_style),
        ],
    ]
    info_table = Table(info_data, colWidths=[30 * mm, 60 * mm, 30 * mm, 60 * mm])
    info_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F7FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(info_table)
    elements.append(Spacer(1, 12))

    # 2. 월간 요약 카드 영역
    sales_invoices = list(get_sales_invoices(business, year_month))
    purchase_evidences = list(get_purchase_evidences(business, year_month))
    labor_payments = list(get_labor_cost_statements(business, year_month))
    deemed_candidates = list(get_deemed_purchase_deductions(business, year_month))

    total_sales = sum(tx.total_amount for tx in sales_invoices)
    total_purchases = sum(tx.total_amount for tx in purchase_evidences)
    total_labor = sum(p.gross_pay for p in labor_payments)
    total_withholding = sum(p.withholding_tax for p in labor_payments)

    summary_data = [
        [
            Paragraph("<b>총 매출 (세금계산서)</b>", cell_header_style),
            Paragraph("<b>총 매입 증빙 합계</b>", cell_header_style),
            Paragraph("<b>인건비 지급 총액</b>", cell_header_style),
            Paragraph("<b>원천징수세액 합계</b>", cell_header_style),
        ],
        [
            Paragraph(f"<b>{_fmt_amt(total_sales)}</b>", cell_right_bold),
            Paragraph(f"<b>{_fmt_amt(total_purchases)}</b>", cell_right_bold),
            Paragraph(f"<b>{_fmt_amt(total_labor)}</b>", cell_right_bold),
            Paragraph(f"<b>{_fmt_amt(total_withholding)}</b>", cell_right_bold),
        ],
    ]
    summary_table = Table(summary_data, colWidths=[45 * mm, 45 * mm, 45 * mm, 45 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2B6CB0")),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#EBF8FF")),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#2B6CB0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BEE3F8")),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 15))

    # 3. 매출 내역 (표)
    elements.append(Paragraph("1. 매출 세금계산서 내역", section_title_style))
    sales_headers = ["거래일자", "거래처명", "구분", "공급가액", "부가세", "합계금액"]
    sales_rows = [
        [Paragraph(f"<b>{h}</b>", cell_header_style) for h in sales_headers]
    ]
    for tx in sales_invoices:
        sales_rows.append(
            [
                Paragraph(_fmt_date(tx.transaction_date), cell_style),
                Paragraph(tx.merchant_name or "-", cell_style),
                Paragraph(_get_source_label(tx.source_type), cell_style),
                Paragraph(_fmt_amt(tx.supply_amount), cell_right_style),
                Paragraph(_fmt_amt(tx.vat_amount), cell_right_style),
                Paragraph(_fmt_amt(tx.total_amount), cell_right_style),
            ]
        )
    # 매출 합계 행
    sales_supply_tot = sum(tx.supply_amount for tx in sales_invoices)
    sales_vat_tot = sum(tx.vat_amount for tx in sales_invoices)
    sales_rows.append(
        [
            Paragraph("<b>매출 합계</b>", cell_style),
            Paragraph(f"<b>총 {len(sales_invoices)}건</b>", cell_style),
            Paragraph("", cell_style),
            Paragraph(f"<b>{_fmt_amt(sales_supply_tot)}</b>", cell_right_bold),
            Paragraph(f"<b>{_fmt_amt(sales_vat_tot)}</b>", cell_right_bold),
            Paragraph(f"<b>{_fmt_amt(total_sales)}</b>", cell_right_bold),
        ]
    )
    sales_table = Table(
        sales_rows,
        colWidths=[25 * mm, 45 * mm, 25 * mm, 28 * mm, 25 * mm, 32 * mm],
        repeatRows=1,
    )
    sales_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4A5568")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EDF2F7")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(sales_table)
    elements.append(Spacer(1, 15))

    # 4. 매입 증빙 내역 (표)
    elements.append(Paragraph("2. 매입 증빙 내역 (세금계산서·신용카드·현금영수증)", section_title_style))
    purchase_headers = ["거래일자", "거래처명", "증빙 구분", "공급가액", "부가세", "합계금액"]
    purchase_rows = [
        [Paragraph(f"<b>{h}</b>", cell_header_style) for h in purchase_headers]
    ]
    for tx in purchase_evidences:
        purchase_rows.append(
            [
                Paragraph(_fmt_date(tx.transaction_date), cell_style),
                Paragraph(tx.merchant_name or "-", cell_style),
                Paragraph(_get_source_label(tx.source_type), cell_style),
                Paragraph(_fmt_amt(tx.supply_amount), cell_right_style),
                Paragraph(_fmt_amt(tx.vat_amount), cell_right_style),
                Paragraph(_fmt_amt(tx.total_amount), cell_right_style),
            ]
        )
    # 매입 합계 행
    purchase_supply_tot = sum(tx.supply_amount for tx in purchase_evidences)
    purchase_vat_tot = sum(tx.vat_amount for tx in purchase_evidences)
    purchase_rows.append(
        [
            Paragraph("<b>매입 합계</b>", cell_style),
            Paragraph(f"<b>총 {len(purchase_evidences)}건</b>", cell_style),
            Paragraph("", cell_style),
            Paragraph(f"<b>{_fmt_amt(purchase_supply_tot)}</b>", cell_right_bold),
            Paragraph(f"<b>{_fmt_amt(purchase_vat_tot)}</b>", cell_right_bold),
            Paragraph(f"<b>{_fmt_amt(total_purchases)}</b>", cell_right_bold),
        ]
    )
    purchase_table = Table(
        purchase_rows,
        colWidths=[25 * mm, 45 * mm, 25 * mm, 28 * mm, 25 * mm, 32 * mm],
        repeatRows=1,
    )
    purchase_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4A5568")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EDF2F7")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    elements.append(purchase_table)
    elements.append(Spacer(1, 15))

    # 5. 인건비 내역 (유형별 구분 표)
    elements.append(Paragraph("3. 인건비 지급 및 원천징수 명세", section_title_style))
    for emp_type, label in Employee.EMPLOYMENT_TYPE_CHOICES:
        rows = [p for p in labor_payments if p.employee.employment_type == emp_type]
        if not rows:
            continue

        elements.append(Paragraph(f"<b>▪ {label}</b>", subtitle_style))
        elements.append(Spacer(1, 4))

        labor_headers = ["성명", "근무시간", "지급금액(과세)", "원천징수세액", "차인지급액(실지급액)"]
        labor_table_rows = [
            [Paragraph(f"<b>{h}</b>", cell_header_style) for h in labor_headers]
        ]
        sub_gross = sum(p.gross_pay for p in rows)
        sub_tax = sum(p.withholding_tax for p in rows)
        sub_net = sub_gross - sub_tax

        for p in rows:
            net_pay = p.gross_pay - p.withholding_tax
            labor_table_rows.append(
                [
                    Paragraph(p.employee.name, cell_style),
                    Paragraph(f"{p.work_hours}시간" if p.work_hours else "-", cell_style),
                    Paragraph(_fmt_amt(p.gross_pay), cell_right_style),
                    Paragraph(_fmt_amt(p.withholding_tax), cell_right_style),
                    Paragraph(_fmt_amt(net_pay), cell_right_style),
                ]
            )
        # 소계 행
        labor_table_rows.append(
            [
                Paragraph("<b>소계</b>", cell_style),
                Paragraph(f"<b>{len(rows)}명</b>", cell_style),
                Paragraph(f"<b>{_fmt_amt(sub_gross)}</b>", cell_right_bold),
                Paragraph(f"<b>{_fmt_amt(sub_tax)}</b>", cell_right_bold),
                Paragraph(f"<b>{_fmt_amt(sub_net)}</b>", cell_right_bold),
            ]
        )
        sub_table = Table(
            labor_table_rows,
            colWidths=[35 * mm, 30 * mm, 38 * mm, 38 * mm, 39 * mm],
            repeatRows=1,
        )
        sub_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4A5568")),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#EDF2F7")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E0")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        elements.append(sub_table)
        elements.append(Spacer(1, 8))

    # 6. 의제매입 검토 후보 내역 (면세 우유/원재료)
    if deemed_candidates:
        elements.append(Spacer(1, 6))
        elements.append(Paragraph("4. 면세 농·축산물 의제매입세액 공제 검토 후보", section_title_style))
        deemed_headers = ["거래일자", "거래처명", "지출 품목", "공급가액", "비고 (공제율 적용 전)"]
        deemed_rows = [
            [Paragraph(f"<b>{h}</b>", cell_header_style) for h in deemed_headers]
        ]
        deemed_tot = sum(r.transaction.total_amount for r in deemed_candidates)
        for r in deemed_candidates:
            tx = r.transaction
            deemed_rows.append(
                [
                    Paragraph(_fmt_date(tx.transaction_date), cell_style),
                    Paragraph(tx.merchant_name or "-", cell_style),
                    Paragraph(_get_source_label(tx.source_type), cell_style),
                    Paragraph(_fmt_amt(tx.total_amount), cell_right_style),
                    Paragraph("면세 매입 (의제매입 9/109 대상)", cell_style),
                ]
            )
        deemed_rows.append(
            [
                Paragraph("<b>의제매입 후보 합계</b>", cell_style),
                Paragraph(f"<b>총 {len(deemed_candidates)}건</b>", cell_style),
                Paragraph("", cell_style),
                Paragraph(f"<b>{_fmt_amt(deemed_tot)}</b>", cell_right_bold),
                Paragraph("세무 신고 시 공제 산출", cell_style),
            ]
        )
        deemed_table = Table(
            deemed_rows,
            colWidths=[25 * mm, 45 * mm, 30 * mm, 35 * mm, 45 * mm],
            repeatRows=1,
        )
        deemed_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C7A7B")),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E6FFFA")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B2F5EA")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        elements.append(deemed_table)

    doc.build(elements)
    return buffer.getvalue()
