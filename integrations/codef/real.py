import requests

from businesses.models import CodefConnection

from .base import BaseCodefProvider, CodefBusinessAccessError
from .client import CodefClient, CodefClientError


class RealCodefProvider(BaseCodefProvider):
    """실제 CODEF API 연동 Provider."""

    SOURCE_CONNECTION_TYPES = {
        "CARD_PURCHASE": "CARD",
        "CASH_RECEIPT_PURCHASE": "HOMETAX",
        "CASH_RECEIPT_SALE": "HOMETAX",
        "TAX_INVOICE": "HOMETAX",
        "CREDIT_CARD_SALES_SUMMARY": "HOMETAX",
    }

    # 사업자등록상태 조회 API
    BUSINESS_STATUS_ORGANIZATION = "0004"
    BUSINESS_STATUS_PATH = "/v1/kr/public/nt/business/status"
    BUSINESS_STATUS_SUCCESS_CODE = "CF-00000"

    def __init__(self, client=None):
        self.client = client or CodefClient()

    def ensure_business_access(self, business, source_type):
        """거래 조회에 필요한 CODEF 계정 연결 여부를 확인한다."""

        connection_type = self.SOURCE_CONNECTION_TYPES.get(source_type)

        if connection_type is None:
            raise CodefBusinessAccessError(
                f"지원하지 않는 CODEF 거래 소스입니다: {source_type}"
            )

        if not CodefConnection.objects.filter(
            business=business,
            connection_type=connection_type,
            status="CONNECTED",
        ).exists():
            raise CodefBusinessAccessError(
                f"이 사업장에 연결된 {connection_type} CODEF 계정이 없습니다."
            )

    def get_business_status(self, business_number):
        """사업자등록상태를 조회하고 내부 공통 형식으로 반환한다."""

        try:
            raw = self.client.post(
                self.BUSINESS_STATUS_PATH,
                {
                    "organization": self.BUSINESS_STATUS_ORGANIZATION,
                    "reqIdentityList": [
                        {
                            "reqIdentity": business_number,
                        }
                    ],
                },
            )

        except CodefClientError as exc:
            return {
                "outcome": "FAILURE",
                "error_code": "CODEF_CLIENT_ERROR",
                "error_message": str(exc),
            }

        except requests.exceptions.RequestException as exc:
            return {
                "outcome": "FAILURE",
                "error_code": "CODEF_HTTP_ERROR",
                "error_message": str(exc),
            }

        return self._normalize_business_status(
            raw,
            business_number,
        )

    @classmethod
    def _normalize_business_status(cls, raw, business_number):
        """CODEF 응답을 Business 서비스에서 사용하는 형식으로 변환한다."""

        result = raw.get("result") or {}
        top_code = result.get("code", "")

        # 전체 요청 실패
        if top_code != cls.BUSINESS_STATUS_SUCCESS_CODE:
            return {
                "outcome": "FAILURE",
                "error_code": top_code or "UNKNOWN",
                "error_message": result.get("message", ""),
            }

        data = raw.get("data") or []

        if not isinstance(data, list):
            data = [data]

        # 요청한 사업자번호와 정확히 일치하는 응답만 사용한다.
        item = next(
            (
                row
                for row in data
                if isinstance(row, dict)
                and row.get("resCompanyIdentityNo") == business_number
            ),
            None,
        )

        if item is None:
            return {
                "outcome": "FAILURE",
                "error_code": "BUSINESS_NOT_FOUND_IN_RESPONSE",
                "error_message": (
                    "CODEF 응답에서 요청한 사업자번호를 찾을 수 없습니다."
                ),
            }

        # 전체 요청은 성공해도 개별 사업자 조회는 실패할 수 있다.
        item_code = item.get("code", top_code)

        if item_code != cls.BUSINESS_STATUS_SUCCESS_CODE:
            return {
                "outcome": "FAILURE",
                "error_code": item_code or "UNKNOWN",
                "error_message": item.get(
                    "message",
                    result.get("message", ""),
                ),
            }

        return {
            "outcome": "SUCCESS",
            "company_identity_no": item.get(
                "resCompanyIdentityNo",
                "",
            ),
            "business_status": item.get(
                "resBusinessStatus",
                "",
            ),
            "taxation_type_code": item.get(
                "resTaxationTypeCode",
                "",
            ),
            "closing_date": item.get(
                "resClosingDate",
                "",
            ),
            "transfer_tax_type_date": item.get(
                "resTransferTaxTypeDate",
                "",
            ),
        }

    def request_auth(self, business, connection_type):
        raise NotImplementedError

    def retry_auth(self, business, connection):
        raise NotImplementedError

    def get_business_card_purchases(
        self,
        business,
        start_date,
        end_date,
    ):
        raise NotImplementedError(
            "실제 사업용 신용카드 매입 조회는 아직 구현되지 않았습니다."
        )

    def get_cash_receipt_sales(
        self,
        business,
        start_date,
        end_date,
    ):
        raise NotImplementedError(
            "실제 현금영수증 매출 조회는 아직 구현되지 않았습니다."
        )

    def get_tax_invoice_purchases(
        self,
        business,
        start_date,
        end_date,
    ):
        raise NotImplementedError(
            "실제 전자세금계산서 매입 조회는 아직 구현되지 않았습니다."
        )

    def get_tax_invoice_sales(
        self,
        business,
        start_date,
        end_date,
    ):
        raise NotImplementedError(
            "실제 전자세금계산서 매출 조회는 아직 구현되지 않았습니다."
        )

    def get_credit_card_sales_summary(
        self,
        business,
        start_date,
        end_date,
    ):
        raise NotImplementedError(
            "실제 신용카드 월별 매출자료 조회는 아직 구현되지 않았습니다."
        )