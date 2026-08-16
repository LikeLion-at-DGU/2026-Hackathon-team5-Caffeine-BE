from abc import ABC, abstractmethod


class BasePaymentGateway(ABC):
    """결제대행사(PG) 연동 공통 인터페이스.

    Mock/Real 구현이 이 인터페이스만 따르면, factory에서 무엇을 반환하든
    호출부(서비스 레이어)는 어떤 구현체인지 신경 쓰지 않아도 된다.
    """

    @abstractmethod
    def issue_billing_key(self, payment_token: str) -> dict:
        """프론트에서 PG SDK로 발급받은 임시 토큰을 받아, 정기결제용 빌링키를 발급.

        Returns:
            {"billing_key": str, "card_company": str, "card_last4": str}
        """
        pass

    @abstractmethod
    def charge(self, billing_key: str, amount: int) -> dict:
        """빌링키로 결제 실행.

        Returns:
            {"success": bool, "transaction_id": str, "charged_at": str}
        """
        pass