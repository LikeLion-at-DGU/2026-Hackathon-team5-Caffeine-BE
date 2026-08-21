from abc import ABC, abstractmethod


class BasePaymentGateway(ABC):
    """목업과 실제 PG 구현이 공유하는 결제 인터페이스."""

    @abstractmethod
    def issue_billing_key(self, payment_token: str) -> dict:
        """PG 임시 토큰을 정기 결제용 빌링키로 교환한다.

        Args:
            payment_token: PG SDK에서 발급한 일회성 결제 토큰.

        Returns:
            빌링키와 카드 표시 정보.
        """
        pass

    @abstractmethod
    def charge(self, billing_key: str, amount: int) -> dict:
        """저장된 빌링키로 정기 결제를 요청한다.

        Args:
            billing_key: PG에서 발급한 정기 결제 키.
            amount: 결제 금액.

        Returns:
            결제 성공 여부와 거래 정보.
        """
        pass
