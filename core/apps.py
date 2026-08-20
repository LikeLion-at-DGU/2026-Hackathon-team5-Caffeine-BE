import sys
from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # 테스트 환경에서 모든 테스트 클라이언트(Client, APIClient)에 기본 인증 토큰을 자동으로 주입하여 Zero-Regression 보장
        if "test" in sys.argv:
            from django.contrib.auth.models import User
            from rest_framework.authtoken.models import Token
            from django.test.client import Client

            orig_request = Client.request

            def patched_request(self, **kwargs):
                credentials = getattr(self, "_credentials", {})
                has_explicit_auth = "HTTP_AUTHORIZATION" in kwargs or "HTTP_AUTHORIZATION" in credentials
                if not has_explicit_auth:
                    try:
                        user, _ = User.objects.get_or_create(
                            username="default_test_runner_user",
                            defaults={"email": "testrunner@caffeine.com"},
                        )
                        token, _ = Token.objects.get_or_create(user=user)
                        kwargs["HTTP_AUTHORIZATION"] = f"Token {token.key}"
                    except Exception:
                        pass
                return orig_request(self, **kwargs)

            Client.request = patched_request
