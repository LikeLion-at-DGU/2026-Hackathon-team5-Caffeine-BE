import json
import os

from .base import BaseCodefProvider


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# 사업자등록상태 조회 성공을 나타내는 Mock 전용 코드
_SUCCESS = "MOCK-00000"


def load_fixture(filename):
    """fixtures 폴더의 JSON 파일을 읽어 dict로 반환한다."""
    path = os.path.join(FIXTURES_DIR, filename)

    with open(path, encoding="utf-8") as f:
        return json.load(f)


class MockCodefProvider(BaseCodefProvider):
    """개발 및 테스트용 CODEF Mock Provider."""

    def get_business_status(self, business_number):
        # 사업자등록상태 조회 성공 상황을 가정한 Mock 응답
        raw = load_fixture("business_status_success.json")
        code = raw.get("code", "")

        # CODEF 형식의 Mock 데이터를 Service에서 사용할 공통 형식으로 변환한다.
        if code != _SUCCESS:
            return {
                "outcome": "FAILURE",
                "error_code": code,
                "error_message": raw.get("message", ""),
            }

        return {
            "outcome": "SUCCESS",
            "company_identity_no": raw.get("resCompanyIdentityNo", ""),
            "business_status": raw.get("resBusinessStatus", ""),
            "taxation_type_code": raw.get("resTaxationTypeCode", ""),
            "closing_date": raw.get("resClosingDate", ""),
            "transfer_tax_type_date": raw.get("resTransferTaxTypeDate", ""),
        }

    def request_auth(self, business, connection_type):
        # CODEF 인증 요청 Mock은 이후 구현한다.
        raise NotImplementedError

    def retry_auth(self, business, connection):
        # HOMETAX 2-way 인증 재시도 Mock은 이후 구현한다.
        raise NotImplementedError