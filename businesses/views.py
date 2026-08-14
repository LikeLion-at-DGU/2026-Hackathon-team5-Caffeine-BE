from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from .models import Business
from .serializers import BusinessSerializer
from .services.tax_type_service import CodefResponseError, TaxTypeService


class BusinessViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    """사업장 정보 조회/수정 및 CODEF 연동 API."""

    # 기본 조회/수정과 @action 기반 POST API를 허용한다.
    http_method_names = ["get", "post", "patch", "head", "options"]

    queryset = Business.objects.all()
    serializer_class = BusinessSerializer

    @action(
        detail=True,
        methods=["post"],
        url_path="tax-type/sync",
        url_name="tax-type-sync",
    )
    def tax_type_sync(self, request, pk=None):
        # ViewSet의 조회 규칙을 적용한 사업장 객체를 Service에 전달한다.
        business = self.get_object()

        try:
            result = TaxTypeService().sync(business)
        except CodefResponseError as e:
            # 외부 CODEF 응답 처리 실패는 502로 반환한다.
            return Response(
                {"error": str(e)},
                status=502,
            )

        return Response(result, status=200)