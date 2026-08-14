from django.test import TestCase

from businesses.models import Business
from transactions.models import Transaction, TransactionDuplicate
from transactions.serializers import (
    DuplicateResolutionSerializer,
    TransactionCategoryUpdateSerializer,
    TransactionSyncRequestSerializer,
)


class TransactionSerializerContractTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(business_name="카페비서 데모카페")

    def test_sync_request_accepts_planned_contract(self):
        serializer = TransactionSyncRequestSerializer(
            data={
                "business_id": self.business.id,
                "start_date": "2026-07-01",
                "end_date": "2026-08-31",
                "sources": [
                    Transaction.SourceType.CARD_PURCHASE,
                    Transaction.SourceType.CASH_RECEIPT_PURCHASE,
                    Transaction.SourceType.CASH_RECEIPT_SALE,
                    Transaction.SourceType.TAX_INVOICE,
                ],
            }
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["business"], self.business)

    def test_sync_request_rejects_reversed_date_range(self):
        serializer = TransactionSyncRequestSerializer(
            data={
                "business_id": self.business.id,
                "start_date": "2026-08-31",
                "end_date": "2026-07-01",
                "sources": [Transaction.SourceType.CARD_PURCHASE],
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("end_date", serializer.errors)

    def test_category_update_accepts_known_category(self):
        serializer = TransactionCategoryUpdateSerializer(
            data={"category": Transaction.Category.RAW_MATERIAL}
        )

        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_duplicate_resolution_only_accepts_terminal_status(self):
        pending = DuplicateResolutionSerializer(data={"status": TransactionDuplicate.Status.PENDING})
        confirmed = DuplicateResolutionSerializer(data={"status": TransactionDuplicate.Status.CONFIRMED})

        self.assertFalse(pending.is_valid())
        self.assertTrue(confirmed.is_valid(), confirmed.errors)
