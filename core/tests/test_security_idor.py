from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from businesses.models import Business
from transactions.models import Transaction


class SecurityIdorTestCase(TestCase):
    """인증 및 IDOR(사업장 간 소유권 침해) 방어 전용 보안 테스트 스위트."""

    def setUp(self):
        self.client = APIClient()

        # 1. 유저 A 및 사업장 A 생성
        self.user_a = User.objects.create_user(
            username="owner_a",
            password="password123",
            email="owner_a@test.com",
        )
        self.token_a = Token.objects.create(user=self.user_a)
        self.business_a = Business.objects.create(
            owner=self.user_a,
            business_name="카페 A호점",
            business_number="111-11-11111",
            is_demo=False,
        )

        # 2. 유저 B 및 사업장 B 생성
        self.user_b = User.objects.create_user(
            username="owner_b",
            password="password123",
            email="owner_b@test.com",
        )
        self.token_b = Token.objects.create(user=self.user_b)
        self.business_b = Business.objects.create(
            owner=self.user_b,
            business_name="카페 B호점",
            business_number="222-22-22222",
            is_demo=False,
        )

    def test_no_auth_header_returns_401(self):
        """인증 헤더 없이 비즈니스 API 요청 시 401 Unauthorized 반환."""
        self.client.credentials(HTTP_AUTHORIZATION="")
        response = self.client.get(f"/api/businesses/{self.business_a.id}/")
        self.assertEqual(response.status_code, 401)

    def test_login_success_and_token_issue(self):
        """정상 로그인 시 DRF Token 및 소유 사업장 정보 반환."""
        response = self.client.post(
            "/api/auth/login/",
            {"username": "owner_a", "password": "password123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["token"], self.token_a.key)
        self.assertEqual(response.data["data"]["primary_business_id"], self.business_a.id)

    def test_register_creates_user_and_business(self):
        """회원가입 시 유저 생성 + 기본 사업장 생성 + 토큰 즉시 발급."""
        response = self.client.post(
            "/api/auth/register/",
            {
                "username": "new_user",
                "password": "Caffeine!2026",
                "business_name": "신규 카페",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertIn("token", response.data["data"])
        self.assertEqual(response.data["data"]["username"], "new_user")
        created_business_id = response.data["data"]["primary_business_id"]
        self.assertTrue(Business.objects.filter(id=created_business_id, owner__username="new_user").exists())

    def test_owner_access_own_business_returns_200(self):
        """유저 A가 본인 사업장 A 상세 조회 시 200 OK."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        response = self.client.get(f"/api/businesses/{self.business_a.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["business_id"], self.business_a.id)

    def test_idor_user_a_cannot_access_user_b_business_returns_403(self):
        """[IDOR 방어] 유저 A가 타인(유저 B) 소유 사업장 B에 접근 시 403 Forbidden 반환."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        response = self.client.get(f"/api/businesses/{self.business_b.id}/")
        self.assertEqual(response.status_code, 403)

    def test_idor_user_a_cannot_access_user_b_transactions(self):
        """[IDOR 방어] 유저 A가 유저 B의 사업장 ID로 거래 목록 조회 시 403 Forbidden 반환."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        response = self.client.get(f"/api/transactions/?business_id={self.business_b.id}")
        self.assertEqual(response.status_code, 403)

    def test_idor_user_a_cannot_access_user_b_payroll(self):
        """[IDOR 방어] 유저 A가 유저 B의 사업장 ID로 급여/직원 목록 조회 시 403 Forbidden 반환."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        response = self.client.get(f"/api/businesses/{self.business_b.id}/payroll/employees/")
        self.assertEqual(response.status_code, 403)

    def test_idor_user_a_cannot_access_user_b_reports(self):
        """[IDOR 방어] 유저 A가 유저 B의 사업장 ID로 리포트 현황 조회 시 403 Forbidden 반환."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        response = self.client.get(f"/api/businesses/{self.business_b.id}/reports/2026-08/")
        self.assertEqual(response.status_code, 403)

    def test_idor_user_a_cannot_access_user_b_benchmark(self):
        """[IDOR 방어] 유저 A가 유저 B의 사업장 ID로 AI 벤치마크 진단 조회 시 403 Forbidden 반환."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        response = self.client.get(f"/api/businesses/{self.business_b.id}/benchmark/?year=2026&month=8")
        self.assertEqual(response.status_code, 403)

    def test_idor_user_a_cannot_access_user_b_settings(self):
        """[IDOR 방어] 유저 A가 유저 B의 사업장 설정 조회 시 403 Forbidden 반환."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        response = self.client.get(f"/api/businesses/{self.business_b.id}/settings/business/")
        self.assertEqual(response.status_code, 403)

    def test_logout_deletes_token(self):
        """로그아웃 호출 시 토큰이 DB에서 삭제되고 이후 요청은 401 반환."""
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token_a.key}")
        response = self.client.post("/api/auth/logout/")
        self.assertEqual(response.status_code, 200)

        # 토큰 삭제 확인
        self.assertFalse(Token.objects.filter(key=self.token_a.key).exists())

        # 삭제된 토큰으로 재요청 시 401 반환
        retry_response = self.client.get(f"/api/businesses/{self.business_a.id}/")
        self.assertEqual(retry_response.status_code, 401)


@override_settings(DEMO_MODE=False, ALLOW_UNOWNED_BUSINESS_ACCESS=False)
class UnownedBusinessFailClosedTests(TestCase):
    """owner가 지정되지 않은 사업장이 fail-closed로 차단되는지 검증한다.

    직전까지는 `business.owner_id is not None and ...` 조건 때문에 owner=NULL인
    사업장에 인증된 아무 사용자나 200으로 접근할 수 있었다. 이 스위트가 그 회귀를
    막는다.
    """

    ORPHAN_PATHS = [
        "/api/businesses/{b}/",
        "/api/businesses/{b}/payroll/employees/",
        "/api/businesses/{b}/payroll/summary/?year=2026&month=8",
        "/api/businesses/{b}/analytics/summary/?year=2026&month=8",
        "/api/businesses/{b}/analytics/cost-ratio/?year=2026&month=8",
        "/api/businesses/{b}/settings/business/",
        "/api/businesses/{b}/settings/subscription/",
        "/api/businesses/{b}/reports/2026-08/",
        "/api/businesses/{b}/benchmark/?year=2026&month=8",
        "/api/businesses/{b}/transactions/?year=2026&month=8",
        "/api/transactions/?business_id={b}",
        "/api/chat/messages/?business_id={b}",
        "/api/tax/vat-forecast/?business_id={b}&year_month=2026-08",
    ]

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="stranger", password="password123")
        self.token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Token {self.token.key}")
        self.orphan = Business.objects.create(
            owner=None,
            business_name="소유자 미지정 사업장",
            business_number="999-99-99999",
            is_demo=False,
        )

    def test_unowned_business_is_forbidden_for_any_authenticated_user(self):
        for path in self.ORPHAN_PATHS:
            with self.subTest(path=path):
                response = self.client.get(path.format(b=self.orphan.id))
                self.assertEqual(
                    response.status_code,
                    403,
                    f"{path} 가 owner=NULL 사업장에 {response.status_code}를 "
                    f"반환했습니다 (403이어야 함)",
                )

    def test_unauthenticated_gets_401_not_403(self):
        anon = APIClient()
        # 테스트 러너가 기본 토큰을 주입하므로 명시적으로 비운다.
        anon.credentials(HTTP_AUTHORIZATION="")
        response = anon.get(f"/api/businesses/{self.orphan.id}/payroll/employees/")
        self.assertEqual(response.status_code, 401)


@override_settings(DEMO_MODE=True, ALLOW_UNOWNED_BUSINESS_ACCESS=False, DEMO_USERNAME="demo")
class DemoGuestAuthenticationTests(TestCase):
    """DEMO_MODE 게스트 경로가 데모 사업장 밖으로 새지 않는지 검증한다."""

    def setUp(self):
        self.demo_user = User.objects.create_user(username="demo", password="demo1234")
        self.demo_business = Business.objects.create(
            owner=self.demo_user,
            business_name="수아네 커피집",
            business_number="214-86-78901",
            is_demo=True,
        )
        self.real_user = User.objects.create_user(username="real_owner", password="password123")
        self.real_business = Business.objects.create(
            owner=self.real_user,
            business_name="실제 사용자 카페",
            business_number="333-33-33333",
            is_demo=False,
        )
        self.anon = APIClient()
        self.anon.credentials(HTTP_AUTHORIZATION="")

    def test_guest_can_read_demo_business(self):
        """토큰 없이도 데모 사업장은 조회된다 (부스 시연용)."""
        response = self.anon.get(f"/api/businesses/{self.demo_business.id}/")
        self.assertEqual(response.status_code, 200)

    def test_guest_cannot_read_real_user_business(self):
        """[핵심] 게스트는 is_demo=False 사업장에 절대 접근할 수 없다."""
        response = self.anon.get(f"/api/businesses/{self.real_business.id}/")
        self.assertEqual(response.status_code, 403)

    def test_guest_cannot_read_real_user_payroll(self):
        """주민등록번호가 담긴 급여 API도 차단된다."""
        response = self.anon.get(
            f"/api/businesses/{self.real_business.id}/payroll/employees/"
        )
        self.assertEqual(response.status_code, 403)

    def test_guest_cannot_read_real_user_transactions(self):
        response = self.anon.get(f"/api/transactions/?business_id={self.real_business.id}")
        self.assertEqual(response.status_code, 403)

    @override_settings(DEMO_MODE=False)
    def test_demo_mode_off_requires_token_even_for_demo_business(self):
        """DEMO_MODE=0이면 데모 사업장도 토큰을 요구한다."""
        response = self.anon.get(f"/api/businesses/{self.demo_business.id}/")
        self.assertEqual(response.status_code, 401)

    def test_invalid_token_is_401_not_downgraded_to_guest(self):
        """잘못된 토큰이 게스트로 강등되지 않는다."""
        bad = APIClient()
        bad.credentials(HTTP_AUTHORIZATION="Token deadbeefdeadbeefdeadbeef")
        response = bad.get(f"/api/businesses/{self.demo_business.id}/")
        self.assertEqual(response.status_code, 401)

    def test_real_owner_still_reaches_own_business_with_token(self):
        owned = APIClient()
        token = Token.objects.create(user=self.real_user)
        owned.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
        response = owned.get(f"/api/businesses/{self.real_business.id}/")
        self.assertEqual(response.status_code, 200)


@override_settings(DEMO_MODE=False)
class RegisterPasswordPolicyTests(TestCase):
    """회원가입 비밀번호 정책 검증."""

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION="")

    def test_weak_numeric_password_is_rejected(self):
        response = self.client.post(
            "/api/auth/register/",
            {"username": "weakuser", "password": "1234"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_common_password_is_rejected(self):
        response = self.client.post(
            "/api/auth/register/",
            {"username": "weakuser2", "password": "password"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_strong_password_is_accepted(self):
        response = self.client.post(
            "/api/auth/register/",
            {"username": "stronguser", "password": "Caffeine!2026"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
