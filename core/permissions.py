"""사업장 소유권(IDOR) 검증의 단일 진실 공급원.

각 앱 views.py에 6개의 이름으로 흩어져 있던 중복 구현을 이 파일 하나로 통합한다.
정책을 바꿀 때 한 곳만 고치면 되고, 한 곳을 놓쳐서 구멍이 생기는 일이 없다.

정책
----
1. 미인증 요청은 401.
2. 소유자(owner)가 지정되지 않은 사업장은 **차단**한다(fail-closed).
   레거시 테스트 픽스처가 owner를 지정하지 않으므로, 테스트 런타임에서만
   `settings.ALLOW_UNOWNED_BUSINESS_ACCESS`로 통과시킨다. 배포에서는 항상 False.
3. 소유자가 다르면 403.
4. 데모 게스트 인증(`core.authentication.DemoGuestAuthentication`)으로 통과한
   요청은 `is_demo=True` 사업장에만 접근할 수 있다.
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
    """접근 가능 여부만 boolean으로 판정한다. 응답 생성은 호출부에 맡긴다."""
    if business is None:
        return False
    if not request.user or not request.user.is_authenticated:
        return False

    # 데모 게스트는 데모 사업장 밖으로 나갈 수 없다.
    if _is_demo_guest(request) and not getattr(business, "is_demo", False):
        return False

    if business.owner_id is None:
        return _allow_unowned()

    return business.owner_id == request.user.id


def check_business_owner(request, business):
    """이미 조회된 Business 객체에 대한 인증·소유권 검증. 통과 시 None."""
    if not request.user or not request.user.is_authenticated:
        return _unauthorized()
    if is_business_accessible(request, business):
        return None
    return _forbidden()


def check_business(request, business_id):
    """business_id로 조회한 뒤 검증. 통과 시 None, 실패 시 error Response."""
    _business, error = get_user_business(request, business_id)
    return error


def get_user_business(request, business_id):
    """(business, error) 튜플 반환. error가 None이면 접근 허용."""
    if business_id in (None, ""):
        return None, _invalid("business_id는 필수 파라미터입니다.")
    try:
        bid = int(business_id)
    except (ValueError, TypeError):
        return None, _invalid()

    business = Business.objects.filter(pk=bid).first()
    if business is None:
        # 미인증 사용자에게는 사업장 존재 여부조차 알려주지 않는다.
        if not request.user or not request.user.is_authenticated:
            return None, _unauthorized()
        return None, _not_found()

    error = check_business_owner(request, business)
    if error:
        return None, error
    return business, None


class IsBusinessOwner(permissions.BasePermission):
    """Business 또는 business FK를 가진 객체의 소유권 검증.

    주의: DRF는 `has_object_permission`을 GenericAPIView.get_object() 또는
    명시적 check_object_permissions() 호출에서만 실행한다. 순수 APIView에서는
    호출되지 않으므로, 그런 뷰에서는 위의 check_business/get_user_business를 쓴다.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if isinstance(obj, Business):
            return is_business_accessible(request, obj)
        business = getattr(obj, "business", None)
        if isinstance(business, Business):
            return is_business_accessible(request, business)
        # 소유권을 판정할 수 없는 객체는 통과시키지 않는다(fail-closed).
        return False
