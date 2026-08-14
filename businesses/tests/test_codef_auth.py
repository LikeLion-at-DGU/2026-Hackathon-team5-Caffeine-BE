from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase
from unittest.mock import patch

from businesses.models import Business, CodefConnection


@override_settings(CODEF_MODE="mock")
class CodefAuthTests(APITestCase):
    def setUp(self):
        self.business = Business.objects.create(business_name="카페비서 데모카페")

    def test_hometax_auth_request_sets_auth_required(self):
        url = reverse("business-codef-auth", kwargs={"pk": self.business.id})
        res = self.client.post(url, {"connection_type": "HOMETAX"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "AUTH_REQUIRED")

        conn = CodefConnection.objects.get(business=self.business, connection_type="HOMETAX")
        self.assertTrue(conn.continue_2way)
        self.assertEqual(conn.jti, "mock-jti-001")
        self.assertIsInstance(conn.two_way_timestamp, int)

    def test_card_auth_request_sets_connected(self):
        url = reverse("business-codef-auth", kwargs={"pk": self.business.id})
        res = self.client.post(url, {"connection_type": "CARD"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "CONNECTED")

        conn = CodefConnection.objects.get(business=self.business, connection_type="CARD")
        self.assertTrue(conn.connected_id)

    def test_request_marks_failed_when_outcome_is_failure(self):
        business = self.business
        url = reverse("business-codef-auth", kwargs={"pk": business.id})
        fail_result = {"outcome": "FAILURE", "error_code": "MOCK-90000", "error_message": "mock failure"}
        with patch("businesses.services.codef_auth_service.get_codef_provider") as mock_factory:
            mock_factory.return_value.request_auth.return_value = fail_result
            res = self.client.post(url, {"connection_type": "HOMETAX"}, format="json")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["status"], "FAILED")
        conn = CodefConnection.objects.get(business=business, connection_type="HOMETAX")
        self.assertEqual(conn.status, "FAILED")
        self.assertEqual(conn.last_error_code, "MOCK-90000")
        self.assertFalse(conn.continue_2way)  # 실패인데 2-way 값이 남아있으면 버그

    def test_request_success_clears_stale_error_from_previous_failure(self):
        # 이전에 실패 기록이 있어도, 새 요청이 성공하면 그 기록은 지워져야 함
        business = self.business
        conn = CodefConnection.objects.create(
            business=business, connection_type="HOMETAX",
            status="FAILED", last_error_code="CF-11111", last_error_message="이전 실패",
        )
        url = reverse("business-codef-auth", kwargs={"pk": business.id})
        res = self.client.post(url, {"connection_type": "HOMETAX"}, format="json")

        self.assertEqual(res.status_code, 200)
        conn.refresh_from_db()
        self.assertEqual(conn.status, "AUTH_REQUIRED")
        self.assertEqual(conn.last_error_code, "")
        self.assertEqual(conn.last_error_message, "")
        
    def test_status_always_shows_both_types_with_disconnected_default(self):
        # 아직 아무 인증도 안 한 상태에서도 CARD/HOMETAX 둘 다 응답에 나와야 함
        url = reverse("business-codef-auth-status", kwargs={"pk": self.business.id})
        res = self.client.get(url)
        types = {c["type"]: c["status"] for c in res.data["connections"]}
        self.assertEqual(types, {"CARD": "DISCONNECTED", "HOMETAX": "DISCONNECTED"})

    def test_status_shows_both_connections_after_auth(self):
        self.client.post(reverse("business-codef-auth", kwargs={"pk": self.business.id}),
                            {"connection_type": "HOMETAX"}, format="json")
        self.client.post(reverse("business-codef-auth", kwargs={"pk": self.business.id}),
                            {"connection_type": "CARD"}, format="json")

        url = reverse("business-codef-auth-status", kwargs={"pk": self.business.id})
        res = self.client.get(url)
        types = {c["type"]: c["status"] for c in res.data["connections"]}
        self.assertEqual(types["CARD"], "CONNECTED")
        self.assertEqual(types["HOMETAX"], "AUTH_REQUIRED")