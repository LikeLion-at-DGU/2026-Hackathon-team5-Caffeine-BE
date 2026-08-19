"""RealCodefProvider.get_credit_card_sales_summary()의 payload 조립 검증.

CODEF "신용카드 매출자료 조회" 공식 문서(organization="0006",
/v1/kr/public/nt/tax-payment/credit-card-sales-data-list) 기준으로 payload가
올바르게 조립되는지 확인한다. 실제 CODEF 서버는 호출하지 않고 CodefClient를
Mock으로 대체한다.

이 상품은 카카오 간편인증이 아니라 공동인증서(certFile/certPassword/
certType[/keyFile]) 기반이라 다른 세 Real 메서드와 검증 포인트가 다르다:
- year/분기 변환이 맞는지 (date 객체와 YYYYMMDD 문자열 문자열 둘 다)
- certPassword가 평문이 아니라 RSA 암호화된 값으로 나가는지
- certFile/keyFile이 파일 "경로"에서 읽혀 Base64로 인코딩되는지
- keyFile이 certType에 따라 있거나 없거나 하는지
"""

import base64
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock
from datetime import date

from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA
from django.test import SimpleTestCase, override_settings

from businesses.models import Business
from integrations.codef.base import CodefBusinessAccessError
from integrations.codef.real import RealCodefProvider


def _generate_test_keypair():
    """CODEF가 실제로 주는 키가 아니라, 우리 암호화 결과를 대응하는 개인키로
    복호화할 수 있는지만 확인하는 용도의 테스트 전용 RSA 키쌍이다.
    (test_client_encryption.py와 동일한 방식)"""
    key = RSA.generate(2048)
    public_key_b64 = base64.b64encode(
        key.publickey().export_key(format="DER")
    ).decode("utf-8")
    return key, public_key_b64


