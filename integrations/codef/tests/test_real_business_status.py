"""RealCodefProvider.get_business_status()의 응답 정규화 검증.

여기 쓰인 성공/실패 응답 형태는 실제 CODEF 서버를 호출하지 않고, 공식
CODEF SDK(github.com/codef-io/easycodef-node) README에 실린 예시 응답을
그대로 사용한다. 실제 네트워크 호출은 CodefClient를 Mock으로 대체해 차단한다
— CI에서도 안전하게 돌아야 하고, 실제 CODEF 응답 형식이 바뀌지 않는 한
이 테스트가 통과하면 파싱 로직은 신뢰할 수 있다.
"""

from unittest.mock import Mock

from django.test import SimpleTestCase

import requests

from integrations.codef.client import CodefClientError
from integrations.codef.real import RealCodefProvider


class GetBusinessStatusTests(SimpleTestCase):
    def test_success_normalizes_official_sample_response(self):
        # easycodef-node README의 사업자등록상태 성공 응답 예시(두 번째 항목) 그대로.
        client = Mock()
        client.post.return_value = {
            "result": {"code": "CF-00000", "message": "성공"},
            "data": [
                {
                    "resBusinessStatus": (
                        "부가가치세일반과세자입니다.\n"
                        "*과세유형전환된날짜는2011년07월01일입니다."
                    ),
                    "resCompanyIdentityNo": "1234567890",
                    "code": "CF-00000",
                    "resTaxationTypeCode": "1",
                    "resClosingDate": "",
                    "resTransferTaxTypeDate": "20110701",
                }
            ],
        }
        provider = RealCodefProvider(client=client)

        result = provider.get_business_status("1234567890")

        self.assertEqual(result["outcome"], "SUCCESS")
        self.assertEqual(result["company_identity_no"], "1234567890")
        self.assertEqual(result["taxation_type_code"], "1")
        self.assertEqual(result["transfer_tax_type_date"], "20110701")

    def test_request_uses_official_organization_and_camel_case_field(self):
        client = Mock()
        client.post.return_value = {
            "result": {"code": "CF-00000", "message": "성공"},
            "data": [{"resCompanyIdentityNo": "1234567890", "code": "CF-00000"}],
        }
        provider = RealCodefProvider(client=client)

        provider.get_business_status("1234567890")

        client.post.assert_called_once_with(
            "/v1/kr/public/nt/business/status",
            {
                "organization": "0004",
                "reqIdentityList": [{"reqIdentity": "1234567890"}],
            },
        )

    def test_top_level_failure_code_is_reported(self):
        client = Mock()
        client.post.return_value = {
            "result": {"code": "CF-04000", "message": "잘못된 요청입니다."},
            "data": [],
        }
        provider = RealCodefProvider(client=client)

        result = provider.get_business_status("0000000000")

        self.assertEqual(result["outcome"], "FAILURE")
        self.assertEqual(result["error_code"], "CF-04000")

    def test_item_level_failure_is_reported_even_when_top_level_succeeds(self):
        # result.code는 CF-00000(전체 요청 자체는 정상)이지만, 개별 조회 항목이
        # 실패할 수 있다 — data[].code까지 확인해야 하는 이유.
        client = Mock()
        client.post.return_value = {
            "result": {"code": "CF-00000", "message": "성공"},
            "data": [
                {
                    "code": "CF-04002",
                    "message": "해당 사업자번호를 찾을 수 없습니다.",
                    "resCompanyIdentityNo": "9999999999",
                }
            ],
        }
        provider = RealCodefProvider(client=client)

        result = provider.get_business_status("9999999999")

        self.assertEqual(result["outcome"], "FAILURE")
        self.assertEqual(result["error_code"], "CF-04002")

    def test_codef_client_error_becomes_failure_outcome(self):
        client = Mock()
        client.post.side_effect = CodefClientError("CODEF_CLIENT_ID가 설정되지 않았습니다.")
        provider = RealCodefProvider(client=client)

        result = provider.get_business_status("1234567890")

        self.assertEqual(result["outcome"], "FAILURE")
        self.assertEqual(result["error_code"], "CODEF_CLIENT_ERROR")

    def test_network_error_becomes_failure_outcome_not_raised_exception(self):
        client = Mock()
        client.post.side_effect = requests.exceptions.ConnectionError("연결 실패")
        provider = RealCodefProvider(client=client)

        result = provider.get_business_status("1234567890")

        self.assertEqual(result["outcome"], "FAILURE")
        self.assertEqual(result["error_code"], "CODEF_HTTP_ERROR")

    def test_no_matching_business_number_in_response_is_reported_not_guessed(self):
        # data에 항목이 있어도, 요청한 사업자번호와 정확히 일치하는 게 없으면
        # 첫 번째 항목을 대신 쓰지 않고 명시적으로 실패해야 한다 — 다른 사업자
        # 데이터를 우리 Business에 잘못 반영하는 사고를 막기 위함.
        client = Mock()
        client.post.return_value = {
            "result": {"code": "CF-00000", "message": "성공"},
            "data": [
                {
                    "resCompanyIdentityNo": "9999999999",
                    "code": "CF-00000",
                    "resBusinessStatus": "다른 사업자 데이터",
                }
            ],
        }
        provider = RealCodefProvider(client=client)

        result = provider.get_business_status("1234567890")

        self.assertEqual(result["outcome"], "FAILURE")
        self.assertEqual(result["error_code"], "BUSINESS_NOT_FOUND_IN_RESPONSE")