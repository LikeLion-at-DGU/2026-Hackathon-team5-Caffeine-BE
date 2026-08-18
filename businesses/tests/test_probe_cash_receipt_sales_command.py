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


def _run_command(**options):
    out = io.StringIO()
    call_command(
        "probe_cash_receipt_sales",
        stdout=out,
        **options,
    )
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
            "login_type": "1",
        }

        # --------------------------------------------------
        # stdin 차단
        # --------------------------------------------------
        #
        # 테스트에서 실제 input/getpass 프롬프트가 실행되어
        # 테스트가 멈추는 것을 방지한다.
        #
        # 특정 민감값이 필요한 테스트에서는
        # @patch.dict(os.environ, ...)으로 별도 값을 주입한다.
        # --------------------------------------------------

        self._input_patcher = patch(
            f"{_ENV_MODULE}.input",
            side_effect=EOFError,
        )

        self._getpass_patcher = patch(
            f"{_ENV_MODULE}.getpass.getpass",
            side_effect=EOFError,
        )

        self._input_patcher.start()
        self._getpass_patcher.start()

        self.addCleanup(
            self._input_patcher.stop
        )
        self.addCleanup(
            self._getpass_patcher.stop
        )

        # --------------------------------------------------
        # 로컬 .env 격리
        # --------------------------------------------------
        #
        # 개발자의 실제 .env에 CODEF_PROBE_* 값이 존재하면
        # "환경변수가 없는 상황"을 테스트하는 케이스에도
        # 실제 값이 들어갈 수 있다.
        #
        # 테스트 시작 시 기본적으로 빈 값으로 덮어써서
        # 로컬 환경과 테스트를 분리한다.
        #
        # 특정 환경변수 값이 필요한 테스트는
        # 테스트 함수의 @patch.dict가 다시 값을 덮어쓴다.
        # --------------------------------------------------

        self._env_patcher = patch.dict(
            os.environ,
            {
                "CODEF_PROBE_USER_NAME": "",
                "CODEF_PROBE_PHONE_NO": "",
                "CODEF_PROBE_LOGIN_IDENTITY": "",
                "CODEF_PROBE_IDENTITY": "",
            },
            clear=False,
        )

        self._env_patcher.start()

        self.addCleanup(
            self._env_patcher.stop
        )

    def test_unknown_business_id_raises_command_error(self):
        with self.assertRaises(CommandError):
            _run_command(
                business_id=999999,
                start_date="20260801",
                end_date="20260803",
                organization="TEST_ORG",
                path="/v1/kr/public/nt/test",
                login_type="1",
            )

    def test_dry_run_does_not_call_codef_client(self):
        with patch(
            f"{_ENV_MODULE}.CodefClient"
        ) as mock_client_cls:
            output = _run_command(
                **self.base_options,
                dry_run=True,
            )

        mock_client_cls.return_value.post.assert_not_called()

        self.assertIn(
            "--dry-run이므로 CODEF로 전송하지 않았습니다.",
            output,
        )

        self.assertIn(
            '"organization": "TEST_ORG"',
            output,
        )

    def test_no_stdin_and_no_env_gracefully_skips_sensitive_fields(self):
        with patch(
            f"{_ENV_MODULE}.CodefClient"
        ) as mock_client_cls:
            mock_client_cls.return_value.post.return_value = {
                "result": {
                    "code": "CF-00000",
                    "message": "성공",
                },
                "data": [],
            }

            _run_command(
                **self.base_options
            )

        _, sent_payload = (
            mock_client_cls
            .return_value
            .post
            .call_args[0]
        )

        self.assertNotIn(
            "userName",
            sent_payload,
        )

        self.assertNotIn(
            "phoneNo",
            sent_payload,
        )

        self.assertNotIn(
            "loginIdentity",
            sent_payload,
        )

        self.assertNotIn(
            "identity",
            sent_payload,
        )

    @patch.dict(
        os.environ,
        {
            "CODEF_PROBE_USER_NAME": "김지훈",
            "CODEF_PROBE_PHONE_NO": "01012345678",
            "CODEF_PROBE_LOGIN_IDENTITY": "19900101",
            "CODEF_PROBE_IDENTITY": "20000101",
        },
    )
    def test_env_values_are_used_without_prompting(self):
        with (
            patch(
                f"{_ENV_MODULE}.CodefClient"
            ) as mock_client_cls,
            patch(
                f"{_ENV_MODULE}.input"
            ) as mock_input,
            patch(
                f"{_ENV_MODULE}.getpass.getpass"
            ) as mock_getpass,
        ):
            mock_client_cls.return_value.post.return_value = {
                "result": {
                    "code": "CF-03002",
                    "message": "",
                },
                "data": {
                    "continue2Way": True,
                    "jobIndex": 0,
                    "threadIndex": 1,
                    "jti": "mock-jti-value",
                    "twoWayTimestamp": 1735689600000,
                },
            }

            _run_command(
                **self.base_options
            )

        mock_input.assert_not_called()
        mock_getpass.assert_not_called()

        _, sent_payload = (
            mock_client_cls
            .return_value
            .post
            .call_args[0]
        )

        self.assertEqual(
            sent_payload["userName"],
            "김지훈",
        )

        self.assertEqual(
            sent_payload["phoneNo"],
            "01012345678",
        )

        self.assertEqual(
            sent_payload["loginIdentity"],
            "19900101",
        )

        self.assertEqual(
            sent_payload["identity"],
            "20000101",
        )

    def test_login_type_5_requires_mandatory_fields(self):
        with self.assertRaisesMessage(
            CommandError,
            "loginType='5'(회원 간편인증) 필수값이 누락되었습니다",
        ):
            _run_command(
                **{
                    **self.base_options,
                    "login_type": "5",
                },
            )

    @patch.dict(
        os.environ,
        {
            "CODEF_PROBE_USER_NAME": "김지훈",
            "CODEF_PROBE_PHONE_NO": "01012345678",
            "CODEF_PROBE_LOGIN_IDENTITY": "19900101",
        },
    )
    def test_login_type_5_succeeds_with_valid_fields(self):
        with patch(
            f"{_ENV_MODULE}.CodefClient"
        ) as mock_client_cls:
            mock_client_cls.return_value.post.return_value = {
                "result": {
                    "code": "CF-00000",
                    "message": "성공",
                },
                "data": [],
            }

            _run_command(
                **{
                    **self.base_options,
                    "login_type": "5",
                },
            )

        _, sent_payload = (
            mock_client_cls
            .return_value
            .post
            .call_args[0]
        )

        self.assertEqual(
            sent_payload["userName"],
            "김지훈",
        )

        self.assertEqual(
            sent_payload["loginIdentity"],
            "19900101",
        )

        self.assertEqual(
            sent_payload["phoneNo"],
            "01012345678",
        )

    @patch.dict(
        os.environ,
        {
            "CODEF_PROBE_USER_NAME": "김지훈",
            "CODEF_PROBE_PHONE_NO": "01012345678",
            "CODEF_PROBE_LOGIN_IDENTITY": "900101",
        },
    )
    def test_login_type_5_invalid_birthdate_raises_error(self):
        with self.assertRaisesMessage(
            CommandError,
            "loginType='5'의 loginIdentity는 생년월일 8자리",
        ):
            _run_command(
                **{
                    **self.base_options,
                    "login_type": "5",
                },
            )

    @patch.dict(
        os.environ,
        {
            "CODEF_PROBE_USER_NAME": "김지훈",
            "CODEF_PROBE_PHONE_NO": "01012345678",
            "CODEF_PROBE_IDENTITY": "20000101",
        },
    )
    def test_dry_run_output_masks_sensitive_fields(self):
        output = _run_command(
            **self.base_options,
            dry_run=True,
        )

        self.assertNotIn(
            "김지훈",
            output,
        )

        self.assertNotIn(
            "01012345678",
            output,
        )

        self.assertNotIn(
            "20000101",
            output,
        )

        self.assertIn(
            '"userName": "***"',
            output,
        )

        self.assertIn(
            '"phoneNo": "010****5678"',
            output,
        )

        self.assertIn(
            '"identity": "********"',
            output,
        )

    def test_first_request_has_no_two_way_fields(self):
        mock_response = {
            "result": {
                "code": "CF-03002",
                "message": "추가인증이 필요합니다.",
            },
            "data": {
                "continue2Way": True,
                "jobIndex": 0,
                "threadIndex": 1,
                "jti": "mock-jti-value",
                "twoWayTimestamp": 1735689600000,
            },
        }

        with patch(
            f"{_ENV_MODULE}.CodefClient"
        ) as mock_client_cls:
            mock_client_cls.return_value.post.return_value = (
                mock_response
            )

            output = _run_command(
                **self.base_options
            )

        sent_path, sent_payload = (
            mock_client_cls
            .return_value
            .post
            .call_args[0]
        )

        self.assertEqual(
            sent_path,
            "/v1/kr/public/nt/test",
        )

        self.assertNotIn(
            "twoWayInfo",
            sent_payload,
        )

        self.assertNotIn(
            "simpleAuth",
            sent_payload,
        )

        self.assertIn(
            "CF-03002",
            output,
        )

        self.assertIn(
            "jobIndex = 0",
            output,
        )

        self.assertIn(
            "jti = 'mock-jti-value'",
            output,
        )

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
            "result": {
                "code": "CF-00000",
                "message": "성공",
            },
            "data": [],
        }

        with patch(
            f"{_ENV_MODULE}.CodefClient"
        ) as mock_client_cls:
            mock_client_cls.return_value.post.return_value = (
                mock_response
            )

            _run_command(
                **self.base_options,
                simple_auth="1",
                job_index=0,
                thread_index=1,
                jti="mock-jti-value",
                two_way_timestamp=1735689600000,
            )

        _, sent_payload = (
            mock_client_cls
            .return_value
            .post
            .call_args[0]
        )

        self.assertEqual(
            sent_payload["simpleAuth"],
            "1",
        )

        self.assertIs(
            sent_payload["is2Way"],
            True,
        )

        self.assertEqual(
            sent_payload["twoWayInfo"],
            {
                "jobIndex": 0,
                "threadIndex": 1,
                "jti": "mock-jti-value",
                "twoWayTimestamp": 1735689600000,
            },
        )

    def test_continue_request_simple_auth_is_independent_from_login_type_level(
        self,
    ):
        mock_response = {
            "result": {
                "code": "CF-00000",
                "message": "성공",
            },
            "data": [],
        }

        with patch(
            f"{_ENV_MODULE}.CodefClient"
        ) as mock_client_cls:
            mock_client_cls.return_value.post.return_value = (
                mock_response
            )

            _run_command(
                **self.base_options,
                login_type_level="1",
                simple_auth="2",
                job_index=0,
                thread_index=1,
                jti="mock-jti-value",
                two_way_timestamp=1735689600000,
            )

        _, sent_payload = (
            mock_client_cls
            .return_value
            .post
            .call_args[0]
        )

        self.assertEqual(
            sent_payload["loginTypeLevel"],
            "1",
        )

        self.assertEqual(
            sent_payload["simpleAuth"],
            "2",
        )

    def test_partial_two_way_args_raise_command_error(self):
        with self.assertRaises(CommandError):
            _run_command(
                **self.base_options,
                job_index=0,
            )

    def test_success_response_prints_normalized_transactions(self):
        mock_response = {
            "result": {
                "code": "CF-00000",
                "message": "성공",
            },
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

        with patch(
            f"{_ENV_MODULE}.CodefClient"
        ) as mock_client_cls:
            mock_client_cls.return_value.post.return_value = (
                mock_response
            )

            output = _run_command(
                **self.base_options
            )

        self.assertIn(
            "CF-00000: 성공. normalizer 결과 미리보기:",
            output,
        )

        self.assertIn(
            "REAL-CR-001",
            output,
        )

        json_line = next(
            line
            for line in output.splitlines()
            if (
                "REAL-CR-001" in line
                and "source_type" in line
            )
        )

        parsed = json.loads(
            json_line
        )

        self.assertEqual(
            parsed["approval_no"],
            "REAL-CR-001",
        )

        self.assertEqual(
            parsed["total_amount"],
            "5500",
        )

    def test_failure_code_is_reported_without_raising(self):
        mock_response = {
            "result": {
                "code": "CF-04000",
                "message": "잘못된 요청입니다.",
            },
            "data": [],
        }

        with patch(
            f"{_ENV_MODULE}.CodefClient"
        ) as mock_client_cls:
            mock_client_cls.return_value.post.return_value = (
                mock_response
            )

            output = _run_command(
                **self.base_options
            )

        self.assertIn(
            "CF-04000",
            output,
        )

        self.assertIn(
            "잘못된 요청입니다",
            output,
        )