class SettingsServiceError(Exception):
    """settings 서비스 레이어 공통 예외."""
    code = "SETTINGS_ERROR"
    message = "처리 중 오류가 발생했습니다."


class SubscriptionNotFound(SettingsServiceError):
    code = "SUBSCRIPTION_NOT_FOUND"
    message = "구독 정보를 찾을 수 없습니다."


class AlreadyCancelled(SettingsServiceError):
    code = "ALREADY_CANCELLED"
    message = "이미 취소된 구독입니다."


class PaymentMethodUpdateFailed(SettingsServiceError):
    code = "PAYMENT_METHOD_UPDATE_FAILED"
    message = "결제수단 변경에 실패했습니다."