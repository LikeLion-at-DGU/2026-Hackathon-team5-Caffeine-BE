from abc import ABC, abstractmethod


class CodefBusinessAccessError(ValueError):
    """요청 사업장과 CODEF 연결을 안전하게 매핑할 수 없을 때 발생한다."""


class BaseCodefProvider(ABC):
    """CODEF 연동 Provider의 공통 인터페이스.

    Service는 Mock/Real 구현을 구분하지 않고 이 인터페이스를 통해
    CODEF 인증 및 거래 조회 기능을 사용한다.
    """

    @abstractmethod
    def ensure_business_access(self, business, source_type):
        """해당 거래 소스를 조회할 수 있는 CODEF 연결 상태인지 확인한다."""
        raise NotImplementedError

    @abstractmethod
    def get_business_status(self, business_number):
        """사업자등록상태를 조회한다.

        반환 예시:
        {
            "outcome": "SUCCESS" | "FAILURE",
            "company_identity_no": str,
            "business_status": str,
            "taxation_type_code": str,
            "closing_date": str,
            "transfer_tax_type_date": str,
            "error_code": str,
            "error_message": str,
        }
        """
        raise NotImplementedError
    
    @abstractmethod
    def get_business_registration_info(self, business):
        """사업자 등록사항에서 업종 정보를 조회한다.

        반환 예시:
        {
            "outcome": "SUCCESS" | "FAILURE",
            "industry_code": str,
            "business_type": str,
            "business_item": str,
            "error_code": str,
            "error_message": str,
        }
        """
        raise NotImplementedError

    @abstractmethod
    def request_auth(self, business, connection_type):
        """기존 CODEF 연결 인증 요청 인터페이스.

        Transaction Sync 과정에서 발생하는 2-way 추가인증과는 별도로
        기존 codef-auth API에서 사용한다.
        """
        raise NotImplementedError

    @abstractmethod
    def retry_auth(self, business, connection):
        """기존 CODEF 연결 인증 재시도 인터페이스."""
        raise NotImplementedError

    @abstractmethod
    def get_business_card_purchases(
        self,
        business,
        start_date,
        end_date,
        *,
        two_way_info=None,
        simple_auth=None,
    ):
        """사업용 신용카드 매입 원본 응답을 반환한다.

        two_way_info와 simple_auth가 전달되면 동일 상품 endpoint에
        2-way 추가인증 정보를 포함해 재요청한다.
        """
        raise NotImplementedError

    @abstractmethod
    def get_cash_receipt_sales(
        self,
        business,
        start_date,
        end_date,
        *,
        two_way_info=None,
        simple_auth=None,
    ):
        """현금영수증 매출 원본 응답을 반환한다.

        two_way_info와 simple_auth가 전달되면 2-way 재요청으로 처리한다.
        """
        raise NotImplementedError

    @abstractmethod
    def get_tax_invoice_purchases(
        self,
        business,
        start_date,
        end_date,
        *,
        two_way_info=None,
        simple_auth=None,
    ):
        """전자세금계산서 매입 원본 응답을 반환한다.

        two_way_info와 simple_auth가 전달되면 2-way 재요청으로 처리한다.
        """
        raise NotImplementedError

    @abstractmethod
    def get_tax_invoice_sales(
        self,
        business,
        start_date,
        end_date,
        *,
        two_way_info=None,
        simple_auth=None,
    ):
        """전자세금계산서 매출 원본 응답을 반환한다.

        two_way_info와 simple_auth가 전달되면 2-way 재요청으로 처리한다.
        """
        raise NotImplementedError

    @abstractmethod
    def get_credit_card_sales_summary(
        self,
        business,
        start_date,
        end_date,
    ):
        """공동인증서 기반 신용카드 월별 매출 집계 원본 응답을 반환한다."""
        raise NotImplementedError