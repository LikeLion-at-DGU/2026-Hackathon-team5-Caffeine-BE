from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from analytics.exceptions import AnalyticsServiceError
from analytics.serializers import (
    AnalyticsExportQuerySerializer,
    AnalyticsPeriodQuerySerializer,
    CostRatioQuerySerializer,
    TrendQuerySerializer,
)
from analytics.services.analytics_service import get_category_trend, get_cost_ratio
from analytics.services import monthly_close_service
from analytics.services.monthly_summary_service import get_monthly_tax_summary
from businesses.models import Business


def _error_response(code: str, message: str, http_status: int, errors: dict | None = None) -> Response:
    return Response(
        {"success": False, "code": code, "message": message, "errors": errors or {}},
        status=http_status,
    )


def _business_error(business_id):
    if Business.objects.filter(pk=business_id).exists():
        return None
    return _error_response(
        "BUSINESS_NOT_FOUND",
        "사업장을 찾을 수 없습니다.",
        status.HTTP_404_NOT_FOUND,
    )


class MonthlySummaryView(APIView):
    def get(self, request, business_id):
        if error := _business_error(business_id):
            return error
        query = AnalyticsPeriodQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return _error_response(
                "INVALID_PERIOD", "조회 기간이 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, query.errors,
            )

        data = get_monthly_tax_summary(business_id, **query.validated_data)
        return Response({
            "success": True,
            "code": "MONTHLY_SUMMARY_SUCCESS",
            "message": "월별 세무 현황 결산을 조회했습니다.",
            "data": data,
        })


class MonthlyCloseView(APIView):
    def post(self, request, business_id):
        if error := _business_error(business_id):
            return error
        serializer = AnalyticsPeriodQuerySerializer(data=request.data)
        if not serializer.is_valid():
            return _error_response(
                "INVALID_PERIOD", "조회 기간이 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, serializer.errors,
            )
        year = serializer.validated_data["year"]
        month = serializer.validated_data["month"]

        try:
            monthly_close = monthly_close_service.close_month(business_id, year, month)
        except AnalyticsServiceError as e:
            return _error_response(e.code, e.message, status.HTTP_409_CONFLICT)

        return Response({
            "success": True,
            "code": "MONTHLY_CLOSE_SUCCESS",
            "message": f"{month}월 장부가 마감 승인되었습니다.",
            "data": {
                "closed_at": monthly_close.approved_at.isoformat(),
                "is_export_available": True,
            },
        })


class CostRatioView(APIView):
    def get(self, request, business_id):
        if error := _business_error(business_id):
            return error
        query = CostRatioQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return _error_response(
                "INVALID_PERIOD", "조회 기간이 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, query.errors,
            )
        return Response({
            "success": True,
            "code": "COST_RATIO_SUCCESS",
            "message": "카테고리별 비용 비율을 조회했습니다.",
            "data": get_cost_ratio(business_id=business_id, **query.validated_data),
        })


class CategoryTrendView(APIView):
    def get(self, request, business_id):
        if error := _business_error(business_id):
            return error
        query = TrendQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return _error_response(
                "INVALID_TREND_QUERY", "증감 추이 조회 조건이 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, query.errors,
            )
        return Response({
            "success": True,
            "code": "CATEGORY_TREND_SUCCESS",
            "message": "카테고리 증감 추이를 조회했습니다.",
            "data": get_category_trend(business_id=business_id, **query.validated_data),
        })


class AnalyticsSummaryView(APIView):
    def get(self, request, business_id):
        if error := _business_error(business_id):
            return error
        query = AnalyticsPeriodQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return _error_response(
                "INVALID_PERIOD", "조회 기간이 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, query.errors,
            )
        data = get_monthly_tax_summary(business_id, **query.validated_data)
        return Response({
            "success": True,
            "code": "ANALYTICS_SUMMARY_SUCCESS",
            "message": "매출·비용 종합 요약을 조회했습니다.",
            "data": data,
        })


class AnalyticsExportView(APIView):
    def get(self, request, business_id):
        if error := _business_error(business_id):
            return error
        query = AnalyticsExportQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return _error_response(
                "INVALID_EXPORT_QUERY", "내보내기 조건이 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, query.errors,
            )
        params = query.validated_data
        year_month = f'{params["year"]:04d}-{params["month"]:02d}'
        file_type = params["file_type"]
        from reports.exceptions import ReportServiceError
        from reports.services import report_service

        try:
            report_service.generate_report(business_id, year_month)
            file_field = report_service.get_report_file(
                business_id, year_month, file_type
            )
        except ReportServiceError as exc:
            return _error_response(exc.code, exc.message, exc.status_code)

        content_type = "text/csv; charset=utf-8" if file_type == "csv" else "application/pdf"
        file_field.open("rb")
        try:
            file_content = file_field.read()
        finally:
            file_field.close()
        response = HttpResponse(file_content, content_type=content_type)
        response["Content-Disposition"] = (
            f'attachment; filename="cafe_assistant_{year_month}.{file_type}"'
        )
        return response
