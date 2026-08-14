from .base import BaseCodefProvider


class MockCodefProvider(BaseCodefProvider):
    """개발 및 테스트용 CODEF Mock Provider."""

    #사업자등록상태
    def get_business_status(self, business_number):
        raise NotImplementedError

    #CODEF 인증 요청
    def request_auth(self, business, connection_type):
        raise NotImplementedError

    #HOMETAX 2-way 인증 재시도
    def retry_auth(self, business, connection):
        raise NotImplementedError