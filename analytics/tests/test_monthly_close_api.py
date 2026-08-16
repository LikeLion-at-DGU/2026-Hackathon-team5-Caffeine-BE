from django.test import TestCase
from rest_framework.test import APIClient

from analytics.models import MonthlyClose
from businesses.models import Business


class MonthlyCloseAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(business_name="카페비서")
        self.url = f"/api/businesses/{self.business.id}/analytics/monthly-summary/close/"

    def test_close_month_success(self):
        response = self.client.post(self.url, {"year": 2026, "month": 8}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"]["is_export_available"])
        self.assertTrue(MonthlyClose.objects.filter(business=self.business, year=2026, month=8).exists())

    def test_close_already_closed_month_returns_409(self):
        self.client.post(self.url, {"year": 2026, "month": 8}, format="json")
        response = self.client.post(self.url, {"year": 2026, "month": 8}, format="json")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "ALREADY_CLOSED")

    def test_close_missing_period_returns_400(self):
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_close_different_months_both_succeed(self):
        response1 = self.client.post(self.url, {"year": 2026, "month": 7}, format="json")
        response2 = self.client.post(self.url, {"year": 2026, "month": 8}, format="json")

        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
        self.assertEqual(MonthlyClose.objects.filter(business=self.business).count(), 2)

    def test_close_same_month_different_business_both_succeed(self):
        other_business = Business.objects.create(business_name="옆동네카페")

        response1 = self.client.post(self.url, {"year": 2026, "month": 8}, format="json")
        response2 = self.client.post(
            f"/api/businesses/{other_business.id}/analytics/monthly-summary/close/",
            {"year": 2026, "month": 8}, format="json",
        )

        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)