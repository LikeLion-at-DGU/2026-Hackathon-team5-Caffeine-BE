from datetime import date
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from businesses.models import Business, CodefConnection
from integrations.codef.base import CodefBusinessAccessError
from integrations.codef.real import RealCodefProvider
from transactions.models import MonthlySalesSummary, Transaction
from transactions.services.sync_service import (
    TransactionSourceMismatchError,
    TransactionSyncService,
)


@override_settings(CODEF_MODE="mock")
class TransactionSyncServiceTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            business_name="카페비서",
            business_number="1234567890",
        )
        self.service = TransactionSyncService()

    def sync_all(self):
        return self.service.sync(
            self.business,
            date(2026, 8, 1),
            date(2026, 8, 31),
            [
                Transaction.SourceType.CARD_PURCHASE,
                Transaction.SourceType.CASH_RECEIPT_SALE,
                Transaction.SourceType.TAX_INVOICE,
            ],
        )

    def test_sync_creates_only_individual_transaction_sources(self):
        result = self.sync_all()

        self.assertEqual(result["created_count"], 19)
        self.assertEqual(Transaction.objects.count(), 19)
        self.assertEqual(
            Transaction.objects.filter(source_type=Transaction.SourceType.CARD_PURCHASE).count(),
            11,
        )
        self.assertFalse(
            Transaction.objects.filter(external_id__contains="credit-card-sales").exists()
        )

    def test_sync_is_idempotent(self):
        self.sync_all()
        second = self.sync_all()

        self.assertEqual(second["created_count"], 0)
        self.assertEqual(second["updated_count"], 19)
        self.assertEqual(Transaction.objects.count(), 19)

    def test_user_category_survives_resync(self):
        self.sync_all()
        transaction = Transaction.objects.filter(
            source_type=Transaction.SourceType.CARD_PURCHASE
        ).first()
        transaction.category = Transaction.Category.OTHER
        transaction.classification_source = Transaction.ClassificationSource.USER
        transaction.expense_purpose = Transaction.ExpensePurpose.BUSINESS
        transaction.expense_purpose_source = Transaction.ClassificationSource.USER
        transaction.classification_confidence = None
        transaction.save()

        self.sync_all()
        transaction.refresh_from_db()

        self.assertEqual(transaction.category, Transaction.Category.OTHER)
        self.assertEqual(transaction.classification_source, Transaction.ClassificationSource.USER)
        self.assertEqual(
            transaction.expense_purpose,
            Transaction.ExpensePurpose.BUSINESS,
        )
        self.assertEqual(
            transaction.expense_purpose_source,
            Transaction.ClassificationSource.USER,
        )

    def test_date_range_filters_mock_records(self):
        result = self.service.sync(
            self.business,
            date(2026, 8, 1),
            date(2026, 8, 5),
            [Transaction.SourceType.CARD_PURCHASE],
        )

        self.assertEqual(result["created_count"], 3)
        self.assertEqual(result["skipped_outside_period_count"], 18)

    def test_business_number_mismatch_is_rejected(self):
        other = Business.objects.create(
            business_name="다른 사업장",
            business_number="9999999999",
        )

        with self.assertRaises(TransactionSourceMismatchError):
            self.service.sync(
                other,
                date(2026, 8, 1),
                date(2026, 8, 31),
                [Transaction.SourceType.CARD_PURCHASE],
            )

    def test_credit_card_sales_summary_is_stored_separately_from_transactions(self):
        result = self.service.sync(
            self.business,
            date(2026, 8, 1),
            date(2026, 8, 31),
            [MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY],
        )

        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["transaction_created_count"], 0)
        self.assertEqual(result["sales_summary_created_count"], 1)
        self.assertEqual(result["skipped_outside_period_count"], 5)
        self.assertEqual(Transaction.objects.count(), 0)
        summary = MonthlySalesSummary.objects.get()
        self.assertEqual(summary.year_month, "2026-08")
        self.assertEqual(summary.transaction_count, 867)

    def test_credit_card_sales_summary_sync_is_idempotent(self):
        sources = [MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY]
        self.service.sync(self.business, date(2026, 8, 1), date(2026, 8, 31), sources)

        second = self.service.sync(
            self.business,
            date(2026, 8, 1),
            date(2026, 8, 31),
            sources,
        )

        self.assertEqual(second["created_count"], 0)
        self.assertEqual(second["updated_count"], 1)
        self.assertEqual(second["sales_summary_updated_count"], 1)
        self.assertEqual(MonthlySalesSummary.objects.count(), 1)

    def test_credit_card_sales_summary_rejects_wrong_mock_business(self):
        other = Business.objects.create(
            business_name="다른 사업장",
            business_number="9999999999",
        )

        with self.assertRaises(TransactionSourceMismatchError):
            self.service.sync(
                other,
                date(2026, 8, 1),
                date(2026, 8, 31),
                [MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY],
            )

    def test_new_duplicate_count_uses_created_events_not_net_table_difference(self):
        with patch.object(
            self.service.duplicate_detector,
            "detect_with_count",
            return_value=([], 1),
        ):
            result = self.service.sync(
                self.business,
                date(2026, 8, 1),
                date(2026, 8, 31),
                [Transaction.SourceType.CARD_PURCHASE],
            )

        self.assertEqual(result["new_duplicate_candidate_count"], 11)
        self.assertEqual(result["duplicate_candidate_total_count"], 0)

    def test_real_summary_access_requires_this_business_hometax_connection(self):
        provider = RealCodefProvider()
        with self.assertRaises(CodefBusinessAccessError):
            provider.ensure_business_access(
                self.business,
                MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
            )

        CodefConnection.objects.create(
            business=self.business,
            connection_type="HOMETAX",
            status="CONNECTED",
        )

        provider.ensure_business_access(
            self.business,
            MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
        )


@override_settings(CODEF_MODE="mock")
class TransactionSyncApiTests(APITestCase):
    def setUp(self):
        self.business = Business.objects.create(
            business_name="앵무101",
            business_number="1234567890",
        )

    def test_sync_endpoint_imports_mock_transactions(self):
        response = self.client.post(
            reverse("transaction-sync"),
            {
                "business_id": self.business.id,
                "start_date": "2026-08-01",
                "end_date": "2026-08-31",
                "sources": [
                    Transaction.SourceType.CARD_PURCHASE,
                    Transaction.SourceType.CASH_RECEIPT_SALE,
                    Transaction.SourceType.TAX_INVOICE,
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["code"], "TRANSACTION_SYNC_SUCCESS")
        self.assertEqual(response.data["data"]["created_count"], 19)

    def test_unavailable_cash_receipt_purchase_is_rejected(self):
        response = self.client.post(
            reverse("transaction-sync"),
            {
                "business_id": self.business.id,
                "start_date": "2026-08-01",
                "end_date": "2026-08-31",
                "sources": [Transaction.SourceType.CASH_RECEIPT_PURCHASE],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "INVALID_TRANSACTION_SYNC_REQUEST")

    def test_sync_endpoint_accepts_credit_card_monthly_sales_summary(self):
        response = self.client.post(
            reverse("transaction-sync"),
            {
                "business_id": self.business.id,
                "start_date": "2026-08-01",
                "end_date": "2026-08-31",
                "sources": [
                    MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["sales_summary_created_count"], 1)
        self.assertEqual(MonthlySalesSummary.objects.count(), 1)
