from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework import status
from core.responses import success_response, error_response
from core.permissions import get_user_business
from businesses.models import Business
from benchmark.serializers import BenchmarkQuerySerializer, BenchmarkRefreshSerializer
from benchmark.services.benchmark_service import BenchmarkService


def _get_business_or_error(request, business_id):
    """공통 사업장 조회와 권한 검사로 위임한다."""
    return get_user_business(request, business_id)


class BenchmarkDashboardView(APIView):
    """상권 비교와 AI 진단을 포함한 경영 대시보드를 조회한다."""

    def get(self, request, business_id):
        business, err = _get_business_or_error(request, business_id)
        if err:
            return err

        serializer = BenchmarkQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return error_response(
                code="INVALID_BENCHMARK_QUERY",
                message="조회 파라미터가 올바르지 않습니다.",
                errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = BenchmarkService.get_dashboard_data(
            business=business,
            year=serializer.validated_data["year"],
            month=serializer.validated_data["month"],
        )
        return success_response(
            code="BENCHMARK_DASHBOARD_SUCCESS",
            message="AI 경영 진단 및 상권 벤치마크 데이터를 조회했습니다.",
            data=data,
        )


class BenchmarkCategoriesView(APIView):
    """비용 항목별 사업장·상권 비율을 조회한다."""

    def get(self, request, business_id):
        business, err = _get_business_or_error(request, business_id)
        if err:
            return err

        serializer = BenchmarkQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return error_response(
                code="INVALID_BENCHMARK_QUERY",
                message="조회 파라미터가 올바르지 않습니다.",
                errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        dashboard = BenchmarkService.get_dashboard_data(
            business=business,
            year=serializer.validated_data["year"],
            month=serializer.validated_data["month"],
        )
        return success_response(
            code="BENCHMARK_CATEGORIES_SUCCESS",
            message="카테고리별 비용 비교 데이터를 조회했습니다.",
            data={
                "business_id": business.id,
                "year_month": dashboard["year_month"],
                "region_name": dashboard["region_name"],
                "category_comparison": dashboard["category_comparison"],
            },
        )


class BenchmarkTrendView(APIView):
    """월별 사업장·상권 지표 추이를 조회한다."""

    def get(self, request, business_id):
        business, err = _get_business_or_error(request, business_id)
        if err:
            return err

        serializer = BenchmarkQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return error_response(
                code="INVALID_BENCHMARK_QUERY",
                message="조회 파라미터가 올바르지 않습니다.",
                errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        dashboard = BenchmarkService.get_dashboard_data(
            business=business,
            year=serializer.validated_data["year"],
            month=serializer.validated_data["month"],
        )
        return success_response(
            code="BENCHMARK_TREND_SUCCESS",
            message="월별 벤치마크 추이 데이터를 조회했습니다.",
            data={
                "business_id": business.id,
                "year_month": dashboard["year_month"],
                "monthly_trends": dashboard["monthly_trends"],
                "mom_profit_improvement": dashboard["mom_profit_improvement"],
            },
        )


class BenchmarkAiDiagnosisRefreshView(APIView):
    """캐시를 사용하지 않고 AI 경영 진단을 다시 생성한다."""
    # 새 진단 요청이 유료 호출을 과도하게 만들지 않도록 제한한다.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "llm"


    def post(self, request, business_id):
        business, err = _get_business_or_error(request, business_id)
        if err:
            return err

        serializer = BenchmarkRefreshSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="INVALID_BENCHMARK_REFRESH_BODY",
                message="요청 바디가 올바르지 않습니다.",
                errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = BenchmarkService.refresh_diagnosis(
            business=business,
            year=serializer.validated_data["year"],
            month=serializer.validated_data["month"],
        )
        return success_response(
            code="BENCHMARK_AI_DIAGNOSIS_REFRESHED",
            message="AI 경영 진단이 새롭게 갱신되었습니다.",
            data=result,
        )


class BenchmarkDeepDiagnosisView(APIView):
    """선택한 월의 경영 종합 진단을 조회한다."""
    # 심층 진단의 유료 호출이 남용되지 않도록 제한한다.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "llm"


    def get(self, request, business_id):
        business, err = _get_business_or_error(request, business_id)
        if err:
            return err

        serializer = BenchmarkQuerySerializer(data=request.query_params)
        if not serializer.is_valid():
            return error_response(
                code="INVALID_BENCHMARK_QUERY",
                message="조회 파라미터가 올바르지 않습니다.",
                errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        from benchmark.services.deep_diagnosis_service import DeepDiagnosisService

        data = DeepDiagnosisService.get_deep_diagnosis(
            business=business,
            year=serializer.validated_data["year"],
            month=serializer.validated_data["month"],
        )
        return success_response(
            code="BENCHMARK_DEEP_DIAGNOSIS_SUCCESS",
            message="8월 경영 종합 심층 진단 리포트를 조회했습니다.",
            data=data,
        )

