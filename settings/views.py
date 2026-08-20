from businesses.models import Business
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error_response, success_response
from settings.exceptions import SettingsServiceError
from settings.serializers import (
    BusinessInfoSerializer, BusinessInfoUpdateSerializer,
    PaymentMethodUpdateSerializer, SubscriptionSerializer,
)
from settings.services import business_info_service, subscription_service


def _error_response(code: str, message: str, http_status: int, errors: dict | None = None) -> Response:
    return error_response(
        code=code,
        message=message,
        errors=errors,
        status=http_status,
    )


def _check_business(request, business_id: int):
    if not request.user or not request.user.is_authenticated:
        return _error_response(
            "UNAUTHORIZED",
            "인증 자격 증명이 제공되지 않았습니다.",
            status.HTTP_401_UNAUTHORIZED,
        )
    business = Business.objects.filter(pk=business_id).first()
    if not business:
        return _error_response(
            "BUSINESS_NOT_FOUND",
            "사업장을 찾을 수 없습니다.",
            status.HTTP_404_NOT_FOUND,
        )
    if business.owner_id is not None and business.owner_id != request.user.id:
        return _error_response(
            "FORBIDDEN_BUSINESS_ACCESS",
            "해당 사업장에 대한 접근 권한이 없습니다.",
            status.HTTP_403_FORBIDDEN,
        )
    return None


class BusinessInfoView(APIView):
    def get(self, request, business_id):
        if err := _check_business(request, business_id):
            return err

        data = business_info_service.get_business_info(business_id)
        serializer = BusinessInfoSerializer(data)
        return success_response(
            code="BUSINESS_SETTINGS_SUCCESS",
            message="사업장 기본정보를 조회했습니다.",
            data=serializer.data,
        )

    def patch(self, request, business_id):
        if err := _check_business(request, business_id):
            return err

        serializer = BusinessInfoUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return _error_response(
                "INVALID_BUSINESS_DATA", "사업장 정보가 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, serializer.errors,
            )

        data = business_info_service.update_business_info(business_id, serializer.validated_data)
        return success_response(
            code="BUSINESS_SETTINGS_UPDATE_SUCCESS",
            message="사업장 기본정보를 저장했습니다.",
            data=data,
        )


class SubscriptionView(APIView):
    def get(self, request, business_id):
        if err := _check_business(request, business_id):
            return err

        try:
            subscription = subscription_service.get_subscription(business_id)
        except SettingsServiceError as e:
            return _error_response(e.code, e.message, status.HTTP_404_NOT_FOUND)

        serializer = SubscriptionSerializer(subscription)
        return success_response(
            code="SUBSCRIPTION_SUCCESS",
            message="구독 정보를 조회했습니다.",
            data=serializer.data,
        )


class PaymentMethodUpdateView(APIView):
    def patch(self, request, business_id):
        if err := _check_business(request, business_id):
            return err

        serializer = PaymentMethodUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return _error_response(
                "INVALID_PAYMENT_TOKEN", "결제 토큰이 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, serializer.errors,
            )
        try:
            subscription_service.update_payment_method(
                business_id, serializer.validated_data["payment_token"]
            )
        except SettingsServiceError as e:
            return _error_response(e.code, e.message, status.HTTP_400_BAD_REQUEST)

        return success_response(
            code="PAYMENT_METHOD_UPDATE_SUCCESS",
            message="결제수단이 변경되었습니다.",
            data={},
        )


class SubscriptionCancelView(APIView):
    def post(self, request, business_id):
        if err := _check_business(request, business_id):
            return err

        try:
            subscription = subscription_service.cancel_subscription(business_id)
        except SettingsServiceError as e:
            http_status = status.HTTP_409_CONFLICT if e.code == "ALREADY_CANCELLED" else status.HTTP_404_NOT_FOUND
            return _error_response(e.code, e.message, http_status)

        return success_response(
            code="SUBSCRIPTION_CANCEL_SUCCESS",
            message="구독이 취소되었습니다.",
            data={
                "cancelled_at": subscription.cancelled_at.isoformat(),
                "access_until": subscription.access_until.isoformat(),
            },
        )
