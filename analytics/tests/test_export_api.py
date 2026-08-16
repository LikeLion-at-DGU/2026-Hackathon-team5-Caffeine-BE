import tempfile
from decimal import Decimal

from django.test import TestCase
from django.test.utils import override_settings
from rest_framework.test import APIClient

from businesses.models import Business
from tax.models import MonthlyClose
from transactions.models import Transaction


class AnalyticsExportAPITests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._media_directory = tempfile.TemporaryDirectory()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_directory.name)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        cls._media_directory.cleanup()

    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(
            business_name="카페비서",
            tax_type="GENERAL",
        )
        self.url = f"/api/businesses/{self.business.id}/analytics/export/"
        self.close = MonthlyClose.objects.create(
            business=self.business,
            year=2026,
            month=8,
            status=MonthlyClose.Status.CLOSED,
        )
        Transaction.objects.create(
            business=self.business,
            source_type=Transaction.SourceType.CARD_PURCHASE,
            external_id="analytics-export-purchase",
            transaction_type=Transaction.TransactionType.PURCHASE,
            transaction_date="2026-08-10",
            merchant_name="서울우유 대리점",
            total_amount=Decimal("300000"),
            category=Transaction.Category.RAW_MATERIAL,
            expense_purpose=Transaction.ExpensePurpose.BUSINESS,
        )

    def test_export_csv_uses_report_data_after_tax_close(self):
        response = self.client.get(
            self.url,
            {"year": 2026, "month": 8, "file_type": "csv"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        content = response.content.decode("utf-8-sig")
        self.assertIn("[매입 증빙]", content)
        self.assertIn("서울우유 대리점", content)

    def test_export_pdf_after_tax_close(self):
        response = self.client.get(
            self.url,
            {"year": 2026, "month": 8, "file_type": "pdf"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_export_requires_tax_month_close(self):
        self.close.delete()

        response = self.client.get(
            self.url,
            {"year": 2026, "month": 8, "file_type": "csv"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "MONTHLY_CLOSE_REQUIRED")

    def test_export_rejects_invalid_query(self):
        response = self.client.get(
            self.url,
            {"year": 2026, "month": 13, "file_type": "xlsx"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "INVALID_EXPORT_QUERY")
        self.assertIn("month", response.data["errors"])
        self.assertIn("file_type", response.data["errors"])

    def test_export_is_scoped_to_existing_business(self):
        response = self.client.get(
            "/api/businesses/999999/analytics/export/",
            {"year": 2026, "month": 8, "file_type": "csv"},
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "BUSINESS_NOT_FOUND")
