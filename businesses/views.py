from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from .models import Business
from .serializers import BusinessSerializer, TaxTypeHistorySerializer
from .services.tax_type_service import CodefResponseError, TaxTypeService


class BusinessViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    """사업장 정보 조회/수정 및 과세유형 관련 API."""

    # 기본 조회/수정과 @action 기반 API를 허용
    http_method_names = ["get", "post", "patch", "head", "options"]

    queryset = Business.objects.all()
    serializer_class = BusinessSerializer

    @action(
        detail=True,
        methods=["get"],
        url_path="tax-type-history",
        url_name="tax-type-history",
    )
    def tax_type_history(self, request, pk=None):
        business = self.get_object()

        # 모델의 기본 정렬에 따라 최신 변경 이력부터 조회
        histories = business.tax_type_histories.all()

        return Response(
            TaxTypeHistorySerializer(histories, many=True).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="tax-type/sync",
        url_name="tax-type-sync",
    )
    def tax_type_sync(self, request, pk=None):
        business = self.get_object()

        try:
            result = TaxTypeService().sync(business)
        except CodefResponseError as e:
            # 외부 CODEF 응답 처리 실패는 502로 반환
            return Response(
                {"error": str(e)},
                status=502,
            )

        return Response(result, status=200)