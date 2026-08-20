"""레거시 테스트 픽스처 호환용 테스트 러너.

기존 테스트 다수가 인증 도입 이전에 작성되어 Authorization 헤더를 세팅하지 않는다.
전면 수정 전까지 테스트 클라이언트에만 기본 토큰을 주입한다.

프로덕션 앱 레지스트리(AppConfig.ready)가 아니라 TEST_RUNNER에만 존재하므로,
배포 런타임에서는 이 모듈이 절대 import되지 않는다.

주의: 미인증(401) 동작을 검증하는 테스트는 반드시
`client.credentials(HTTP_AUTHORIZATION="")`로 헤더를 명시적으로 비워야 한다.
"""

from django.test.runner import DiscoverRunner


class LegacyAuthTestRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        from django.test.client import Client

        if getattr(Client, "_caffeine_auth_patched", False):
            return

        original_request = Client.request

        def request_with_default_token(self, **kwargs):
            from django.contrib.auth.models import User
            from rest_framework.authtoken.models import Token

            credentials = getattr(self, "_credentials", {})
            already_set = (
                "HTTP_AUTHORIZATION" in kwargs or "HTTP_AUTHORIZATION" in credentials
            )
            if not already_set:
                user, _ = User.objects.get_or_create(
                    username="default_test_runner_user",
                    defaults={"email": "testrunner@caffeine.com"},
                )
                token, _ = Token.objects.get_or_create(user=user)
                kwargs["HTTP_AUTHORIZATION"] = f"Token {token.key}"
            return original_request(self, **kwargs)

        Client.request = request_with_default_token
        Client._caffeine_auth_patched = True
