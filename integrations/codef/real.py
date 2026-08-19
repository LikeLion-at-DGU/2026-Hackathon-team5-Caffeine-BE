import base64
import os
from pathlib import Path

import requests

from businesses.models import CodefConnection

from .base import BaseCodefProvider, CodefBusinessAccessError
from .client import (
    CodefClient,
    CodefClientError,
    build_two_way_payload,
    encrypt_with_public_key,
)


class RealCodefProvider(BaseCodefProvider):
    """실제 CODEF API 연동 Provider."""

    SOURCE_CONNECTION_TYPES = {
        # 현재 Real 연동에서 사용하는 사업용카드 매입 API는
        # 홈택스(현금영수증 사업용 신용카드 매입세액 조회) 상품이다.
        "CARD_PURCHASE": "HOMETAX",
        "CASH_RECEIPT_PURCHASE": "HOMETAX",
        "CASH_RECEIPT_SALE": "HOMETAX",
        "TAX_INVOICE": "HOMETAX",
        "CREDIT_CARD_SALES_SUMMARY": "HOMETAX",
    }

    # --------------------------------------------------
    # 사업자등록상태
    # --------------------------------------------------

    BUSINESS_STATUS_ORGANIZATION = "0004"
    BUSINESS_STATUS_PATH = "/v1/kr/public/nt/business/status"
    BUSINESS_STATUS_SUCCESS_CODE = "CF-00000"

    # --------------------------------------------------
    # 현금영수증 매출
    # --------------------------------------------------

    CASH_RECEIPT_SALES_ORGANIZATION = "0003"
    CASH_RECEIPT_SALES_PATH = (
        "/v1/kr/public/nt/cash-receipt/sales-details"
    )

    # --------------------------------------------------
    # 전자세금계산서 통합
    # --------------------------------------------------

    TAX_INVOICE_ORGANIZATION = "0002"
    TAX_INVOICE_PATH = (
        "/v1/kr/public/nt/tax-invoice/integrated-check-list"
    )

    # --------------------------------------------------
    # 사업용 신용카드 매입
    # --------------------------------------------------

    BUSINESS_CARD_PURCHASE_ORGANIZATION = "0003"
    BUSINESS_CARD_PURCHASE_PATH = (
        "/v1/kr/public/nt/cash-receipt/"
        "deduction-of-business-credit-card-purchase-amount"
    )

    # --------------------------------------------------
    # 신용카드 매출자료
    # --------------------------------------------------

    CREDIT_CARD_SALES_ORGANIZATION = "0006"
    CREDIT_CARD_SALES_PATH = (
        "/v1/kr/public/nt/tax-payment/"
        "credit-card-sales-data-list"
    )

    # --------------------------------------------------
    # 공통
    # --------------------------------------------------

    SUCCESS_CODE = "CF-00000"

    def __init__(self, client=None):
        self.client = client or CodefClient()

    # ==================================================
    # 공통 Helper
    # ==================================================

    @staticmethod
    def _digits(value):
        """숫자만 남긴다."""
        return "".join(
            character
            for character in str(value or "")
            if character.isdigit()
        )

    @classmethod
    def _format_yyyymmdd(cls, value):
        """date 또는 문자열을 YYYYMMDD 형식으로 변환한다."""

        if hasattr(value, "strftime"):
            return value.strftime("%Y%m%d")

        text = cls._digits(value)

        if len(text) != 8:
            raise CodefBusinessAccessError(
                f"날짜는 YYYYMMDD 형식이어야 합니다: {value!r}"
            )

        return text

    @classmethod
    def _format_yyyymm(cls, value):
        """date 또는 문자열을 YYYYMM 형식으로 변환한다."""

        if hasattr(value, "strftime"):
            return value.strftime("%Y%m")

        text = cls._digits(value)

        # YYYYMMDD가 들어와도 앞 6자리 사용
        if len(text) == 8:
            text = text[:6]

        if len(text) != 6:
            raise CodefBusinessAccessError(
                f"월은 YYYYMM 형식이어야 합니다: {value!r}"
            )

        return text

    @classmethod
    def _same_month(cls, start_date, end_date):
        return (
            cls._format_yyyymm(start_date)
            == cls._format_yyyymm(end_date)
        )

    @classmethod
    def _format_year(cls, value):
        """date 또는 문자열에서 YYYY를 반환한다."""

        if hasattr(value, "strftime"):
            return value.strftime("%Y")

        text = cls._digits(value)

        if len(text) not in {6, 8}:
            raise CodefBusinessAccessError(
                f"날짜는 YYYYMM 또는 YYYYMMDD 형식이어야 합니다: {value!r}"
            )

        return text[:4]

    @classmethod
    def _format_quarter(cls, value):
        """date 또는 문자열을 분기 번호(1~4)로 변환한다."""

        if hasattr(value, "strftime"):
            month = int(value.strftime("%m"))
        else:
            text = cls._digits(value)

            if len(text) in {6, 8}:
                month = int(text[4:6])
            else:
                raise CodefBusinessAccessError(
                    "신용카드 매출자료 조회 날짜는 "
                    f"YYYYMM 또는 YYYYMMDD 형식이어야 합니다: {value!r}"
                )

        if not 1 <= month <= 12:
            raise CodefBusinessAccessError(
                f"올바르지 않은 월입니다: {value!r}"
            )

        return str(((month - 1) // 3) + 1)

    @staticmethod
    def _read_base64_file(file_path, label):
        """로컬 인증서 파일을 읽어 Base64 문자열로 변환한다.

        CODEF_PROBE_CERT_FILE / CODEF_PROBE_KEY_FILE은 인증서 파일
        "경로"를 가리킨다. (.env에 인코딩된 문자열을 직접 붙여넣지 않는다.
        인증서가 갱신될 때 파일 경로는 그대로 두고 파일만 교체하면 되도록
        하기 위함이다.)
        """

        if not file_path:
            raise CodefBusinessAccessError(
                f"{label} 경로가 설정되지 않았습니다."
            )

        path = Path(file_path)

        if not path.exists():
            raise CodefBusinessAccessError(
                f"{label} 파일을 찾을 수 없습니다: {path}"
            )

        try:
            raw_bytes = path.read_bytes()
        except OSError as exc:
            raise CodefBusinessAccessError(
                f"{label} 파일을 읽을 수 없습니다: {exc}"
            ) from exc

        return base64.b64encode(raw_bytes).decode("ascii")

    def _get_credit_card_sales_certificate_fields(self):
        """신용카드 매출자료 조회용 공동인증서 필드를 조립한다.

        CODEF 명세상 이 상품은 간편인증 loginType을 사용하지 않고
        certFile / certPassword / certType을 직접 받는다.

        certFile / keyFile은 CODEF_PROBE_CERT_FILE / CODEF_PROBE_KEY_FILE
        경로의 실제 인증서 파일을 읽어 Base64로 인코딩한 값을 사용한다.
        """

        cert_file_path = os.environ.get(
            "CODEF_PROBE_CERT_FILE",
            "",
        ).strip()
        key_file_path = os.environ.get(
            "CODEF_PROBE_KEY_FILE",
            "",
        ).strip()
        cert_password = os.environ.get(
            "CODEF_PROBE_CERT_PASSWORD",
            "",
        ).strip()
        cert_type = os.environ.get(
            "CODEF_PROBE_CERT_TYPE",
            "1",
        ).strip()

        if not cert_password:
            raise CodefBusinessAccessError(
                "CODEF_PROBE_CERT_PASSWORD가 설정되지 않았습니다."
            )

        if cert_type not in {"1", "pfx"}:
            raise CodefBusinessAccessError(
                "CODEF_PROBE_CERT_TYPE은 신용카드 매출자료 명세 기준 "
                "'1'(der/key) 또는 'pfx'여야 합니다."
            )

        cert_file = self._read_base64_file(
            cert_file_path,
            "certFile",
        )

        try:
            encrypted_password = encrypt_with_public_key(
                cert_password
            )
        except CodefClientError as exc:
            raise CodefBusinessAccessError(
                f"공동인증서 비밀번호 RSA 암호화에 실패했습니다: {exc}"
            ) from exc

        fields = {
            "certFile": cert_file,
            "certPassword": encrypted_password,
            "certType": cert_type,
        }

        if cert_type == "1":
            fields["keyFile"] = self._read_base64_file(
                key_file_path,
                "keyFile",
            )

        # CODEF 문서상 선택 입력값. 필요한 경우에만 전송한다.
        optional_env_fields = {
            "deptUserId": "CODEF_PROBE_DEPT_USER_ID",
            "deptUserPass": "CODEF_PROBE_DEPT_USER_PASS",
            "loginIdentity": "CODEF_PROBE_CARD_SALES_LOGIN_IDENTITY",
            "manageNo": "CODEF_PROBE_MANAGE_NO",
            "managePass": "CODEF_PROBE_MANAGE_PASS",
        }

        for field_name, env_name in optional_env_fields.items():
            value = os.environ.get(env_name, "").strip()
            if value:
                fields[field_name] = value

        return fields

    def _post_maybe_two_way(
        self,
        path,
        payload,
        *,
        two_way_info=None,
        simple_auth=None,
    ):
        """CODEF 거래 조회의 1차 요청 또는 2-way 재요청을 수행한다.

        two_way_info와 simple_auth가 전달되면 기존 payload에
        simpleAuth / is2Way / twoWayInfo를 추가해 동일 endpoint로 재요청한다.

        CODEF 2-way는 별도의 인증 API를 호출하는 방식이 아니라,
        인증이 발생한 거래 상품을 동일 endpoint로 다시 요청하는 구조다.
        """

        if two_way_info is not None and simple_auth is not None:
            payload = build_two_way_payload(
                payload,
                two_way_info,
                simple_auth=simple_auth,
            )

        return self.client.post(path, payload)

    def _get_hometax_simple_auth_fields(
        self,
        business,
        *,
        include_identity=True,
    ):
        """홈택스 카카오 간편인증 입력값을 조립한다.

        userName / phoneNo / loginIdentity는 로컬 환경변수에서 가져온다.

        identity는 별도 환경변수보다 Business.business_number를 우선한다.
        즉 실제 조회 대상 사업자번호와 payload의 사업자번호가 어긋나는 것을
        방지한다.
        """

        user_name = os.environ.get(
            "CODEF_PROBE_USER_NAME",
            "",
        ).strip()

        phone_no = os.environ.get(
            "CODEF_PROBE_PHONE_NO",
            "",
        ).strip()

        login_identity = os.environ.get(
            "CODEF_PROBE_LOGIN_IDENTITY",
            "",
        ).strip()

        if not user_name:
            raise CodefBusinessAccessError(
                "CODEF_PROBE_USER_NAME이 설정되지 않았습니다."
            )

        if not phone_no:
            raise CodefBusinessAccessError(
                "CODEF_PROBE_PHONE_NO가 설정되지 않았습니다."
            )

        if not login_identity:
            raise CodefBusinessAccessError(
                "CODEF_PROBE_LOGIN_IDENTITY가 설정되지 않았습니다."
            )

        if not (
            login_identity.isdigit()
            and len(login_identity) == 8
        ):
            raise CodefBusinessAccessError(
                "CODEF_PROBE_LOGIN_IDENTITY는 "
                "생년월일 8자리(YYYYMMDD)여야 합니다."
            )

        fields = {
            "userName": user_name,
            "phoneNo": phone_no,
            "loginIdentity": login_identity,
        }

        if include_identity:
            business_number = self._digits(
                business.business_number
            )

            # DB 사업자번호가 없을 경우에만
            # 기존 probe 환경변수를 fallback으로 사용한다.
            if not business_number:
                business_number = self._digits(
                    os.environ.get(
                        "CODEF_PROBE_IDENTITY",
                        "",
                    )
                )

            if business_number:
                fields["identity"] = business_number

        return fields

    # ==================================================
    # CODEF 연결 상태 확인
    # ==================================================

    def ensure_business_access(
        self,
        business,
        source_type,
    ):
        """거래 조회에 필요한 CODEF 계정 연결 여부를 확인한다."""

        connection_type = self.SOURCE_CONNECTION_TYPES.get(
            source_type
        )

        if connection_type is None:
            raise CodefBusinessAccessError(
                "지원하지 않는 CODEF 거래 소스입니다: "
                f"{source_type}"
            )

        if not CodefConnection.objects.filter(
            business=business,
            connection_type=connection_type,
            status="CONNECTED",
        ).exists():
            raise CodefBusinessAccessError(
                f"이 사업장에 연결된 "
                f"{connection_type} CODEF 계정이 없습니다."
            )

    # ==================================================
    # 사업자등록상태
    # ==================================================

    def get_business_status(
        self,
        business_number,
    ):
        """사업자등록상태를 조회하고 내부 공통 형식으로 반환한다."""

        try:
            raw = self.client.post(
                self.BUSINESS_STATUS_PATH,
                {
                    "organization":
                        self.BUSINESS_STATUS_ORGANIZATION,

                    "reqIdentityList": [
                        {
                            "reqIdentity":
                                business_number,
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
    def _normalize_business_status(
        cls,
        raw,
        business_number,
    ):
        """CODEF 응답을 Business 서비스에서 사용하는 형식으로 변환한다."""

        result = raw.get("result") or {}
        top_code = result.get(
            "code",
            "",
        )

        # 전체 요청 실패
        if (
            top_code
            != cls.BUSINESS_STATUS_SUCCESS_CODE
        ):
            return {
                "outcome": "FAILURE",
                "error_code":
                    top_code or "UNKNOWN",
                "error_message":
                    result.get(
                        "message",
                        "",
                    ),
            }

        data = raw.get(
            "data"
        ) or []

        if not isinstance(
            data,
            list,
        ):
            data = [data]

        item = next(
            (
                row
                for row in data
                if (
                    isinstance(
                        row,
                        dict,
                    )
                    and row.get(
                        "resCompanyIdentityNo"
                    )
                    == business_number
                )
            ),
            None,
        )

        if item is None:
            return {
                "outcome": "FAILURE",
                "error_code":
                    "BUSINESS_NOT_FOUND_IN_RESPONSE",
                "error_message": (
                    "CODEF 응답에서 요청한 "
                    "사업자번호를 찾을 수 없습니다."
                ),
            }

        item_code = item.get(
            "code",
            top_code,
        )

        if (
            item_code
            != cls.BUSINESS_STATUS_SUCCESS_CODE
        ):
            return {
                "outcome": "FAILURE",
                "error_code":
                    item_code or "UNKNOWN",
                "error_message":
                    item.get(
                        "message",
                        result.get(
                            "message",
                            "",
                        ),
                    ),
            }

        return {
            "outcome": "SUCCESS",

            "company_identity_no":
                item.get(
                    "resCompanyIdentityNo",
                    "",
                ),

            "business_status":
                item.get(
                    "resBusinessStatus",
                    "",
                ),

            "taxation_type_code":
                item.get(
                    "resTaxationTypeCode",
                    "",
                ),

            "closing_date":
                item.get(
                    "resClosingDate",
                    "",
                ),

            "transfer_tax_type_date":
                item.get(
                    "resTransferTaxTypeDate",
                    "",
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
        """기존 codef-auth API용 연결 인증 인터페이스.

        Transaction Sync 과정에서 발생하는 거래별 2-way 추가인증과는
        별도의 흐름이다.
        """
        raise NotImplementedError(
            "Real CODEF 공통 인증 요청은 "
            "아직 별도 구현되지 않았습니다."
        )

    def retry_auth(
        self,
        business,
        connection,
    ):
        """기존 codef-auth API용 연결 인증 재시도 인터페이스."""
        raise NotImplementedError(
            "Real CODEF 공통 인증 재시도는 "
            "아직 별도 구현되지 않았습니다."
        )

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
        """사업용 신용카드 매입 원본 CODEF 응답을 반환한다.

        최초 호출에서는 카카오 간편인증을 포함한 1차 요청을 수행한다.
        two_way_info와 simple_auth가 전달되면 동일 상품의 2-way 재요청을
        수행한다.

        이 상품은 월 단위 조회이므로 start_date와 end_date는
        같은 월이어야 한다.
        """

        if not self._same_month(
            start_date,
            end_date,
        ):
            raise CodefBusinessAccessError(
                "사업용 신용카드 매입 Real 조회는 "
                "현재 월 단위 조회만 지원합니다. "
                "start_date와 end_date를 동일한 월로 지정하세요."
            )

        auth_fields = (
            self._get_hometax_simple_auth_fields(
                business,
                include_identity=False,
            )
        )

        payload = {
            "organization":
                self.BUSINESS_CARD_PURCHASE_ORGANIZATION,

            # 회원 간편인증
            "loginType": "5",

            # 카카오톡
            "loginTypeLevel": "1",

            **auth_fields,

            # 월별 조회
            "searchType": "1",

            # YYYYMM
            "startDate":
                self._format_yyyymm(
                    start_date
                ),

            # 전체
            "inquiryType": "0",

            # 카드정보 포함
            "detailYN": "1",
        }

        return self._post_maybe_two_way(
            self.BUSINESS_CARD_PURCHASE_PATH,
            payload,
            two_way_info=two_way_info,
            simple_auth=simple_auth,
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
        """현금영수증 매출 원본 CODEF 응답을 반환한다.

        two_way_info와 simple_auth가 전달되면 동일 상품 endpoint로
        2-way 추가인증 재요청을 수행한다.
        """

        auth_fields = (
            self._get_hometax_simple_auth_fields(
                business,
                include_identity=True,
            )
        )

        payload = {
            "organization":
                self.CASH_RECEIPT_SALES_ORGANIZATION,

            # 회원 간편인증
            "loginType": "5",

            # 카카오톡
            "loginTypeLevel": "1",

            **auth_fields,

            "startDate":
                self._format_yyyymmdd(
                    start_date
                ),

            "endDate":
                self._format_yyyymmdd(
                    end_date
                ),

            # CODEF 실호출에서 명시하지 않으면
            # CF-12411 / SEQ_ORDER 문제가 발생했던 값
            "orderBy": "0",
        }

        return self._post_maybe_two_way(
            self.CASH_RECEIPT_SALES_PATH,
            payload,
            two_way_info=two_way_info,
            simple_auth=simple_auth,
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
        """전자세금계산서 매입 원본 CODEF 응답을 반환한다.

        transeType="02"로 매입 자료를 조회한다.
        two_way_info와 simple_auth가 전달되면 동일 조회 조건으로
        2-way 추가인증 재요청을 수행한다.
        """

        auth_fields = (
            self._get_hometax_simple_auth_fields(
                business,
                include_identity=True,
            )
        )

        payload = {
            "organization":
                self.TAX_INVOICE_ORGANIZATION,

            # 회원 간편인증
            "loginType": "5",

            # 카카오톡
            "loginTypeLevel": "1",

            **auth_fields,

            # 전자세금계산서
            "inquiryType": "01",

            # 작성일자 기준
            "searchType": "01",

            "startDate":
                self._format_yyyymmdd(
                    start_date
                ),

            "endDate":
                self._format_yyyymmdd(
                    end_date
                ),

            # 작성일자 정렬
            "sortby": "1",

            # 최신순
            "orderBy": "0",

            # 매입
            "transeType": "02",

            # 기존 조회 방식
            "type": "0",

            # 페이징
            "startPageNo": "1",
            "pageCount": "40",
        }

        return self._post_maybe_two_way(
            self.TAX_INVOICE_PATH,
            payload,
            two_way_info=two_way_info,
            simple_auth=simple_auth,
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
        """전자세금계산서 매출 원본 CODEF 응답을 반환한다.

        transeType="01"로 매출 자료를 조회한다.
        two_way_info와 simple_auth가 전달되면 동일 조회 조건으로
        2-way 추가인증 재요청을 수행한다.
        """

        auth_fields = (
            self._get_hometax_simple_auth_fields(
                business,
                include_identity=True,
            )
        )

        payload = {
            "organization":
                self.TAX_INVOICE_ORGANIZATION,

            # 회원 간편인증
            "loginType": "5",

            # 카카오톡
            "loginTypeLevel": "1",

            **auth_fields,

            # 전자세금계산서
            "inquiryType": "01",

            # 작성일자 기준
            "searchType": "01",

            "startDate":
                self._format_yyyymmdd(
                    start_date
                ),

            "endDate":
                self._format_yyyymmdd(
                    end_date
                ),

            # 작성일자 정렬
            "sortby": "1",

            # 최신순
            "orderBy": "0",

            # 매출
            "transeType": "01",

            # 기존 조회 방식
            "type": "0",

            # 페이징
            "startPageNo": "1",
            "pageCount": "40",
        }

        return self._post_maybe_two_way(
            self.TAX_INVOICE_PATH,
            payload,
            two_way_info=two_way_info,
            simple_auth=simple_auth,
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
        """공동인증서 기반 신용카드 월별 매출자료를 조회한다.

        CODEF 명세 기준:
        - organization="0006"
        - certFile / certPassword / certType 사용
        - year=YYYY
        - startDate / endDate는 조회 분기("1"~"4")

        카카오 간편인증 상품이 아니므로 Transaction Sync의
        2-way 추가인증 흐름을 사용하지 않는다.

        API 입력에 사업자번호(identity)가 없어 business는
        Provider 인터페이스 호환을 위해서만 전달받는다.
        """

        start_year = self._format_year(start_date)
        end_year = self._format_year(end_date)

        if start_year != end_year:
            raise CodefBusinessAccessError(
                "신용카드 매출자료 Real 조회는 CODEF 명세상 year를 하나만 "
                "전송하므로 연도를 넘겨 조회할 수 없습니다. "
                "start_date와 end_date를 같은 연도로 지정하세요."
            )

        start_quarter = self._format_quarter(start_date)
        end_quarter = self._format_quarter(end_date)

        if int(start_quarter) > int(end_quarter):
            raise CodefBusinessAccessError(
                "신용카드 매출자료 조회 시작 분기가 종료 분기보다 늦습니다."
            )

        certificate_fields = (
            self._get_credit_card_sales_certificate_fields()
        )

        payload = {
            "organization":
                self.CREDIT_CARD_SALES_ORGANIZATION,

            **certificate_fields,

            "year": start_year,
            "startDate": start_quarter,
            "endDate": end_quarter,
        }

        return self.client.post(
            self.CREDIT_CARD_SALES_PATH,
            payload,
        )