"""앱 전반에서 공통으로 사용하는 사업장 소유권 검사.

1. 미인증 요청 차단
2. 소유자가 없는 사업장은 기본 차단
3. 다른 사용자의 사업장 접근 차단
4. 데모 게스트는 데모 사업장만 허용
"""

from django.conf import settings as dj_settings
from rest_framework import permissions

from businesses.models import Business
from core.authentication import DEMO_GUEST_MARKER
from core.responses import error_response


def _unauthorized():
    return error_response(
        code="UNAUTHORIZED",
        message="인증 자격 증명이 제공되지 않았습니다.",
        status=401,
    )


def _forbidden():
    return error_response(
        code="FORBIDDEN_BUSINESS_ACCESS",
        message="해당 사업장에 대한 접근 권한이 없습니다.",
        status=403,
    )


def _not_found():
    return error_response(
        code="BUSINESS_NOT_FOUND",
        message="사업장을 찾을 수 없습니다.",
        status=404,
    )


def _invalid(message="business_id 형식이 올바르지 않습니다."):
    return error_response(code="INVALID_BUSINESS_ID", message=message, status=400)


def _allow_unowned() -> bool:
    return bool(getattr(dj_settings, "ALLOW_UNOWNED_BUSINESS_ACCESS", False))


def _is_demo_guest(request) -> bool:
    return getattr(request, "auth", None) == DEMO_GUEST_MARKER


def is_business_accessible(request, business) -> bool:
    """요청 사용자가 사업장에 접근할 수 있는지 반환한다."""
    if business is None:
        return False
    if not request.user or not request.user.is_authenticated:
        return False

    # 게스트 인증이 실제 사업장의 소유권 검사를 우회하지 못하도록 제한한다.
    if _is_demo_guest(request) and not getattr(business, "is_demo", False):
        return False

    if business.owner_id is None:
        return _allow_unowned()

    return business.owner_id == request.user.id


def check_business_owner(request, business):
    """조회된 사업장의 접근 권한을 검사하고 실패 응답을 반환한다."""
    if not request.user or not request.user.is_authenticated:
        return _unauthorized()
    if is_business_accessible(request, business):
        return None
    return _forbidden()


def check_business(request, business_id):
    """사업장을 조회해 접근 권한을 검사하고 실패 응답을 반환한다."""
    _business, error = get_user_business(request, business_id)
    return error


def get_user_business(request, business_id):
    """접근 가능한 사업장과 오류 응답을 `(business, error)` 형태로 반환한다."""
    if business_id in (None, ""):
        return None, _invalid("business_id는 필수 파라미터입니다.")
    try:
        bid = int(business_id)
    except (ValueError, TypeError):
        return None, _invalid()

    business = Business.objects.filter(pk=bid).first()
    if business is None:
        # 미인증 요청에는 사업장 존재 여부를 노출하지 않는다.
        if not request.user or not request.user.is_authenticated:
            return None, _unauthorized()
        return None, _not_found()

    error = check_business_owner(request, business)
    if error:
        return None, error
    return business, None


class IsBusinessOwner(permissions.BasePermission):
    """사업장 또는 사업장 외래 키를 가진 객체의 소유권을 검사한다.

    `APIView`에서는 객체 권한 검사가 자동 호출되지 않으므로
    `check_business` 또는 `get_user_business`를 직접 사용한다.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if isinstance(obj, Business):
            return is_business_accessible(request, obj)
        business = getattr(obj, "business", None)
        if isinstance(business, Business):
            return is_business_accessible(request, business)
        # 사업장을 식별할 수 없는 객체는 안전하게 차단한다.
        return False
