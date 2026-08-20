from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error_response, success_response
from analytics.exceptions import AnalyticsServiceError
from analytics.serializers import (
    AnalyticsExportQuerySerializer,
    AnalyticsPeriodQuerySerializer,
    CostRatioQuerySerializer,
    ProfitTrendQuerySerializer,
    TrendQuerySerializer,
)
from analytics.services.analytics_service import ( get_category_trend, get_cost_ratio, get_profit_trend, )
from analytics.services import monthly_close_service
from analytics.services.monthly_summary_service import get_monthly_tax_summary
from businesses.models import Business


def _error_response(code: str, message: str, http_status: int, errors: dict | None = None) -> Response:
    return error_response(
        code=code,
        message=message,
        errors=errors,
        status=http_status,
    )


def _business_error(request, business_id):
    business = Business.objects.filter(pk=business_id).first()
    if not business:
        return _error_response(
            "BUSINESS_NOT_FOUND",
            "사업장을 찾을 수 없습니다.",
            status.HTTP_404_NOT_FOUND,
        )
    if business.is_demo or business.owner_id is None:
        return None
    if not request.user or not request.user.is_authenticated:
        return _error_response(
            "UNAUTHORIZED",
            "인증 자격 증명이 제공되지 않았습니다.",
            status.HTTP_401_UNAUTHORIZED,
        )
    if business.owner_id != request.user.id:
        return _error_response(
            "FORBIDDEN_BUSINESS_ACCESS",
            "해당 사업장에 대한 접근 권한이 없습니다.",
            status.HTTP_403_FORBIDDEN,
        )
    return None


def _resolve_business_id(request, business_id=None):
    if business_id is not None:
        return business_id, None
    bid = request.query_params.get("business_id")
    if not bid:
        return None, _error_response(
            "INVALID_BUSINESS_ID",
            "business_id는 필수 파라미터입니다.",
            status.HTTP_400_BAD_REQUEST,
        )
    try:
        bid_int = int(bid)
        return bid_int, None
    except (ValueError, TypeError):
        return None, _error_response(
            "INVALID_BUSINESS_ID",
            "business_id 형식이 올바르지 않습니다.",
            status.HTTP_400_BAD_REQUEST,
        )


class MonthlySummaryView(APIView):
    def get(self, request, business_id=None):
        resolved_id, error = _resolve_business_id(request, business_id)
        if error:
            return error
        if b_error := _business_error(request, resolved_id):
            return b_error

        query = AnalyticsPeriodQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return _error_response(
                "INVALID_PERIOD",
                "조회 기간이 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST,
                query.errors,
            )

        data = get_monthly_tax_summary(resolved_id, **query.validated_data)
        return success_response(
            code="MONTHLY_SUMMARY_SUCCESS",
            message="월별 세무 현황 결산을 조회했습니다.",
            data=data,
        )


class DeductionBreakdownView(APIView):
    def get(self, request, business_id=None):
        resolved_id, error = _resolve_business_id(request, business_id)
        if error:
            return error
        if b_error := _business_error(request, resolved_id):
            return b_error

        query = AnalyticsPeriodQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return _error_response(
                "INVALID_PERIOD",
                "조회 기간이 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST,
                query.errors,
            )

        from analytics.services.monthly_summary_service import get_deduction_breakdown

        data = get_deduction_breakdown(resolved_id, **query.validated_data)
        return success_response(
            code="DEDUCTION_BREAKDOWN_SUCCESS",
            message="부가세 공제 구조 분석 데이터를 조회했습니다.",
            data=data,
        )


class MonthlyCloseView(APIView):
    def post(self, request, business_id):
        if error := _business_error(request, business_id):
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

        return success_response(
            code="MONTHLY_CLOSE_SUCCESS",
            message=f"{month}월 장부가 마감 승인되었습니다.",
            data={
                "closed_at": monthly_close.approved_at.isoformat(),
                "is_export_available": True,
            },
        )


class CostRatioView(APIView):
    def get(self, request, business_id):
        if error := _business_error(request, business_id):
            return error
        query = CostRatioQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return _error_response(
                "INVALID_PERIOD", "조회 기간이 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, query.errors,
            )
        return success_response(
            code="COST_RATIO_SUCCESS",
            message="카테고리별 비용 비율을 조회했습니다.",
            data=get_cost_ratio(business_id=business_id, **query.validated_data),
        )


class CategoryTrendView(APIView):
    def get(self, request, business_id):
        if error := _business_error(request, business_id):
            return error
        query = TrendQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return _error_response(
                "INVALID_TREND_QUERY", "증감 추이 조회 조건이 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, query.errors,
            )
        return success_response(
            code="CATEGORY_TREND_SUCCESS",
            message="카테고리 증감 추이를 조회했습니다.",
            data=get_category_trend(business_id=business_id, **query.validated_data),
        )
        

class ProfitTrendView(APIView):
    def get(self, request, business_id):
        if error := _business_error(request, business_id):
            return error

        query = ProfitTrendQuerySerializer(data=request.query_params)

        if not query.is_valid():
            return _error_response(
                "INVALID_PROFIT_TREND_QUERY",
                "매출 및 영업이익 추이 조회 조건이 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST,
                query.errors,
            )

        return success_response(
            code="PROFIT_TREND_SUCCESS",
            message="최근 매출 및 영업이익 추이를 조회했습니다.",
            data=get_profit_trend(
                business_id=business_id,
                **query.validated_data,
            ),
        )


class AnalyticsSummaryView(APIView):
    def get(self, request, business_id):
        if error := _business_error(request, business_id):
            return error
        query = AnalyticsPeriodQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return _error_response(
                "INVALID_PERIOD", "조회 기간이 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, query.errors,
            )
        data = get_monthly_tax_summary(business_id, **query.validated_data)
        return success_response(
            code="ANALYTICS_SUMMARY_SUCCESS",
            message="매출·비용 종합 요약을 조회했습니다.",
            data=data,
        )


class AnalyticsExportView(APIView):
    def get(self, request, business_id):
        if error := _business_error(request, business_id):
            return error
        query = AnalyticsExportQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return _error_response(
                "INVALID_EXPORT_QUERY", "내보내기 조건이 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, query.errors,
            )
        params = query.validated_data
        year_month = f'{params["year"]:04d}-{params["month"]:02d}'
        file_type = request.query_params.get("file_type") or request.query_params.get("format") or params.get("file_type", "csv")
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
