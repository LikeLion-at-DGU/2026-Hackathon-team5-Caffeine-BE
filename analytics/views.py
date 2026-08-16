from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.exceptions import AnalyticsServiceError
from analytics.services import monthly_close_service
from analytics.services.monthly_summary_service import get_monthly_tax_summary

from django.http import HttpResponse

from analytics.services.export_service import build_export


def _error_response(code: str, message: str, http_status: int, errors: dict | None = None) -> Response:
    return Response(
        {"success": False, "code": code, "message": message, "errors": errors or {}},
        status=http_status,
    )


class MonthlySummaryView(APIView):
    def get(self, request, business_id):
        year = request.query_params.get("year")
        month = request.query_params.get("month")
        if not year or not month:
            return _error_response(
                "INVALID_PERIOD", "조회 기간이 올바르지 않습니다.", status.HTTP_400_BAD_REQUEST
            )

        data = get_monthly_tax_summary(business_id, int(year), int(month))
        return Response({
            "success": True,
            "code": "MONTHLY_SUMMARY_SUCCESS",
            "message": "월별 세무 현황 결산을 조회했습니다.",
            "data": data,
        })


class MonthlyCloseView(APIView):
    def post(self, request, business_id):
        year = request.data.get("year")
        month = request.data.get("month")
        if not year or not month:
            return _error_response(
                "INVALID_PERIOD", "조회 기간이 올바르지 않습니다.", status.HTTP_400_BAD_REQUEST
            )

        try:
            monthly_close = monthly_close_service.close_month(business_id, int(year), int(month))
        except AnalyticsServiceError as e:
            return _error_response(e.code, e.message, status.HTTP_409_CONFLICT)

        return Response({
            "success": True,
            "code": "MONTHLY_CLOSE_SUCCESS",
            "message": f"{month}월 장부가 마감 승인되었습니다.",
            "data": {
                "closed_at": monthly_close.closed_at.isoformat(),
                "is_export_available": True,
            },
        })


class ExportView(APIView):
    def get(self, request, business_id):
        year = request.query_params.get("year")
        month = request.query_params.get("month")
        export_format = request.query_params.get("file_type")

        if not year or not month or export_format not in ("pdf", "xlsx"):
            return _error_response(
                "INVALID_EXPORT_FORMAT", "지원하지 않는 파일 형식입니다.", status.HTTP_400_BAD_REQUEST
            )

        try:
            file_bytes = build_export(business_id, int(year), int(month), export_format)
        except AnalyticsServiceError as e:
            return _error_response(e.code, e.message, status.HTTP_409_CONFLICT)

        if export_format == "xlsx":
            response = HttpResponse(
                file_bytes,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f'attachment; filename="tax_export_{year}_{month}.xlsx"'
            return response

        response = HttpResponse(file_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="tax_export_{year}_{month}.pdf"'
        return response