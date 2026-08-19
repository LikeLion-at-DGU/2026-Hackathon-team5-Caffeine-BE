import base64
import json

from django.test import TestCase

from settings.payment_gateway.mock import MockPaymentGateway


def _encode_token(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


class MockPaymentGatewayTests(TestCase):
    def setUp(self):
        self.gateway = MockPaymentGateway()

    def test_issue_billing_key_with_opaque_token_falls_back_to_defaults(self):
        # 우리 포맷이 아닌 임의 문자열(과거 데모/테스트 토큰 포함)도 항상 성공해야 한다.
        result = self.gateway.issue_billing_key("tok_abc123")

        self.assertTrue(result["billing_key"])
        self.assertEqual(result["card_company"], "목업카드사")
        self.assertEqual(result["card_last4"], "1234")

    def test_issue_billing_key_reflects_frontend_card_info(self):
        token = _encode_token({"card_company": "국민카드(가상)", "card_last4": "5678", "scenario": None})

        result = self.gateway.issue_billing_key(token)

        self.assertEqual(result["card_company"], "국민카드(가상)")
        self.assertEqual(result["card_last4"], "5678")

    def test_charge_succeeds_for_normal_card(self):
        token = _encode_token({"card_company": "국민카드(가상)", "card_last4": "5678", "scenario": None})
        billing_key = self.gateway.issue_billing_key(token)["billing_key"]

        result = self.gateway.charge(billing_key, 19900)

        self.assertTrue(result["success"])
        self.assertTrue(result["transaction_id"])

    def test_charge_fails_for_charge_fail_scenario_card(self):
        token = _encode_token({"card_company": "국민카드(가상)", "card_last4": "0341", "scenario": "CHARGE_FAIL"})
        billing_key = self.gateway.issue_billing_key(token)["billing_key"]

        result = self.gateway.charge(billing_key, 19900)

        self.assertFalse(result["success"])
        self.assertIn("error", result)
