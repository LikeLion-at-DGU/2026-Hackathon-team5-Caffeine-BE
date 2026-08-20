"""데모 시연용 게스트 인증.

배경
----
심사 부스에서는 로그인 없이 바로 대시보드를 보여줘야 하고, 프론트엔드에는 아직
로그인 플로우와 Authorization 헤더 주입이 구현되어 있지 않다. 그렇다고 소유권
검증을 무력화하면(예: owner가 NULL인 사업장을 통과시키면) 실제 사용자의 세무·급여
데이터까지 열리므로, 대신 **좁고 명시적인 게스트 경로 하나**를 만든다.

위협 모델
--------
이 경로로 인증된 요청은 `is_demo=True` 사업장에만 접근할 수 있다(권한 계층에서
강제, `core.permissions` 참조). 실제 사용자가 회원가입으로 만든 사업장은
`is_demo=False`이므로 게스트 토큰으로는 절대 도달하지 못한다. 즉 노출되는 것은
`seed_demo_data`가 만든 가상 데이터 한 벌뿐이다.

끄는 방법
--------
`.env`에 `DEMO_MODE=0`을 넣으면 이 인증 클래스는 즉시 무동작이 되고, 모든 요청은
`Authorization: Token <key>`를 요구한다. 실서비스 전환 시 반드시 0으로 둔다.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication

# 이 인증 클래스로 통과한 요청을 권한 계층에서 식별하기 위한 마커.
# request.auth 값으로 실려 전달된다.
DEMO_GUEST_MARKER = "DEMO_GUEST"


class DemoGuestAuthentication(BaseAuthentication):
    """DEMO_MODE=True이고 Authorization 헤더가 없을 때만 데모 계정으로 인증한다."""

    def authenticate(self, request):
        if not getattr(settings, "DEMO_MODE", False):
            return None

        # 토큰이 실려 있으면 TokenAuthentication이 처리한다. 여기서는 관여하지 않는다.
        # (인증 클래스 순서상 TokenAuthentication이 먼저 실행되므로, 잘못된 토큰은
        #  이미 401로 끊겨서 이 지점에 도달하지 않는다.)
        if request.META.get("HTTP_AUTHORIZATION"):
            return None

        user_model = get_user_model()
        demo_username = getattr(settings, "DEMO_USERNAME", "demo")
        user = user_model.objects.filter(username=demo_username, is_active=True).first()
        if user is None:
            # 데모 계정이 아직 시딩되지 않았다면 익명으로 두고 401을 받게 한다.
            return None

        return (user, DEMO_GUEST_MARKER)

    def authenticate_header(self, request):
        # 401 응답에 WWW-Authenticate를 남겨 프론트엔드가 원인을 알 수 있게 한다.
        return 'Token realm="api"'
