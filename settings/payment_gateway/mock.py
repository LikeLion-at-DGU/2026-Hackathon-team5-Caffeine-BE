import base64
import json
import uuid
from datetime import datetime

from settings.payment_gateway.base import BasePaymentGateway


DEFAULT_CARD_COMPANY = "목업카드사"
DEFAULT_CARD_LAST4 = "1234"
CHARGE_FAIL_ERROR_MESSAGE = "카드 한도 초과로 결제에 실패했습니다."


def _decode_token(token: str) -> dict | None:
    """프론트의 가상 PG SDK(mockPaymentGateway.js)가 만든 토큰을 디코딩한다.

    실제 PG 토큰은 우리 쪽에서 해석할 수 없는 완전한 불투명(opaque) 값이지만,
    Mock 구현체는 데모 시나리오(카드사/마지막4자리/실패 재현)를 위해 자체 포맷으로
    base64 JSON을 인코딩해서 보낸다. 우리 포맷이 아닌 임의의 문자열(과거 테스트가
    보내는 "tok_abc123" 같은 값 포함)이 오면 None을 반환해서 항상 성공 처리로
    폴백하게 한다 — 실제 PG의 "알 수 없는 토큰이면 그냥 거부"와는 다르지만,
    Mock 자체는 "항상 성공한다고 가정"하는 게 원래 설계이므로 하위호환을 유지한다.
    """
    try:
        payload = json.loads(base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        return payload
    except Exception:
        return None


class MockPaymentGateway(BasePaymentGateway):
    """실제 PG사 연동 전까지 사용하는 Mock.

    카드번호 원본은 절대 다루지 않음 — payment_token 자체가 이미
    프론트의(가상) PG SDK가 발급한 토큰이라는 전제(실제 연동 시에도 동일한 전제).

    프론트(mockPaymentGateway.js)가 카드번호 마지막 4자리를 기준으로 테스트
    시나리오 카드를 흉내내는데, 그중 "정기결제 실패" 시나리오(마지막 4자리 0341)는
    토큰에 scenario="CHARGE_FAIL"로 표시돼서 넘어온다. 이 클래스는 그 표시를
    billing_key에도 그대로 실어 보내서, 나중에 charge()가 호출될 때(정기결제 cron)
    실패를 재현할 수 있게 한다.

    "카드 등록 자체가 거절되는" 시나리오(마지막 4자리 0002)는 프론트에서 아예
    payment_token을 만들지 않고 등록 단계에서 바로 거부하므로, 여기까지 도달하지
    않는다 — 실제 PG SDK도 카드 승인 자체가 안 되면 토큰을 안 주는 경우가 많다.
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
        # billing_key 형식: "mock_billing_<random>.<base64 payload>"
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
