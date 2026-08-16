from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from businesses.models import Business
from transactions.models import Transaction


class AnalyticsApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(
            business_name="카페비서",
            tax_type="GENERAL",
        )
        Transaction.objects.create(
            business=self.business,
            source_type=Transaction.SourceType.CARD_PURCHASE,
            external_id="analytics-purchase",
            transaction_type=Transaction.TransactionType.PURCHASE,
            transaction_date="2026-08-10",
            total_amount=Decimal("300000"),
            category=Transaction.Category.RAW_MATERIAL,
            expense_purpose=Transaction.ExpensePurpose.BUSINESS,
        )
        self.base = f"/api/businesses/{self.business.id}/analytics"

    def test_cost_ratio_returns_transaction_categories(self):
        response = self.client.get(f"{self.base}/cost-ratio/", {"year": 2026, "month": 8})

        self.assertEqual(response.status_code, 200)
        items = response.data["data"]["items"]
        self.assertTrue(any(item["category"] == "RAW_MATERIAL" for item in items))

    def test_category_trend_returns_requested_month_window(self):
        response = self.client.get(
            f"{self.base}/trend/",
            {
                "category": "RAW_MATERIAL",
                "end_year": 2026,
                "end_month": 8,
                "months": 3,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]["items"]), 3)
        self.assertEqual(response.data["data"]["items"][-1]["amount"], 300000)

    def test_summary_includes_tax_forecast_shape(self):
        response = self.client.get(f"{self.base}/summary/", {"year": 2026, "month": 8})

        self.assertEqual(response.status_code, 200)
        self.assertIn("sales_tax", response.data["data"]["vat_breakdown"])
