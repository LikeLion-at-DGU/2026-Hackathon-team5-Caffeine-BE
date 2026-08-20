from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient


def authenticate_client_for_business(test_case, business=None):
    """테스트 케이스의 APIClient에 인증 토큰을 주입하고 사업장 소유권을 연결한다."""
    user = User.objects.create_user(
        username=f"test_user_{User.objects.count() + 1}",
        password="password123",
    )
    token = Token.objects.create(user=user)
    if not hasattr(test_case, "client") or test_case.client is None:
        test_case.client = APIClient()
    test_case.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")

    if business is not None:
        business.owner = user
        business.save(update_fields=["owner"])

    test_case.user = user
    test_case.token = token
    return user, token
