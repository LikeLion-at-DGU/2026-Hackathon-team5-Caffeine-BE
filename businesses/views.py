from rest_framework import mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import GenericViewSet

from core.permissions import IsBusinessOwner
from core.responses import error_response, success_response
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
from .services.business_info_service import (BusinessInfoService, BusinessInfoSyncError)


class BusinessViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    GenericViewSet,
):
    """사업장 정보 조회/수정 및 CODEF 연동 API."""

    permission_classes = [IsAuthenticated, IsBusinessOwner]

    # 삭제로 외부 연동 이력까지 유실되지 않도록 필요한 메서드만 허용한다.
    http_method_names = ["get", "post", "patch", "head", "options"]

    queryset = Business.objects.all()
    serializer_class = BusinessSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)

        return success_response(
            data=serializer.data,
            code="BUSINESS_DETAIL_SUCCESS",
            message="사업장 정보를 조회했습니다.",
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return success_response(
            data=serializer.data,
            code="BUSINESS_UPDATE_SUCCESS",
            message="사업장 정보를 수정했습니다.",
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="tax-type-history",
        url_name="tax-type-history",
    )
    def tax_type_history(self, request, pk=None):
        business = self.get_object()

        histories = business.tax_type_histories.all()
        data = TaxTypeHistorySerializer(histories, many=True).data

        return success_response(
            data=data,
            code="TAX_TYPE_HISTORY_SUCCESS",
            message="과세유형 변경 이력을 조회했습니다.",
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
            return error_response(
                code="CODEF_RESPONSE_ERROR",
                message="과세유형 정보를 동기화하지 못했습니다.",
                errors={"detail": str(e)},
                status=502,
            )

        return success_response(
            data=result,
            code="TAX_TYPE_SYNC_SUCCESS",
            message="과세유형 정보를 동기화했습니다.",
        )
        
    @action(
        detail=True,
        methods=["post"],
        url_path="business-info/sync",
        url_name="business-info-sync",
    )
    def business_info_sync(self, request, pk=None):
        business = self.get_object()

        try:
            result = BusinessInfoService().sync(
                business
            )

        except BusinessInfoSyncError as e:
            return error_response(
                code="BUSINESS_INFO_SYNC_ERROR",
                message="사업자 업종정보를 동기화하지 못했습니다.",
                errors={
                    "detail": str(e)
                },
                status=502,
            )

        return success_response(
            data=result,
            code="BUSINESS_INFO_SYNC_SUCCESS",
            message="사업자 업종정보를 동기화했습니다.",
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="codef-auth",
        url_name="codef-auth",
    )
    def codef_auth(self, request, pk=None):
        business = self.get_object()

        serializer = CodefAuthRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = CodefAuthService().request(
            business,
            serializer.validated_data["connection_type"],
        )

        return success_response(
            data=result,
            code="CODEF_AUTH_SUCCESS",
            message="CODEF 연동을 요청했습니다.",
        )

    @action(
        detail=True,
        methods=["get"],
        url_path="codef-auth/status",
        url_name="codef-auth-status",
    )
    def codef_auth_status(self, request, pk=None):
        business = self.get_object()

        result = CodefAuthService().status(business)

        return success_response(
            data=result,
            code="CODEF_AUTH_STATUS_SUCCESS",
            message="CODEF 연동 상태를 조회했습니다.",
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="codef-auth/retry",
        url_name="codef-auth-retry",
    )
    def codef_auth_retry(self, request, pk=None):
        business = self.get_object()

        serializer = CodefAuthRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = CodefAuthService().retry(
                business,
                serializer.validated_data["connection_type"],
            )
        except InvalidAuthRequestError as e:
            return error_response(
                code="INVALID_AUTH_REQUEST",
                message="인증 재시도 요청이 올바르지 않습니다.",
                errors={"detail": str(e)},
                status=400,
            )

        return success_response(
            data=result,
            code="CODEF_AUTH_RETRY_SUCCESS",
            message="CODEF 인증을 재시도했습니다.",
        )
