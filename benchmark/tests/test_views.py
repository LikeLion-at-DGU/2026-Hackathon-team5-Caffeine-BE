from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from businesses.models import Business


class BenchmarkViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(
            id=1,
            business_name="카페비서 1호점",
            business_number="1234567890",
        )

    def test_dashboard_success(self):
        response = self.client.get(f"/api/businesses/{self.business.id}/benchmark/?year=2026&month=8")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["code"], "BENCHMARK_DASHBOARD_SUCCESS")
        self.assertIn("overview", data["data"])
        self.assertIn("ai_prescriptions", data["data"])
        self.assertIn("overall_health", data["data"])
        self.assertIn("category_comparison", data["data"])
        self.assertIn("monthly_trends", data["data"])

    def test_categories_view_success(self):
        response = self.client.get(f"/api/businesses/{self.business.id}/benchmark/categories/?year=2026&month=8")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["code"], "BENCHMARK_CATEGORIES_SUCCESS")
        self.assertIn("category_comparison", data["data"])

    def test_trend_view_success(self):
        response = self.client.get(f"/api/businesses/{self.business.id}/benchmark/trend/?year=2026&month=8")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["code"], "BENCHMARK_TREND_SUCCESS")
        self.assertIn("monthly_trends", data["data"])
        self.assertIn("mom_profit_improvement", data["data"])

    def test_ai_diagnosis_refresh_success(self):
        response = self.client.post(
            f"/api/businesses/{self.business.id}/benchmark/ai-diagnosis/",
            data={"year": 2026, "month": 8},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["code"], "BENCHMARK_AI_DIAGNOSIS_REFRESHED")
        self.assertIn("overall_health", data["data"])
        self.assertIn("ai_prescriptions", data["data"])

    def test_unknown_business_returns_404(self):
        response = self.client.get("/api/businesses/99999/benchmark/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(response.json()["code"], "BUSINESS_NOT_FOUND")
