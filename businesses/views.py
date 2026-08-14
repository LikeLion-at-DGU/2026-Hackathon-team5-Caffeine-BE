from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from .models import Business
from .serializers import (
    BusinessSerializer,
    CodefAuthRequestSerializer,
    TaxTypeHistorySerializer,
)
from .services.codef_auth_service import (
    CodefAuthService,
    InvalidAuthRequestError,
)
from .services.tax_type_service import CodefResponseError, TaxTypeService


class BusinessViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    """사업장 정보 조회/수정 및 CODEF 연동 API."""

    # 기본 조회/수정과 @action 기반 API를 허용한다.
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

        # 최신 과세유형 변경 이력부터 조회한다.
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
            # CODEF 응답 처리 실패는 502로 반환한다.
            return Response(
                {"error": str(e)},
                status=502,
            )

        return Response(result, status=200)

    @action(
        detail=True,
        methods=["post"],
        url_path="codef-auth",
        url_name="codef-auth",
    )
    def codef_auth(self, request, pk=None):
        business = self.get_object()

        # 요청한 연결 유형(CARD/HOMETAX)을 검증한다.
        serializer = CodefAuthRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # CODEF 연결 요청을 Service에 위임한다.
        result = CodefAuthService().request(
            business,
            serializer.validated_data["connection_type"],
        )

        return Response(result, status=200)

    @action(
        detail=True,
        methods=["get"],
        url_path="codef-auth/status",
        url_name="codef-auth-status",
    )
    def codef_auth_status(self, request, pk=None):
        business = self.get_object()

        # CARD/HOMETAX의 현재 CODEF 연결 상태를 조회한다.
        result = CodefAuthService().status(business)

        return Response(result, status=200)

    @action(
        detail=True,
        methods=["post"],
        url_path="codef-auth/retry",
        url_name="codef-auth-retry",
    )
    def codef_auth_retry(self, request, pk=None):
        business = self.get_object()

        # 재시도할 연결 유형을 검증한다.
        serializer = CodefAuthRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            # HOMETAX 2-way 인증 재시도를 Service에 위임한다.
            result = CodefAuthService().retry(
                business,
                serializer.validated_data["connection_type"],
            )
        except InvalidAuthRequestError as e:
            # 허용되지 않는 재시도 요청은 400으로 반환한다.
            return Response(
                {"error": str(e)},
                status=400,
            )

        return Response(result, status=200)