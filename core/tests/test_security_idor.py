from django.contrib.auth.models import User
from django.test import TestCase
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
                "password": "password123",
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
