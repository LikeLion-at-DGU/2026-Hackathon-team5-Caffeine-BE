from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from settings.exceptions import SettingsServiceError
from settings.serializers import PaymentMethodUpdateSerializer, SubscriptionSerializer
from settings.services import subscription_service


def _error_response(code: str, message: str, http_status: int, errors: dict | None = None) -> Response:
    return Response(
        {"success": False, "code": code, "message": message, "errors": errors or {}},
        status=http_status,
    )


class SubscriptionView(APIView):
    def get(self, request, business_id):
        try:
            subscription = subscription_service.get_subscription(business_id)
        except SettingsServiceError as e:
            return _error_response(e.code, e.message, status.HTTP_404_NOT_FOUND)

        serializer = SubscriptionSerializer(subscription)
        return Response({
            "success": True,
            "code": "SUBSCRIPTION_SUCCESS",
            "message": "구독 정보를 조회했습니다.",
            "data": serializer.data,
        })


class PaymentMethodUpdateView(APIView):
    def patch(self, request, business_id):
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

        return Response({
            "success": True,
            "code": "PAYMENT_METHOD_UPDATE_SUCCESS",
            "message": "결제수단이 변경되었습니다.",
            "data": {},
        })


class SubscriptionCancelView(APIView):
    def post(self, request, business_id):
        try:
            subscription = subscription_service.cancel_subscription(business_id)
        except SettingsServiceError as e:
            http_status = status.HTTP_409_CONFLICT if e.code == "ALREADY_CANCELLED" else status.HTTP_404_NOT_FOUND
            return _error_response(e.code, e.message, http_status)

        return Response({
            "success": True,
            "code": "SUBSCRIPTION_CANCEL_SUCCESS",
            "message": "구독이 취소되었습니다.",
            "data": {
                "cancelled_at": subscription.cancelled_at.isoformat(),
                "access_until": subscription.access_until.isoformat(),
            },
        })