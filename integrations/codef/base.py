from abc import ABC, abstractmethod


class BaseCodefProvider(ABC):
    """CODEF 연동 Provider의 공통 인터페이스.

    Service에서는 CODEF의 실제 응답 구조를 직접 다루지 않고,
    Provider가 정리한 공통 형식만 사용한다.

    MockProvider는 개발용 응답을 반환하고,
    RealProvider는 실제 CODEF 응답을 같은 형식으로 변환한다.
    """

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
    def request_auth(self, business, connection_type):
        """CARD 또는 HOMETAX 연결을 요청한다.

        반환 예시:
        {
            "outcome": "SUCCESS" | "AUTH_REQUIRED" | "FAILURE",
            "connected_id": str,
            "continue_2way": bool,
            "method": str,
            "job_index": int,
            "thread_index": int,
            "jti": str,
            "two_way_timestamp": int,
            "error_code": str,
            "error_message": str,
        }
        """
        raise NotImplementedError

    @abstractmethod
    def retry_auth(self, business, connection):
        """저장된 2-way 정보를 사용해 HOMETAX 인증을 재시도한다."""
        raise NotImplementedError