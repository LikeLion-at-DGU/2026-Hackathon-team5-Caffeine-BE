from .base import BaseCodefProvider


class RealCodefProvider(BaseCodefProvider):
    """실제 CODEF API 연동 Provider.

    실제 응답을 MockProvider와 동일한 내부 형식으로 변환해 반환한다.
    """

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
