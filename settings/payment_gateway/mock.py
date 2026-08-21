import base64
import json
import uuid
from datetime import datetime

from settings.payment_gateway.base import BasePaymentGateway


DEFAULT_CARD_COMPANY = "목업카드사"
DEFAULT_CARD_LAST4 = "1234"
CHARGE_FAIL_ERROR_MESSAGE = "카드 한도 초과로 결제에 실패했습니다."


def _decode_token(token: str) -> dict | None:
    """가상 PG SDK가 만든 데모 토큰을 해석한다.

    목업은 카드 표시 정보와 실패 시나리오를 Base64 JSON에 담는다. 자체 형식이 아닌
    토큰은 기존 테스트와의 호환을 위해 기본 성공 시나리오로 처리한다.
    """
    try:
        payload = json.loads(base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        return payload
    except Exception:
        return None


class MockPaymentGateway(BasePaymentGateway):
    """카드 원문 없이 등록과 정기 결제를 재현하는 PG 목업.

    가상 SDK가 전달한 `CHARGE_FAIL` 표시를 빌링키에 보존해 정기 결제 실패를
    재현한다. 카드 등록 거절은 토큰 발급 전 프론트에서 처리한다.
    """

    def issue_billing_key(self, payment_token: str) -> dict:
        payload = _decode_token(payment_token)

        card_company = (payload or {}).get("card_company") or DEFAULT_CARD_COMPANY
        card_last4 = (payload or {}).get("card_last4") or DEFAULT_CARD_LAST4
        charge_should_fail = bool((payload or {}).get("scenario") == "CHARGE_FAIL")

        billing_key_payload = {
            "card_company": card_company,
            "card_last4": card_last4,
            "charge_should_fail": charge_should_fail,
        }
        billing_key = "mock_billing_{}.{}".format(
            uuid.uuid4().hex[:16],
            base64.urlsafe_b64encode(json.dumps(billing_key_payload).encode("utf-8")).decode("utf-8"),
        )

        return {
            "billing_key": billing_key,
            "card_company": card_company,
            "card_last4": card_last4,
        }

    def charge(self, billing_key: str, amount: int) -> dict:
        charge_should_fail = False
        # 빌링키에 보존한 시나리오 정보로 정기 결제 결과를 재현한다.
        if "." in billing_key:
            _, _, encoded_payload = billing_key.partition(".")
            payload = _decode_token(encoded_payload)
            charge_should_fail = bool((payload or {}).get("charge_should_fail"))

        if charge_should_fail:
            return {
                "success": False,
                "transaction_id": None,
                "charged_at": datetime.now().isoformat(),
                "error": CHARGE_FAIL_ERROR_MESSAGE,
            }

        return {
            "success": True,
            "transaction_id": f"mock_txn_{uuid.uuid4().hex[:12]}",
            "charged_at": datetime.now().isoformat(),
        }
