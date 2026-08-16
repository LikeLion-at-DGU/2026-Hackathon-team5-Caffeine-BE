from rest_framework import status


class ReportServiceError(Exception):
    """reports 서비스 레이어 공통 예외."""
    code = "REPORT_ERROR"
    message = "처리 중 오류가 발생했습니다."
    status_code = status.HTTP_400_BAD_REQUEST


class BusinessNotFound(ReportServiceError):
    code = "BUSINESS_NOT_FOUND"
    message = "사업장을 찾을 수 없습니다."
    status_code = status.HTTP_404_NOT_FOUND


class ReportNotFound(ReportServiceError):
    code = "REPORT_NOT_FOUND"
    message = "리포트를 찾을 수 없습니다."
    status_code = status.HTTP_404_NOT_FOUND


class ReportNotApproved(ReportServiceError):
    code = "REPORT_NOT_APPROVED"
    message = "승인된 리포트만 전송할 수 있습니다."
    status_code = status.HTTP_400_BAD_REQUEST


class ReportFileNotReady(ReportServiceError):
    code = "REPORT_FILE_NOT_READY"
    message = "아직 생성된 파일이 없습니다."
    status_code = status.HTTP_400_BAD_REQUEST


class TaxAccountantEmailNotSet(ReportServiceError):
    code = "TAX_ACCOUNTANT_EMAIL_NOT_SET"
    message = "세무사 이메일이 등록되어 있지 않습니다."
    status_code = status.HTTP_400_BAD_REQUEST


class InvalidReportPeriod(ReportServiceError):
    code = "INVALID_YEAR_MONTH"
    message = "보고서 대상 월은 YYYY-MM 형식이어야 합니다."
    status_code = status.HTTP_400_BAD_REQUEST


class InvalidReportFileType(ReportServiceError):
    code = "INVALID_REPORT_FILE_TYPE"
    message = "보고서 파일 형식은 csv 또는 pdf만 지원합니다."
    status_code = status.HTTP_400_BAD_REQUEST


class MonthlyCloseRequired(ReportServiceError):
    code = "MONTHLY_CLOSE_REQUIRED"
    message = "월 마감 승인 후 보고서를 생성할 수 있습니다."
    status_code = status.HTTP_409_CONFLICT