class GetCreditCardSalesSummaryTests(SimpleTestCase):
    def setUp(self):
        self.private_key, self.public_key_b64 = _generate_test_keypair()

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp_dir.cleanup)

        cert_path = Path(self.tmp_dir.name) / "signCert.der"
        key_path = Path(self.tmp_dir.name) / "signPri.key"
        cert_path.write_bytes(b"FAKE DER CERT BYTES - NOT A REAL CERTIFICATE")
        key_path.write_bytes(b"FAKE KEY BYTES - NOT A REAL KEY")
        self.cert_path = str(cert_path)
        self.key_path = str(key_path)

        self.business = Business(business_number="1234567890")

        self._env_patcher = self._patch_env(
            CODEF_PROBE_CERT_FILE=self.cert_path,
            CODEF_PROBE_KEY_FILE=self.key_path,
            CODEF_PROBE_CERT_PASSWORD="testpw123",
            CODEF_PROBE_CERT_TYPE="1",
            CODEF_PROBE_DEPT_USER_ID="",
            CODEF_PROBE_DEPT_USER_PASS="",
            CODEF_PROBE_CARD_SALES_LOGIN_IDENTITY="",
            CODEF_PROBE_MANAGE_NO="",
            CODEF_PROBE_MANAGE_PASS="",
        )

        self._settings_override = override_settings(
            CODEF_PUBLIC_KEY=self.public_key_b64
        )
        self._settings_override.enable()
        self.addCleanup(self._settings_override.disable)

    def _patch_env(self, **values):
        from unittest.mock import patch

        patcher = patch.dict(os.environ, values, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        return patcher

    def _decrypt(self, ciphertext_b64):
        cipher = PKCS1_v1_5.new(self.private_key)
        sentinel = object()
        return cipher.decrypt(
            base64.b64decode(ciphertext_b64), sentinel
        ).decode("utf-8")

    # --------------------------------------------------
    # organization / endpoint
    # --------------------------------------------------

    def test_request_uses_official_organization_and_endpoint(self):
        client = Mock()
        client.post.return_value = {"result": {"code": "CF-00000"}, "data": {}}
        provider = RealCodefProvider(client=client)

        provider.get_credit_card_sales_summary(
            self.business, "20260801", "20260818"
        )

        path, _ = client.post.call_args[0]
        self.assertEqual(
            path,
            "/v1/kr/public/nt/tax-payment/credit-card-sales-data-list",
        )

    # --------------------------------------------------
    # year / 분기 변환
    # --------------------------------------------------

    def test_yyyymmdd_strings_convert_to_year_and_quarter(self):
        client = Mock()
        client.post.return_value = {"result": {"code": "CF-00000"}, "data": {}}
        provider = RealCodefProvider(client=client)

        # 2026년 8월 -> 3분기
        provider.get_credit_card_sales_summary(
            self.business, "20260801", "20260818"
        )

        _, payload = client.post.call_args[0]
        self.assertEqual(payload["year"], "2026")
        self.assertEqual(payload["startDate"], "3")
        self.assertEqual(payload["endDate"], "3")

    def test_date_objects_convert_to_year_and_quarter(self):
        client = Mock()
        client.post.return_value = {"result": {"code": "CF-00000"}, "data": {}}
        provider = RealCodefProvider(client=client)

        provider.get_credit_card_sales_summary(
            self.business, date(2026, 4, 15), date(2026, 9, 20)
        )

        _, payload = client.post.call_args[0]
        self.assertEqual(payload["year"], "2026")
        self.assertEqual(payload["startDate"], "2")  # 4월 -> 2분기
        self.assertEqual(payload["endDate"], "3")  # 9월 -> 3분기

    def test_cross_year_range_raises_error(self):
        provider = RealCodefProvider(client=Mock())

        with self.assertRaises(CodefBusinessAccessError):
            provider.get_credit_card_sales_summary(
                self.business,
                date(2025, 12, 1),
                date(2026, 1, 1),
            )

    def test_reversed_quarter_range_raises_error(self):
        provider = RealCodefProvider(client=Mock())

        with self.assertRaises(CodefBusinessAccessError):
            provider.get_credit_card_sales_summary(
                self.business,
                date(2026, 9, 1),
                date(2026, 4, 1),
            )

    # --------------------------------------------------
    # 공동인증서 - certPassword RSA 암호화
    # --------------------------------------------------

    def test_cert_password_is_encrypted_not_sent_as_plaintext(self):
        client = Mock()
        client.post.return_value = {"result": {"code": "CF-00000"}, "data": {}}
        provider = RealCodefProvider(client=client)

        provider.get_credit_card_sales_summary(
            self.business, "20260801", "20260818"
        )

        _, payload = client.post.call_args[0]
        self.assertNotEqual(payload["certPassword"], "testpw123")
        # 실제 CODEF가 해독 가능한 형태인지, 우리가 만든 개인키로 직접 확인
        self.assertEqual(self._decrypt(payload["certPassword"]), "testpw123")

    # --------------------------------------------------
    # 공동인증서 - certFile / keyFile 파일 경로 처리
    # --------------------------------------------------

    def test_cert_file_is_read_from_path_and_base64_encoded(self):
        client = Mock()
        client.post.return_value = {"result": {"code": "CF-00000"}, "data": {}}
        provider = RealCodefProvider(client=client)

        provider.get_credit_card_sales_summary(
            self.business, "20260801", "20260818"
        )

        _, payload = client.post.call_args[0]
        decoded = base64.b64decode(payload["certFile"])
        self.assertEqual(decoded, b"FAKE DER CERT BYTES - NOT A REAL CERTIFICATE")

    def test_key_file_included_when_cert_type_is_1(self):
        client = Mock()
        client.post.return_value = {"result": {"code": "CF-00000"}, "data": {}}
        provider = RealCodefProvider(client=client)

        provider.get_credit_card_sales_summary(
            self.business, "20260801", "20260818"
        )

        _, payload = client.post.call_args[0]
        self.assertIn("keyFile", payload)
        self.assertEqual(
            base64.b64decode(payload["keyFile"]),
            b"FAKE KEY BYTES - NOT A REAL KEY",
        )

    def test_key_file_omitted_when_cert_type_is_pfx(self):
        self._patch_env(CODEF_PROBE_CERT_TYPE="pfx")

        client = Mock()
        client.post.return_value = {"result": {"code": "CF-00000"}, "data": {}}
        provider = RealCodefProvider(client=client)

        provider.get_credit_card_sales_summary(
            self.business, "20260801", "20260818"
        )

        _, payload = client.post.call_args[0]
        self.assertNotIn("keyFile", payload)
        self.assertEqual(payload["certType"], "pfx")

    def test_invalid_cert_type_raises_error(self):
        self._patch_env(CODEF_PROBE_CERT_TYPE="2")
        provider = RealCodefProvider(client=Mock())

        with self.assertRaises(CodefBusinessAccessError):
            provider.get_credit_card_sales_summary(
                self.business, "20260801", "20260818"
            )

    def test_missing_cert_password_raises_error(self):
        self._patch_env(CODEF_PROBE_CERT_PASSWORD="")
        provider = RealCodefProvider(client=Mock())

        with self.assertRaises(CodefBusinessAccessError):
            provider.get_credit_card_sales_summary(
                self.business, "20260801", "20260818"
            )

    def test_missing_cert_file_env_raises_error(self):
        self._patch_env(CODEF_PROBE_CERT_FILE="")
        provider = RealCodefProvider(client=Mock())

        with self.assertRaises(CodefBusinessAccessError):
            provider.get_credit_card_sales_summary(
                self.business, "20260801", "20260818"
            )

    def test_cert_file_path_not_found_raises_error_not_generic_crash(self):
        self._patch_env(
            CODEF_PROBE_CERT_FILE=str(
                Path(self.tmp_dir.name) / "does_not_exist.der"
            )
        )
        provider = RealCodefProvider(client=Mock())

        with self.assertRaises(CodefBusinessAccessError):
            provider.get_credit_card_sales_summary(
                self.business, "20260801", "20260818"
            )

    # --------------------------------------------------
    # 선택 입력값
    # --------------------------------------------------

    def test_optional_fields_omitted_when_not_set(self):
        client = Mock()
        client.post.return_value = {"result": {"code": "CF-00000"}, "data": {}}
        provider = RealCodefProvider(client=client)

        provider.get_credit_card_sales_summary(
            self.business, "20260801", "20260818"
        )

        _, payload = client.post.call_args[0]
        for field_name in (
            "deptUserId",
            "deptUserPass",
            "loginIdentity",
            "manageNo",
            "managePass",
        ):
            self.assertNotIn(field_name, payload)

    def test_optional_fields_included_when_set(self):
        self._patch_env(
            CODEF_PROBE_CARD_SALES_LOGIN_IDENTITY="9001011",
            CODEF_PROBE_MANAGE_NO="TAXAGENT01",
            CODEF_PROBE_MANAGE_PASS="agentpw",
        )

        client = Mock()
        client.post.return_value = {"result": {"code": "CF-00000"}, "data": {}}
        provider = RealCodefProvider(client=client)

        provider.get_credit_card_sales_summary(
            self.business, "20260801", "20260818"
        )

        _, payload = client.post.call_args[0]
        self.assertEqual(payload["loginIdentity"], "9001011")
        self.assertEqual(payload["manageNo"], "TAXAGENT01")
        self.assertEqual(payload["managePass"], "agentpw")

    def test_login_identity_env_var_is_distinct_from_other_products(self):
        # 이 상품의 loginIdentity(7자리 주민번호 앞자리)는 다른 홈택스
        # 간편인증 상품들의 loginIdentity(생년월일 8자리, CODEF_PROBE_
        # LOGIN_IDENTITY)와 의미가 달라 별도 환경변수를 쓴다. 두 env var가
        # 서로 안 섞이는지 확인한다.
        self._patch_env(
            CODEF_PROBE_LOGIN_IDENTITY="19900101",  # 다른 상품 전용, 8자리
            CODEF_PROBE_CARD_SALES_LOGIN_IDENTITY="",  # 이 상품 것만 비움
        )

        client = Mock()
        client.post.return_value = {"result": {"code": "CF-00000"}, "data": {}}
        provider = RealCodefProvider(client=client)

        provider.get_credit_card_sales_summary(
            self.business, "20260801", "20260818"
        )

        _, payload = client.post.call_args[0]
        self.assertNotIn("loginIdentity", payload)