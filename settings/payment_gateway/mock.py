import uuid
from datetime import datetime

from settings.payment_gateway.base import BasePaymentGateway


class MockPaymentGateway(BasePaymentGateway):
    """실제 PG사 연동 전까지 사용하는 Mock. 항상 성공한다고 가정.

    카드번호 원본은 절대 다루지 않음 — payment_token 자체가 이미
    프론트의 PG SDK가 발급한 토큰이라는 전제(실제 연동 시에도 동일한 전제).
    """

    def issue_billing_key(self, payment_token: str) -> dict:
        return {
            "billing_key": f"mock_billing_{uuid.uuid4().hex[:16]}",
            "card_company": "목업카드사",
            "card_last4": "1234",
        }

    def charge(self, billing_key: str, amount: int) -> dict:
        return {
            "success": True,
            "transaction_id": f"mock_txn_{uuid.uuid4().hex[:12]}",
            "charged_at": datetime.now().isoformat(),
        }