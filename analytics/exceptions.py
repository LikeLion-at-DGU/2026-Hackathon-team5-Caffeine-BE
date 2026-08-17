class AnalyticsServiceError(Exception):
    code = "ANALYTICS_ERROR"
    message = "처리 중 오류가 발생했습니다."


class AlreadyClosed(AnalyticsServiceError):
    code = "ALREADY_CLOSED"
    message = "이미 마감 승인된 월입니다."


class CloseNotReady(AnalyticsServiceError):
    code = "MONTHLY_CLOSE_NOT_READY"
    message = "공제 검토 또는 사업자 과세유형을 먼저 확인해주세요."
