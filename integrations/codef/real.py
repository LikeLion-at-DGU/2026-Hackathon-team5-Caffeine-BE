from .base import BaseCodefProvider


class RealCodefProvider(BaseCodefProvider):
    """실제 CODEF API 연동 Provider.

    실제 응답을 MockProvider와 동일한 내부 형식으로 변환해 반환한다.
    """

    def get_business_status(self, business_number):
        raise NotImplementedError(
            "RealCodefProvider는 아직 구현 전 / CODEF_MODE=mock으로 개발"
        )

    def request_auth(self, business, connection_type):
        raise NotImplementedError

    def retry_auth(self, business, connection):
        raise NotImplementedError