from rest_framework import permissions
from rest_framework.response import Response
from businesses.models import Business
from core.responses import error_response


def get_user_business(request, business_id: int | str) -> tuple[Business | None, Response | None]:
    """현재 로그인한 유저가 소유한 사업장인지 엄격하게 검증 (IDOR 방어 핵심 헬퍼)."""
    if not business_id:
        return None, error_response(
            code="INVALID_BUSINESS_ID",
            message="business_id는 필수 파라미터입니다.",
            status=400,
        )

    try:
        bid = int(business_id)
    except (ValueError, TypeError):
        return None, error_response(
            code="INVALID_BUSINESS_ID",
            message="business_id 형식이 올바르지 않습니다.",
            status=400,
        )

    # 미인증 유저 차단
    if not request.user or not request.user.is_authenticated:
        return None, error_response(
            code="UNAUTHORIZED",
            message="인증 자격 증명이 제공되지 않았습니다.",
            status=401,
        )

    # 사업장 존재 여부 및 소유권 검사
    business = Business.objects.filter(id=bid).first()
    if not business:
        return None, error_response(
            code="BUSINESS_NOT_FOUND",
            message="사업장을 찾을 수 없습니다.",
            status=404,
        )

    # 다른 유저의 사업장 접근 시도 차단 (IDOR 차단: 403 Forbidden 반환)
    if business.owner_id is not None and business.owner_id != request.user.id:
        return None, error_response(
            code="FORBIDDEN_BUSINESS_ACCESS",
            message="해당 사업장에 대한 접근 권한이 없습니다.",
            status=403,
        )

    return business, None


class IsBusinessOwner(permissions.BasePermission):
    """Business 객체 또는 Business에 종속된 객체의 소유권을 검증하는 DRF Permission."""

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False

        # Business 자체인 경우
        if isinstance(obj, Business):
            if obj.owner_id is None:
                return True
            return obj.owner_id == request.user.id

        # business 속성을 가진 도메인 모델인 경우 (Transaction, Employee 등)
        if hasattr(obj, "business") and isinstance(obj.business, Business):
            if obj.business.owner_id is None:
                return True
            return obj.business.owner_id == request.user.id

        return True
