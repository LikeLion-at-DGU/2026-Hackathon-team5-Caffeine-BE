from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from businesses.models import Business
from core.responses import error_response, success_response
from reports.exceptions import ReportServiceError
from reports.serializers import ReportSerializer
from reports.services import report_service


def _error_response(code: str, message: str, http_status: int, errors: dict | None = None) -> Response:
    return error_response(
        code=code,
        message=message,
        errors=errors,
        status=http_status,
    )


def _check_business(request, business_id: int):
    if not request.user or not request.user.is_authenticated:
        return _error_response(
            "UNAUTHORIZED",
            "인증 자격 증명이 제공되지 않았습니다.",
            status.HTTP_401_UNAUTHORIZED,
        )
    business = Business.objects.filter(pk=business_id).first()
    if not business:
        return _error_response(
            "BUSINESS_NOT_FOUND",
            "사업장을 찾을 수 없습니다.",
            status.HTTP_404_NOT_FOUND,
        )
    if business.owner_id is not None and business.owner_id != request.user.id:
        return _error_response(
            "FORBIDDEN_BUSINESS_ACCESS",
            "해당 사업장에 대한 접근 권한이 없습니다.",
            status.HTTP_403_FORBIDDEN,
        )
    return None


class ReportDetailView(APIView):
    def get(self, request, business_id, year_month):
        if err := _check_business(request, business_id):
            return err
        try:
            report = report_service.get_report(business_id, year_month)
        except ReportServiceError as e:
            return _error_response(e.code, e.message, e.status_code)

        return success_response(
            code="REPORT_DETAIL_SUCCESS",
            message="리포트 현황을 조회했습니다.",
            data=ReportSerializer(report).data,
        )


class ReportGenerateView(APIView):
    def post(self, request, business_id, year_month):
        if err := _check_business(request, business_id):
            return err
        try:
            report = report_service.generate_report(business_id, year_month)
        except ReportServiceError as e:
            return _error_response(e.code, e.message, e.status_code)

        return success_response(
            code="REPORT_GENERATE_SUCCESS",
            message="리포트를 생성했습니다.",
            data=ReportSerializer(report).data,
        )


class ReportDownloadView(APIView):
    def get(self, request, business_id, year_month):
        if err := _check_business(request, business_id):
            return err
        file_type = request.query_params.get("type", "pdf")
        try:
            file_field = report_service.get_report_file(business_id, year_month, file_type)
        except ReportServiceError as e:
            return _error_response(e.code, e.message, e.status_code)

        content_type = "text/csv" if file_type == "csv" else "application/pdf"
        file_field.open("rb")
        try:
            file_content = file_field.read()
        finally:
            file_field.close()
        response = HttpResponse(file_content, content_type=content_type)
        filename = file_field.name.split("/")[-1]
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class ReportApproveView(APIView):
    def post(self, request, business_id, year_month):
        if err := _check_business(request, business_id):
            return err
        try:
            report = report_service.approve_report(business_id, year_month)
        except ReportServiceError as e:
            return _error_response(e.code, e.message, e.status_code)

        return success_response(
            code="REPORT_APPROVE_SUCCESS",
            message="리포트를 승인했습니다.",
            data=ReportSerializer(report).data,
        )


class ReportSendEmailView(APIView):
    def post(self, request, business_id, year_month):
        if err := _check_business(request, business_id):
            return err
        try:
            report = report_service.send_report_email(business_id, year_month)
        except ReportServiceError as e:
            return _error_response(e.code, e.message, e.status_code)

        return success_response(
            code="REPORT_SEND_EMAIL_SUCCESS",
            message="세무사에게 자료를 전송했습니다.",
            data=ReportSerializer(report).data,
        )
