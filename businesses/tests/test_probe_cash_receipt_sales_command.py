"""probe_cash_receipt_sales 명령 검증.

이 명령은 실험/검증 전용이라 CODEF로 실제 네트워크 요청을 보내면 안 되므로,
CodefClient.post를 항상 Mock으로 대체해 차단한다.

사용자 이름·전화번호·식별값은 더 이상 CLI 인자로 받지 않는다(셸 history에
남기 때문) — .env 값 또는 실행 중 입력으로만 받으므로, 여기서는
os.environ을 patch.dict로 채워 넣거나 input()/getpass.getpass()를 Mock으로
대체해 검증한다.
"""

import base64
import io
import json
import os
from unittest.mock import patch

from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from businesses.models import Business

_ENV_MODULE = "businesses.management.commands.probe_cash_receipt_sales"

# 암호화 관련 테스트에서 재사용할 고정 테스트 키쌍. 매 테스트마다 새로 생성할
# 필요 없어 모듈 로드 시 한 번만 만든다 — CODEF가 실제로 주는 키가 아니라,
# encrypt_with_public_key()가 만든 값을 대응하는 개인키로 복호화할 수 있는지
# 확인하는 용도다.
_TEST_PRIVATE_KEY = RSA.generate(2048)
_TEST_PUBLIC_KEY_B64 = base64.b64encode(
    _TEST_PRIVATE_KEY.publickey().export_key(format="DER")
).decode("utf-8")


def _decrypt_with_test_private_key(ciphertext_b64):
    cipher = PKCS1_v1_5.new(_TEST_PRIVATE_KEY)
    sentinel = object()
    return cipher.decrypt(base64.b64decode(ciphertext_b64), sentinel).decode("utf-8")


def _run_command(**options):
    out = io.StringIO()
    call_command("probe_cash_receipt_sales", stdout=out, **options)
    return out.getvalue()


class ProbeCashReceiptSalesCommandTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            business_name="카페비서 데모카페",
            business_number="1234567890",
        )
        self.base_options = {
            "business_id": self.business.id,
            "start_date": "20260801",
            "end_date": "20260803",
            "organization": "TEST_ORG",
            "path": "/v1/kr/public/nt/test",
        }
        # 테스트에서 프롬프트가 실제로 블로킹되지 않도록, 기본적으로 EOFError로
        # 즉시 건너뛰게 만든다. 특정 값이 필요한 테스트는 os.environ을 patch한다.
        self._input_patcher = patch(f"{_ENV_MODULE}.input", side_effect=EOFError)
        self._getpass_patcher = patch(
            f"{_ENV_MODULE}.getpass.getpass", side_effect=EOFError
        )
        self._input_patcher.start()
        self._getpass_patcher.start()
        self.addCleanup(self._input_patcher.stop)
        self.addCleanup(self._getpass_patcher.stop)

    def test_unknown_business_id_raises_command_error(self):
        with self.assertRaises(CommandError):
            _run_command(business_id=999999, start_date="20260801", end_date="20260803",
                          organization="TEST_ORG", path="/v1/kr/public/nt/test")

    def test_dry_run_does_not_call_codef_client(self):
        with patch(f"{_ENV_MODULE}.CodefClient") as mock_client_cls:
            output = _run_command(**self.base_options, dry_run=True)

        mock_client_cls.return_value.post.assert_not_called()
        self.assertIn("--dry-run이므로 CODEF로 전송하지 않았습니다.", output)
        self.assertIn('"organization": "TEST_ORG"', output)

    def test_no_stdin_and_no_env_gracefully_skips_sensitive_fields(self):
        # setUp에서 input/getpass가 EOFError를 내도록 이미 patch돼 있고,
        # 환경변수도 없는 상태 — 그래도 명령이 죽지 않고 그냥 필드를 생략해야 한다.
        with patch(f"{_ENV_MODULE}.CodefClient") as mock_client_cls:
            mock_client_cls.return_value.post.return_value = {
                "result": {"code": "CF-00000", "message": "성공"},
                "data": [],
            }
            _run_command(**self.base_options)

        _, sent_payload = mock_client_cls.return_value.post.call_args[0]
        self.assertNotIn("userName", sent_payload)
        self.assertNotIn("phoneNo", sent_payload)
        self.assertNotIn("identity", sent_payload)

    @patch.dict(
        os.environ,
        {
            "CODEF_PROBE_USER_NAME": "김지훈",
            "CODEF_PROBE_PHONE_NO": "01012345678",
            "CODEF_PROBE_IDENTITY": "20000101",
        },
    )
    def test_env_values_are_used_without_prompting(self):
        with patch(f"{_ENV_MODULE}.CodefClient") as mock_client_cls, \
             patch(f"{_ENV_MODULE}.input") as mock_input, \
             patch(f"{_ENV_MODULE}.getpass.getpass") as mock_getpass:
            mock_client_cls.return_value.post.return_value = {
                "result": {"code": "CF-03002", "message": ""},
                "data": {
                    "continue2Way": True,
                    "jobIndex": 0,
                    "threadIndex": 1,
                    "jti": "mock-jti-value",
                    "twoWayTimestamp": 1735689600000,
                },
            }
            # 이 테스트는 "물어보지 않는다"는 것만 확인하면 되므로 암호화는
            # 끄고 identity 원문이 그대로 전달됐는지로 간단히 검증한다.
            _run_command(**self.base_options, no_encrypt_identity=True)

        # .env 값이 있으면 물어보지 않아야 한다.
        mock_input.assert_not_called()
        mock_getpass.assert_not_called()

        _, sent_payload = mock_client_cls.return_value.post.call_args[0]
        self.assertEqual(sent_payload["userName"], "김지훈")
        self.assertEqual(sent_payload["phoneNo"], "01012345678")
        self.assertEqual(sent_payload["identity"], "20000101")

    @patch.dict(os.environ, {"CODEF_PROBE_IDENTITY": "1234567890"})
    @override_settings(CODEF_PUBLIC_KEY=_TEST_PUBLIC_KEY_B64)
    def test_identity_is_encrypted_by_default_and_decrypts_back_to_original(self):
        # 명령을 통째로 돌려서 실제로 전송되는 identity가 평문이 아니고,
        # 대응하는 개인키로 복호화하면 원문 그대로 나오는지까지 확인한다 —
        # encrypt_with_public_key() 단위 테스트와 별개로, 커맨드가 그 함수를
        # 제대로 연결해서 쓰는지 보는 통합 테스트다.
        mock_response = {"result": {"code": "CF-00000", "message": "성공"}, "data": []}
        with patch(f"{_ENV_MODULE}.CodefClient") as mock_client_cls:
            mock_client_cls.return_value.post.return_value = mock_response
            output = _run_command(**self.base_options)

        _, sent_payload = mock_client_cls.return_value.post.call_args[0]
        self.assertNotEqual(sent_payload["identity"], "1234567890")
        self.assertEqual(_decrypt_with_test_private_key(sent_payload["identity"]), "1234567890")
        self.assertIn("RSA 암호화했습니다", output)

    @patch.dict(os.environ, {"CODEF_PROBE_IDENTITY": "1234567890"})
    def test_identity_encryption_without_public_key_raises_clear_command_error(self):
        # CODEF_PUBLIC_KEY가 비어 있으면(.env.example 기본값), 알 수 없는
        # crypto 라이브러리 예외가 아니라 알아볼 수 있는 CommandError가 나야 한다.
        with override_settings(CODEF_PUBLIC_KEY=""):
            with self.assertRaisesMessage(CommandError, "identity 암호화 실패"):
                _run_command(**self.base_options)

    @patch.dict(os.environ, {"CODEF_PROBE_IDENTITY": "1234567890"})
    def test_no_encrypt_identity_sends_plaintext(self):
        mock_response = {"result": {"code": "CF-00000", "message": "성공"}, "data": []}
        with patch(f"{_ENV_MODULE}.CodefClient") as mock_client_cls:
            mock_client_cls.return_value.post.return_value = mock_response
            output = _run_command(**self.base_options, no_encrypt_identity=True)

        _, sent_payload = mock_client_cls.return_value.post.call_args[0]
        self.assertEqual(sent_payload["identity"], "1234567890")
        self.assertIn("암호화하지 않고 평문으로 보냅니다", output)

    @patch.dict(
        os.environ,
        {
            "CODEF_PROBE_USER_NAME": "김지훈",
            "CODEF_PROBE_PHONE_NO": "01012345678",
            "CODEF_PROBE_IDENTITY": "20000101",
        },
    )
    def test_dry_run_output_masks_plaintext_identity_when_encryption_disabled(self):
        output = _run_command(**self.base_options, dry_run=True, no_encrypt_identity=True)

        # 실제 값이 화면에 그대로 나오면 안 된다.
        self.assertNotIn("김지훈", output)
        self.assertNotIn("01012345678", output)
        self.assertNotIn("20000101", output)

        # 마스킹된 형태로는 나와야 한다 (전화번호는 앞3/뒤4 유지).
        self.assertIn('"userName": "***"', output)
        self.assertIn('"phoneNo": "010****5678"', output)
        self.assertIn('"identity": "********"', output)

    @patch.dict(
        os.environ,
        {
            "CODEF_PROBE_USER_NAME": "김지훈",
            "CODEF_PROBE_PHONE_NO": "01012345678",
            "CODEF_PROBE_IDENTITY": "20000101",
        },
    )
    @override_settings(CODEF_PUBLIC_KEY=_TEST_PUBLIC_KEY_B64)
    def test_dry_run_output_shows_encrypted_marker_by_default(self):
        output = _run_command(**self.base_options, dry_run=True)

        self.assertNotIn("20000101", output)
        # 암호화된 값은 매번 랜덤이라 원문 길이로 마스킹하지 않고 고정 표시를 쓴다.
        self.assertIn('"identity": "***encrypted***"', output)

    def test_first_request_has_no_two_way_fields(self):
        mock_response = {
            "result": {"code": "CF-03002", "message": "추가인증이 필요합니다."},
            "data": {
                "continue2Way": True,
                "jobIndex": 0,
                "threadIndex": 1,
                "jti": "mock-jti-value",
                "twoWayTimestamp": 1735689600000,
            },
        }
        with patch(f"{_ENV_MODULE}.CodefClient") as mock_client_cls:
            mock_client_cls.return_value.post.return_value = mock_response
            output = _run_command(**self.base_options)

        sent_path, sent_payload = mock_client_cls.return_value.post.call_args[0]
        self.assertEqual(sent_path, "/v1/kr/public/nt/test")
        self.assertNotIn("twoWayInfo", sent_payload)
        self.assertNotIn("simpleAuth", sent_payload)

        self.assertIn("CF-03002", output)
        self.assertIn("jobIndex = 0", output)
        self.assertIn("jti = 'mock-jti-value'", output)

    def test_continue_request_requires_simple_auth(self):
        with self.assertRaises(CommandError):
            _run_command(
                **self.base_options,
                job_index=0,
                thread_index=1,
                jti="mock-jti-value",
                two_way_timestamp=1735689600000,
            )

    def test_continue_request_adds_two_way_info_to_payload(self):
        mock_response = {
            "result": {"code": "CF-00000", "message": "성공"},
            "data": [],
        }
        with patch(f"{_ENV_MODULE}.CodefClient") as mock_client_cls:
            mock_client_cls.return_value.post.return_value = mock_response
            _run_command(
                **self.base_options,
                simple_auth="1",
                job_index=0,
                thread_index=1,
                jti="mock-jti-value",
                two_way_timestamp=1735689600000,
            )

        _, sent_payload = mock_client_cls.return_value.post.call_args[0]
        self.assertEqual(sent_payload["simpleAuth"], "1")
        self.assertIs(sent_payload["is2Way"], True)
        self.assertEqual(
            sent_payload["twoWayInfo"],
            {
                "jobIndex": 0,
                "threadIndex": 1,
                "jti": "mock-jti-value",
                "twoWayTimestamp": 1735689600000,
            },
        )

    def test_continue_request_simple_auth_is_independent_from_login_type_level(self):
        # simpleAuth와 loginTypeLevel(카카오=1)이 우연히 값이 겹쳐도 서로 다른
        # 필드로 따로 실려야 한다 — 하나로 합쳐지거나 덮어써지면 안 된다.
        mock_response = {"result": {"code": "CF-00000", "message": "성공"}, "data": []}
        with patch(f"{_ENV_MODULE}.CodefClient") as mock_client_cls:
            mock_client_cls.return_value.post.return_value = mock_response
            _run_command(
                **self.base_options,
                login_type_level="1",
                simple_auth="2",
                job_index=0,
                thread_index=1,
                jti="mock-jti-value",
                two_way_timestamp=1735689600000,
            )

        _, sent_payload = mock_client_cls.return_value.post.call_args[0]
        self.assertEqual(sent_payload["loginTypeLevel"], "1")
        self.assertEqual(sent_payload["simpleAuth"], "2")

    def test_partial_two_way_args_raise_command_error(self):
        with self.assertRaises(CommandError):
            _run_command(**self.base_options, job_index=0)

    def test_success_response_prints_normalized_transactions(self):
        mock_response = {
            "result": {"code": "CF-00000", "message": "성공"},
            "data": [
                {
                    "resUsedDate": "20260802",
                    "resUsedTime": "091523",
                    "resTransTypeNm": "승인거래",
                    "resApprovalNo": "REAL-CR-001",
                    "resSupplyValue": "5000",
                    "resVAT": "500",
                    "resTotalAmount": "5500",
                    "resCompanyIdentityNo": "1234567890",
                }
            ],
        }
        with patch(f"{_ENV_MODULE}.CodefClient") as mock_client_cls:
            mock_client_cls.return_value.post.return_value = mock_response
            output = _run_command(**self.base_options)

        self.assertIn("CF-00000: 성공. normalizer 결과 미리보기:", output)
        self.assertIn("REAL-CR-001", output)

        # normalizer 출력(한 줄 JSON)이 실제로 JSON 파싱 가능한지 확인한다.
        # (raw 응답도 pretty-print돼 있어 같은 승인번호를 담은 줄이 더 있으므로
        # normalizer 전용 키인 source_type으로 정확히 그 줄만 골라낸다.)
        json_line = next(
            line
            for line in output.splitlines()
            if "REAL-CR-001" in line and "source_type" in line
        )
        parsed = json.loads(json_line)
        self.assertEqual(parsed["approval_no"], "REAL-CR-001")
        self.assertEqual(parsed["total_amount"], "5500")

    def test_failure_code_is_reported_without_raising(self):
        mock_response = {
            "result": {"code": "CF-04000", "message": "잘못된 요청입니다."},
            "data": [],
        }
        with patch(f"{_ENV_MODULE}.CodefClient") as mock_client_cls:
            mock_client_cls.return_value.post.return_value = mock_response
            output = _run_command(**self.base_options)

        self.assertIn("CF-04000", output)
        self.assertIn("잘못된 요청입니다", output)