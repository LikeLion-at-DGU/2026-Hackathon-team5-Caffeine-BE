from settings.payment_gateway.base import BasePaymentGateway


class RealPaymentGateway(BasePaymentGateway):
    """PG사 선정과 가맹점 계약 후 구현할 실제 결제 제공자."""

    def issue_billing_key(self, payment_token: str) -> dict:
        raise NotImplementedError("실제 PG사 선정 후 구현 예정")

    def charge(self, billing_key: str, amount: int) -> dict:
        raise NotImplementedError("실제 PG사 선정 후 구현 예정")
