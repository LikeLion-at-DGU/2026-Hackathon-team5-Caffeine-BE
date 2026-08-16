from businesses.models import CodefConnection

from .base import BaseCodefProvider, CodefBusinessAccessError


class RealCodefProvider(BaseCodefProvider):
    """실제 CODEF API 연동 Provider.

    실제 응답을 MockProvider와 동일한 내부 형식으로 변환해 반환한다.
    """

    SOURCE_CONNECTION_TYPES = {
        "CARD_PURCHASE": "CARD",
        "CASH_RECEIPT_PURCHASE": "HOMETAX",
        "CASH_RECEIPT_SALE": "HOMETAX",
        "TAX_INVOICE": "HOMETAX",
        "CREDIT_CARD_SALES_SUMMARY": "HOMETAX",
    }

    def ensure_business_access(self, business, source_type):
        connection_type = self.SOURCE_CONNECTION_TYPES.get(source_type)
        if connection_type is None:
            raise CodefBusinessAccessError(
                f"지원하지 않는 CODEF 거래 소스입니다: {source_type}"
            )
        if not CodefConnection.objects.filter(
            business=business,
            connection_type=connection_type,
            status="CONNECTED",
        ).exists():
            raise CodefBusinessAccessError(
                f"이 사업장에 연결된 {connection_type} CODEF 계정이 없습니다."
            )

    def get_business_status(self, business_number):
        raise NotImplementedError(
            "RealCodefProvider는 아직 구현 전 / CODEF_MODE=mock으로 개발"
        )

    def request_auth(self, business, connection_type):
        raise NotImplementedError

    def retry_auth(self, business, connection):
        raise NotImplementedError

    def get_business_card_purchases(self, business, start_date, end_date):
        raise NotImplementedError("실제 사업용 신용카드 매입 조회는 아직 구현되지 않았습니다.")

    def get_cash_receipt_sales(self, business, start_date, end_date):
        raise NotImplementedError("실제 현금영수증 매출 조회는 아직 구현되지 않았습니다.")

    def get_tax_invoice_purchases(self, business, start_date, end_date):
        raise NotImplementedError("실제 전자세금계산서 매입 조회는 아직 구현되지 않았습니다.")

    def get_tax_invoice_sales(self, business, start_date, end_date):
        raise NotImplementedError("실제 전자세금계산서 매출 조회는 아직 구현되지 않았습니다.")

    def get_credit_card_sales_summary(self, business, start_date, end_date):
        raise NotImplementedError("실제 신용카드 월별 매출자료 조회는 아직 구현되지 않았습니다.")
