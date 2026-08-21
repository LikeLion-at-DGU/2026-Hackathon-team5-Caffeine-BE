"""인증 도입 전 작성된 테스트에 기본 토큰을 주입하는 테스트 러너.

배포 코드에서는 불러오지 않으며, 미인증 동작을 검증하는 테스트는
`client.credentials(HTTP_AUTHORIZATION="")`로 기본 토큰을 해제한다.
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
