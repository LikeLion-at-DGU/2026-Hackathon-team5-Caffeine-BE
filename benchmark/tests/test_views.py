from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from businesses.models import Business
from benchmark.models import AIDiagnosisHistory
from transactions.models import MonthlySalesSummary


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

    def test_dashboard_invalidates_ai_cache_when_financial_data_changes(self):
        url = f"/api/businesses/{self.business.id}/benchmark/?year=2026&month=8"
        first = self.client.get(url)
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        history = AIDiagnosisHistory.objects.get(
            business=self.business,
            year_month="2026-08",
        )
        self.assertEqual(
            history.raw_response["_calculation_fingerprint"]["total_revenue"],
            0,
        )

        MonthlySalesSummary.objects.create(
            business=self.business,
            year=2026,
            month=8,
            source_type=MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
            total_amount=5_000_000,
            transaction_count=50,
        )
        second = self.client.get(url)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        history.refresh_from_db()

        self.assertEqual(second.json()["data"]["overview"]["total_revenue"], 5_000_000)
        self.assertEqual(
            history.raw_response["_calculation_fingerprint"]["total_revenue"],
            5_000_000,
        )

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
