"""로그인 없이 시연할 때 사용하는 데모 게스트 인증.

- 게스트 요청은 `is_demo=True` 사업장에만 접근 허용
- 실제 사업장의 소유권 검증은 그대로 유지
- `DEMO_MODE=0`이면 토큰 인증만 허용
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication

# 권한 검사에서 일반 토큰 인증과 데모 게스트를 구분하기 위한 값.
DEMO_GUEST_MARKER = "DEMO_GUEST"


class DemoGuestAuthentication(BaseAuthentication):
    """인증 헤더가 없는 데모 요청에 제한된 게스트 권한을 부여한다."""

    def authenticate(self, request):
        if not getattr(settings, "DEMO_MODE", False):
            return None

        # 명시된 인증 헤더는 앞선 TokenAuthentication의 결과를 존중한다.
        if request.META.get("HTTP_AUTHORIZATION"):
            return None

        user_model = get_user_model()
        demo_username = getattr(settings, "DEMO_USERNAME", "demo")
        user = user_model.objects.filter(username=demo_username, is_active=True).first()
        if user is None:
            # 시드 데이터가 없을 때 임의 계정을 만들지 않고 일반 401 흐름을 유지한다.
            return None

        return (user, DEMO_GUEST_MARKER)

    def authenticate_header(self, request):
        # 인증 실패 응답이 토큰 인증 방식임을 클라이언트에 알린다.
        return 'Token realm="api"'
