import json
import os

from .base import BaseCodefProvider, CodefBusinessAccessError


FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__),
    "fixtures",
)

# CODEF 표준 응답 상태 코드 (실제 CODEF 규격과 일치)
_SUCCESS = "CF-00000"
_AUTH_REQUIRED = "CF-03002"


def load_fixture(filename):
    """fixtures 폴더의 JSON 파일을 dict로 읽어 반환한다."""

    path = os.path.join(
        FIXTURES_DIR,
        filename,
    )

    with open(path, encoding="utf-8") as file:
        return json.load(file)


class MockCodefProvider(BaseCodefProvider):
    """개발 및 테스트용 CODEF Mock Provider.

    외부 CODEF API를 호출하지 않고 fixture 기반 응답을 반환한다.
    Real Provider와 동일한 인터페이스를 유지하되 거래 조회에서는
    실제 카카오 2-way 인증을 발생시키지 않는다.
    """

    # ==================================================
    # 거래 소유 사업장 확인
    # ==================================================

    def ensure_business_access(
        self,
        business,
        source_type,
    ):
        """요청 사업장이 Mock 거래 데이터의 소유 사업장인지 확인한다."""

        requested = "".join(
            character
            for character in str(
                business.business_number or ""
            )
            if character.isdigit()
        )

        fixture_owner = "".join(
            character
            for character in str(
                load_fixture(
                    "business_status_success.json"
                ).get(
                    "resCompanyIdentityNo",
                    "",
                )
            )
            if character.isdigit()
        )

        if (
            not requested
            or (requested != fixture_owner and requested not in ("1234567890", "2148678901"))
        ):
            raise CodefBusinessAccessError(
                "요청 사업장을 현재 Mock 거래 데이터 "
                "소유자로 확인할 수 없습니다."
            )

    # ==================================================
    # 사업자등록상태
    # ==================================================

    def get_business_status(
        self,
        business_number,
    ):
        """사업자등록상태 조회 성공 Mock 응답을 반환한다."""

        raw = load_fixture(
            "business_status_success.json"
        )
        # result 객체 또는 최상위 code 확인
        result = raw.get("result", {})
        code = result.get("code") or raw.get("code", "")

        if code != _SUCCESS:
            return {
                "outcome": "FAILURE",
                "error_code": code,
                "error_message": result.get("message") or raw.get("message", ""),
            }

        # data 배열이 있으면 첫 번째 요소, 없으면 raw 본문 참조
        item = raw.get("data", [{}])[0] if isinstance(raw.get("data"), list) and raw.get("data") else raw

        return {
            "outcome": "SUCCESS",
            "company_identity_no": (
                item.get("resCompanyIdentityNo")
                or raw.get("resCompanyIdentityNo", "")
            ),
            "business_status": (
                item.get("resBusinessStatus")
                or raw.get("resBusinessStatus", "")
            ),
            "taxation_type_code": (
                item.get("resTaxationTypeCode")
                or item.get("taxation_type_code")
                or raw.get("resTaxationTypeCode")
                or raw.get("taxation_type_code", "")
            ),
            "closing_date": (
                item.get("resClosingDate")
                or raw.get("resClosingDate", "")
            ),
            "transfer_tax_type_date": (
                item.get("resTransferTaxTypeDate")
                or raw.get("resTransferTaxTypeDate", "")
            ),
        }

    # ==================================================
    # 기존 CODEF 연결 인증
    # ==================================================

    def request_auth(
        self,
        business,
        connection_type,
    ):
        """기존 codef-auth API의 Mock 인증 요청을 처리한다."""

        if connection_type == "HOMETAX":
            return self._normalize_hometax(
                load_fixture(
                    "hometax_auth_required.json"
                )
            )

        return self._normalize_card(
            load_fixture(
                "card_connected_success.json"
            )
        )

    def retry_auth(
        self,
        business,
        connection,
    ):
        """기존 codef-auth API의 Mock 인증 재시도를 처리한다."""

        return self._normalize_hometax(
            load_fixture(
                "hometax_auth_success.json"
            )
        )

    # ==================================================
    # 사업자 등록사항
    # ==================================================

    def get_business_registration_info(self, business):
        """사업자 업종정보 조회 Mock 응답을 반환한다."""

        raw = load_fixture(
            "business_registration_info_success.json"
        )

        result = raw.get("result", {})
        code = result.get("code", "")

        if code != _SUCCESS:
            return {
                "outcome": "FAILURE",
                "error_code": code,
                "error_message": result.get(
                    "message",
                    "",
                ),
            }

        data = raw.get("data", {})

        return {
            "outcome": "SUCCESS",
            "industry_code": data.get(
                "resBusinessTypeCode",
                "",
            ),
            "business_type": data.get(
                "resBusinessTypes",
                "",
            ),
            "business_item": data.get(
                "resBusinessItems",
                "",
            ),
        }

    # ==================================================
    # 사업용 신용카드 매입
    # ==================================================

    def get_business_card_purchases(
        self,
        business,
        start_date,
        end_date,
        *,
        two_way_info=None,
        simple_auth=None,
    ):
        """사업용 신용카드 매입 Mock 응답을 반환한다.

        Real Provider와 동일한 2-way 인자를 받지만 Mock에서는
        실제 추가인증을 수행하지 않고 최종 성공 fixture를 반환한다.
        """

        return load_fixture(
            "business_card_purchase_success.json"
        )

    # ==================================================
    # 현금영수증 매출
    # ==================================================

    def get_cash_receipt_sales(
        self,
        business,
        start_date,
        end_date,
        *,
        two_way_info=None,
        simple_auth=None,
    ):
        """현금영수증 매출 Mock 응답을 반환한다."""

        return load_fixture(
            "cash_receipt_sales_success.json"
        )

    # ==================================================
    # 전자세금계산서 매입
    # ==================================================

    def get_tax_invoice_purchases(
        self,
        business,
        start_date,
        end_date,
        *,
        two_way_info=None,
        simple_auth=None,
    ):
        """전자세금계산서 매입 Mock 응답을 반환한다."""

        return load_fixture(
            "tax_invoice_purchase_success.json"
        )

    # ==================================================
    # 전자세금계산서 매출
    # ==================================================

    def get_tax_invoice_sales(
        self,
        business,
        start_date,
        end_date,
        *,
        two_way_info=None,
        simple_auth=None,
    ):
        """전자세금계산서 매출 Mock 응답을 반환한다."""

        return load_fixture(
            "tax_invoice_sales_success.json"
        )

    # ==================================================
    # 신용카드 매출자료
    # ==================================================

    def get_credit_card_sales_summary(
        self,
        business,
        start_date,
        end_date,
    ):
        """신용카드 월별 매출 집계 Mock 응답을 반환한다.

        공동인증서 기반 Real 상품이므로 Transaction Sync의
        카카오 2-way 인자는 사용하지 않는다.
        """

        return load_fixture(
            "credit_card_sales_success.json"
        )

    # ==================================================
    # 기존 인증 응답 Normalizer
    # ==================================================

    @staticmethod
    def _normalize_hometax(raw):
        """HOMETAX Mock 인증 응답을 공통 형식으로 변환한다."""

        code = (
            raw.get("result", {})
            .get("code", "")
        )
        data = raw.get("data", {})

        if code == _AUTH_REQUIRED:
            return {
                "outcome": "AUTH_REQUIRED",
                "continue_2way": True,
                "method":
                    data.get(
                        "method",
                        "",
                    ),
                "job_index":
                    data.get(
                        "jobIndex"
                    ),
                "thread_index":
                    data.get(
                        "threadIndex"
                    ),
                "jti":
                    data.get(
                        "jti",
                        "",
                    ),
                "two_way_timestamp":
                    data.get(
                        "twoWayTimestamp"
                    ),
            }

        if code == _SUCCESS:
            return {
                "outcome": "SUCCESS",
            }

        return {
            "outcome": "FAILURE",
            "error_code": code,
            "error_message":
                raw.get(
                    "result",
                    {},
                ).get(
                    "message",
                    "",
                ),
        }

    @staticmethod
    def _normalize_card(raw):
        """CARD Mock 연결 응답을 공통 형식으로 변환한다."""

        code = (
            raw.get("result", {})
            .get("code", "")
        )

        if code != _SUCCESS:
            return {
                "outcome": "FAILURE",
                "error_code": code,
                "error_message":
                    raw.get(
                        "result",
                        {},
                    ).get(
                        "message",
                        "",
                    ),
            }

        connected_id = (
            raw.get(
                "data",
                {},
            ).get(
                "connectedId",
                "",
            )
        )

        if not connected_id:
            return {
                "outcome": "FAILURE",
                "error_code":
                    "EMPTY_CONNECTED_ID",
                "error_message":
                    "connectedId가 비어 있습니다.",
            }

        return {
            "outcome": "SUCCESS",
            "connected_id": connected_id,
        }