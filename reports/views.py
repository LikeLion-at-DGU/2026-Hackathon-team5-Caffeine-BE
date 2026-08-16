from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from reports.exceptions import ReportServiceError
from reports.serializers import ReportSerializer
from reports.services import report_service


def _error_response(code: str, message: str, http_status: int, errors: dict | None = None) -> Response:
    return Response(
        {"success": False, "code": code, "message": message, "errors": errors or {}},
        status=http_status,
    )


class ReportDetailView(APIView):
    def get(self, request, business_id, year_month):
        try:
            report = report_service.get_report(business_id, year_month)
        except ReportServiceError as e:
            return _error_response(e.code, e.message, e.status_code)

        return Response({
            "success": True,
            "code": "REPORT_DETAIL_SUCCESS",
            "message": "리포트 현황을 조회했습니다.",
            "data": ReportSerializer(report).data,
        })


class ReportGenerateView(APIView):
    def post(self, request, business_id, year_month):
        try:
            report = report_service.generate_report(business_id, year_month)
        except ReportServiceError as e:
            return _error_response(e.code, e.message, e.status_code)

        return Response({
            "success": True,
            "code": "REPORT_GENERATE_SUCCESS",
            "message": "리포트를 생성했습니다.",
            "data": ReportSerializer(report).data,
        })


class ReportDownloadView(APIView):
    def get(self, request, business_id, year_month):
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
        try:
            report = report_service.approve_report(business_id, year_month)
        except ReportServiceError as e:
            return _error_response(e.code, e.message, e.status_code)

        return Response({
            "success": True,
            "code": "REPORT_APPROVE_SUCCESS",
            "message": "리포트를 승인했습니다.",
            "data": ReportSerializer(report).data,
        })


class ReportSendEmailView(APIView):
    def post(self, request, business_id, year_month):
        try:
            report = report_service.send_report_email(business_id, year_month)
        except ReportServiceError as e:
            return _error_response(e.code, e.message, e.status_code)

        return Response({
            "success": True,
            "code": "REPORT_SEND_EMAIL_SUCCESS",
            "message": "세무사에게 자료를 전송했습니다.",
            "data": ReportSerializer(report).data,
        })
