from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.responses import error_response, success_response
from core.serializers import (
    LoginSerializer,
    RegisterSerializer,
    UserProfileSerializer,
    UserBusinessItemSerializer,
)


class LoginView(APIView):
    """로그인한 사용자에게 API 토큰과 기본 사업장을 반환한다."""

    permission_classes = [AllowAny]
    # 비밀번호 무차별 대입을 제한한다.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="INVALID_CREDENTIALS",
                message="로그인 정보가 올바르지 않습니다.",
                errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)

        businesses = user.businesses.all().order_by("id")
        primary_business = businesses.first()

        data = {
            "token": token.key,
            "user_id": user.id,
            "username": user.username,
            "primary_business_id": primary_business.id if primary_business else None,
            "businesses": UserBusinessItemSerializer(businesses, many=True).data,
        }

        return success_response(
            code="LOGIN_SUCCESS",
            message="로그인에 성공했습니다.",
            data=data,
        )


class RegisterView(APIView):
    """사용자와 기본 사업장을 만들고 바로 사용할 API 토큰을 발급한다."""

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="INVALID_REGISTRATION_DATA",
                message="회원가입 정보가 올바르지 않습니다.",
                errors=serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )

        user, business = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)

        data = {
            "token": token.key,
            "user_id": user.id,
            "username": user.username,
            "primary_business_id": business.id,
            "businesses": UserBusinessItemSerializer([business], many=True).data,
        }

        return success_response(
            code="REGISTER_SUCCESS",
            message="회원가입이 완료되었습니다.",
            data=data,
            status=status.HTTP_201_CREATED,
        )


class LogoutView(APIView):
    """현재 API 토큰을 폐기해 로그아웃한다."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if hasattr(request.user, "auth_token"):
            request.user.auth_token.delete()

        return success_response(
            code="LOGOUT_SUCCESS",
            message="로그아웃되었습니다.",
            data={},
        )


class MeView(APIView):
    """현재 사용자와 접근 가능한 사업장 목록을 반환한다."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return success_response(
            code="ME_SUCCESS",
            message="내 계정 정보를 조회했습니다.",
            data=serializer.data,
        )
