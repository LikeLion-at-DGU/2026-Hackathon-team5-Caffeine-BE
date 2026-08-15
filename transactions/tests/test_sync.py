from datetime import date

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from businesses.models import Business
from transactions.models import Transaction
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

        self.assertEqual(result["created_count"], 29)
        self.assertEqual(Transaction.objects.count(), 29)
        self.assertEqual(
            Transaction.objects.filter(source_type=Transaction.SourceType.CARD_PURCHASE).count(),
            12,
        )
        self.assertFalse(
            Transaction.objects.filter(external_id__contains="credit-card-sales").exists()
        )

    def test_sync_is_idempotent(self):
        self.sync_all()
        second = self.sync_all()

        self.assertEqual(second["created_count"], 0)
        self.assertEqual(second["updated_count"], 29)
        self.assertEqual(Transaction.objects.count(), 29)

    def test_user_category_survives_resync(self):
        self.sync_all()
        transaction = Transaction.objects.filter(
            source_type=Transaction.SourceType.CARD_PURCHASE
        ).first()
        transaction.category = Transaction.Category.OTHER
        transaction.classification_source = Transaction.ClassificationSource.USER
        transaction.classification_confidence = None
        transaction.save()

        self.sync_all()
        transaction.refresh_from_db()

        self.assertEqual(transaction.category, Transaction.Category.OTHER)
        self.assertEqual(transaction.classification_source, Transaction.ClassificationSource.USER)

    def test_date_range_filters_mock_records(self):
        result = self.service.sync(
            self.business,
            date(2026, 8, 1),
            date(2026, 8, 5),
            [Transaction.SourceType.CARD_PURCHASE],
        )

        self.assertEqual(result["created_count"], 2)
        self.assertEqual(result["skipped_outside_period_count"], 10)

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


@override_settings(CODEF_MODE="mock")
class TransactionSyncApiTests(APITestCase):
    def setUp(self):
        self.business = Business.objects.create(
            business_name="카페비서",
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
        self.assertEqual(response.data["data"]["created_count"], 29)

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
