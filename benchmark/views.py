from rest_framework.views import APIView
from rest_framework import status
from core.responses import success_response, error_response
from businesses.models import Business
from benchmark.serializers import BenchmarkQuerySerializer, BenchmarkRefreshSerializer
from benchmark.services.benchmark_service import BenchmarkService


def _get_business_or_error(business_id: int):
    business = Business.objects.filter(pk=business_id).first()
    if not business:
        return None, error_response(
            code="BUSINESS_NOT_FOUND",
            message="사업장을 찾을 수 없습니다.",
            status=status.HTTP_404_NOT_FOUND,
        )
    return business, None


class BenchmarkDashboardView(APIView):
    """AI 벤치마크 종합 대시보드 조회 (처방, 도넛점수, 바차트, 라인차트 통합)."""

    def get(self, request, business_id):
        business, err = _get_business_or_error(business_id)
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
    """카테고리별 비용 비교 단독 조회 (바 차트용)."""

    def get(self, request, business_id):
        business, err = _get_business_or_error(business_id)
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
    """월별 벤치마크 추이 단독 조회 (라인 차트용)."""

    def get(self, request, business_id):
        business, err = _get_business_or_error(business_id)
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
    """AI 경영 진단 새로고침 (OpenAI 강제 재실행)."""

    def post(self, request, business_id):
        business, err = _get_business_or_error(business_id)
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
    """8월 경영 종합 진단 리포트 (모달 팝업 전용 심층 진단 데이터)."""

    def get(self, request, business_id):
        business, err = _get_business_or_error(business_id)
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

