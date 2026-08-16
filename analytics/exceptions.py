class AnalyticsServiceError(Exception):
    code = "ANALYTICS_ERROR"
    message = "처리 중 오류가 발생했습니다."


class AlreadyClosed(AnalyticsServiceError):
    code = "ALREADY_CLOSED"
    message = "이미 마감 승인된 월입니다."


class MonthlyCloseRequired(AnalyticsServiceError):
    code = "MONTHLY_CLOSE_REQUIRED"
    message = "장부 마감 승인 이후 다운로드할 수 있습니다."