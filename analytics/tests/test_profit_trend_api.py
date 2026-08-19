from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from businesses.models import Business
from transactions.models import MonthlySalesSummary


class ProfitTrendAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.business = Business.objects.create(
            business_name="카페비서",
            tax_type="GENERAL",
        )

        self.url = (
            f"/api/businesses/{self.business.id}/analytics/profit-trend/"
        )

        sales_by_month = {
            3: 8_200_000,
            4: 8_700_000,
            5: 9_100_000,
            6: 9_600_000,
            7: 10_200_000,
            8: 10_800_000,
        }

        for month, amount in sales_by_month.items():
            MonthlySalesSummary.objects.create(
                business=self.business,
                source_type="CREDIT_CARD_SALES_SUMMARY",
                year=2026,
                month=month,
                transaction_count=100,
                total_amount=Decimal(str(amount)),
            )

    def test_profit_trend_returns_six_months(self):
        response = self.client.get(
            self.url,
            {
                "end_year": 2026,
                "end_month": 8,
                "months": 6,
            },
        )

        self.assertEqual(response.status_code, 200)

        months = response.data["data"]["months"]

        self.assertEqual(len(months), 6)
        self.assertEqual(months[0]["year_month"], "2026-03")
        self.assertEqual(months[-1]["year_month"], "2026-08")

    def test_profit_trend_returns_sales_and_net_profit(self):
        response = self.client.get(
            self.url,
            {
                "end_year": 2026,
                "end_month": 8,
                "months": 6,
            },
        )

        august = response.data["data"]["months"][-1]

        self.assertEqual(august["total_sales"], 10_800_000)
        self.assertIn("net_profit", august)

    def test_profit_trend_handles_year_boundary(self):
        response = self.client.get(
            self.url,
            {
                "end_year": 2026,
                "end_month": 2,
                "months": 6,
            },
        )

        months = response.data["data"]["months"]

        self.assertEqual(
            [item["year_month"] for item in months],
            [
                "2025-09",
                "2025-10",
                "2025-11",
                "2025-12",
                "2026-01",
                "2026-02",
            ],
        )

    def test_profit_trend_requires_end_year_and_month_together(self):
        response = self.client.get(
            self.url,
            {
                "end_year": 2026,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["code"],
            "INVALID_PROFIT_TREND_QUERY",
        )

    def test_profit_trend_business_not_found(self):
        response = self.client.get(
            "/api/businesses/999999/analytics/profit-trend/",
            {
                "end_year": 2026,
                "end_month": 8,
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.data["code"],
            "BUSINESS_NOT_FOUND",
        )