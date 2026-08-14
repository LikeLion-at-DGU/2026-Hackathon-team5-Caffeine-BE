from datetime import date
from decimal import Decimal

from django.test import TestCase

from businesses.models import Business
from transactions.models import Transaction, TransactionDuplicate
from transactions.services.duplicate_detector import DuplicateDetector
from transactions.services.ingestion_service import TransactionIngestionService
from transactions.services.types import NormalizedTransaction


class TransactionServiceTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(business_name="카페비서 데모카페")
        self.ingestion = TransactionIngestionService()

    def normalized(self, **overrides):
        values = {
            "source_type": Transaction.SourceType.CARD_PURCHASE,
            "external_id": "card-001",
            "transaction_type": Transaction.TransactionType.PURCHASE,
            "transaction_date": date(2026, 8, 3),
            "merchant_name": "서울우유 성동대리점",
            "merchant_business_number": "1234567890",
            "supply_amount": Decimal("170000.00"),
            "vat_amount": Decimal("17000.00"),
            "total_amount": Decimal("187000.00"),
            "raw_data": {"source": "mock"},
        }
        values.update(overrides)
        return NormalizedTransaction(**values)

    def test_ingestion_is_idempotent_and_refreshes_source_fields(self):
        item, created = self.ingestion.save(self.business, self.normalized())
        self.assertTrue(created)

        item.category = Transaction.Category.RAW_MATERIAL
        item.classification_source = Transaction.ClassificationSource.USER
        item.save()

        refreshed, created = self.ingestion.save(
            self.business,
            self.normalized(merchant_name="서울우유 새 상호"),
        )

        self.assertFalse(created)
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertEqual(refreshed.merchant_name, "서울우유 새 상호")
        self.assertEqual(refreshed.category, Transaction.Category.RAW_MATERIAL)
        self.assertEqual(refreshed.classification_source, Transaction.ClassificationSource.USER)

    def test_duplicate_detector_matches_different_sources(self):
        card, _ = self.ingestion.save(self.business, self.normalized())
        invoice, _ = self.ingestion.save(
            self.business,
            self.normalized(
                source_type=Transaction.SourceType.TAX_INVOICE,
                external_id="invoice-001",
            ),
        )

        results = DuplicateDetector().detect(invoice)

        self.assertEqual(len(results), 1)
        duplicate = results[0]
        self.assertEqual(duplicate.primary_transaction, card)
        self.assertEqual(duplicate.suspected_transaction, invoice)
        self.assertEqual(duplicate.status, TransactionDuplicate.Status.PENDING)

    def test_duplicate_detector_does_not_duplicate_existing_pair(self):
        card, _ = self.ingestion.save(self.business, self.normalized())
        invoice, _ = self.ingestion.save(
            self.business,
            self.normalized(
                source_type=Transaction.SourceType.TAX_INVOICE,
                external_id="invoice-001",
            ),
        )
        detector = DuplicateDetector()

        detector.detect(invoice)
        detector.detect(card)

        self.assertEqual(TransactionDuplicate.objects.count(), 1)

    def test_cancelled_transaction_is_not_a_duplicate_candidate(self):
        self.ingestion.save(self.business, self.normalized())
        cancelled, _ = self.ingestion.save(
            self.business,
            self.normalized(
                source_type=Transaction.SourceType.TAX_INVOICE,
                external_id="invoice-001",
                cancel_status=Transaction.CancelStatus.CANCELLED,
            ),
        )

        self.assertEqual(DuplicateDetector().detect(cancelled), [])
