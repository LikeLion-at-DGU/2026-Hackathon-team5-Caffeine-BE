"""세무사 전달용 클린데이터 내보내기.

원칙: analytics는 자체 PDF/엑셀 생성 로직을 만들지 않는다. payroll이 이미
같은 데이터(급여명세서, 4대보험)로 PDF/엑셀을 만드는 기능을 갖고 있으므로,
그걸 그대로 호출해서 재사용한다 — 생성 로직을 중복 구현하면 나중에 서식이나
계산이 어긋날 위험이 있다.

TODO: transactions/tax 앱이 준비되면 매출·매입 세금계산서, 부가세 추이
그래프도 이 패키지에 포함해야 함 (지금은 인건비 부분만 포함).
"""

from analytics.exceptions import MonthlyCloseRequired
from analytics.services.monthly_close_service import is_month_closed
from payroll.services.payment_service import list_payments
from payroll.services.payslip_pdf_service import generate_payslip_pdf
from payroll.services.payslip_xlsx_service import generate_payslip_xlsx


def build_export(business_id: int, year: int, month: int, export_format: str) -> bytes:
    if not is_month_closed(business_id, year, month):
        raise MonthlyCloseRequired()

    payments = list(list_payments(business_id, year=year, month=month))

    if export_format == "xlsx":
        return generate_payslip_xlsx(payments, year, month)

    return generate_payslip_pdf(payments)