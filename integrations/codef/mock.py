import json
import os

from .base import BaseCodefProvider


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

# Mock 응답 상태 코드
_SUCCESS = "MOCK-00000"
_AUTH_REQUIRED = "MOCK-AUTH-REQUIRED"


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
            "transfer_tax_type_date": raw.get(
                "resTransferTaxTypeDate",
                "",
            ),
        }

    def request_auth(self, business, connection_type):
        # 연결 유형에 맞는 Mock 응답을 공통 형식으로 변환해 반환한다.
        if connection_type == "HOMETAX":
            return self._normalize_hometax(
                load_fixture("hometax_auth_required.json")
            )

        return self._normalize_card(
            load_fixture("card_connected_success.json")
        )

    def retry_auth(self, business, connection):
        # HOMETAX 2-way 인증 재시도 성공 상황을 가정한 Mock 응답
        return self._normalize_hometax(
            load_fixture("hometax_auth_success.json")
        )

    def get_business_card_purchases(self, business, start_date, end_date):
        return load_fixture("business_card_purchase_success.json")

    def get_cash_receipt_sales(self, business, start_date, end_date):
        return load_fixture("cash_receipt_sales_success.json")

    def get_tax_invoice_purchases(self, business, start_date, end_date):
        return load_fixture("tax_invoice_purchase_success.json")

    def get_tax_invoice_sales(self, business, start_date, end_date):
        return load_fixture("tax_invoice_sales_success.json")

    def get_credit_card_sales_summary(self, business, start_date, end_date):
        return load_fixture("credit_card_sales_success.json")

    @staticmethod
    def _normalize_hometax(raw):
        # CODEF 2-way 응답을 Service에서 사용할 공통 형식으로 변환한다.
        code = raw.get("result", {}).get("code", "")
        data = raw.get("data", {})

        if code == _AUTH_REQUIRED:
            return {
                "outcome": "AUTH_REQUIRED",
                "continue_2way": True,
                "method": data.get("method", ""),
                "job_index": data.get("jobIndex"),
                "thread_index": data.get("threadIndex"),
                "jti": data.get("jti", ""),
                "two_way_timestamp": data.get("twoWayTimestamp"),
            }

        if code == _SUCCESS:
            return {
                "outcome": "SUCCESS",
            }

        return {
            "outcome": "FAILURE",
            "error_code": code,
            "error_message": raw.get("result", {}).get(
                "message",
                "",
            ),
        }

    @staticmethod
    def _normalize_card(raw):
        # CODEF 계정 등록 응답을 Service에서 사용할 공통 형식으로 변환한다.
        code = raw.get("result", {}).get("code", "")

        if code != _SUCCESS:
            return {
                "outcome": "FAILURE",
                "error_code": code,
                "error_message": raw.get("result", {}).get(
                    "message",
                    "",
                ),
            }

        connected_id = raw.get("data", {}).get("connectedId", "")

        # 성공 응답이라도 Connected ID가 없으면 연결 실패로 처리한다.
        if not connected_id:
            return {
                "outcome": "FAILURE",
                "error_code": "EMPTY_CONNECTED_ID",
                "error_message": "connectedId가 비어 있습니다.",
            }

        return {
            "outcome": "SUCCESS",
            "connected_id": connected_id,
        }
