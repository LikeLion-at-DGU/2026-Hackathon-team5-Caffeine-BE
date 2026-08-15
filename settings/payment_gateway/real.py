from settings.payment_gateway.base import BasePaymentGateway


class RealPaymentGateway(BasePaymentGateway):
    """실제 PG사(토스페이먼츠/포트원 등) 연동 — PG사 선정 및 가맹점 계약 후 구현."""

    def issue_billing_key(self, payment_token: str) -> dict:
        raise NotImplementedError("실제 PG사 선정 후 구현 예정")

    def charge(self, billing_key: str, amount: int) -> dict:
        raise NotImplementedError("실제 PG사 선정 후 구현 예정")