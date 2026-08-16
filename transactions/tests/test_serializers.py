from datetime import date
from decimal import Decimal

from django.test import TestCase

from businesses.models import Business
from transactions.models import MonthlySalesSummary, Transaction, TransactionDuplicate
from transactions.serializers import (
    DuplicateResolutionSerializer,
    TransactionCategoryUpdateSerializer,
    TransactionPurposeUpdateSerializer,
    TransactionSerializer,
    TransactionSyncRequestSerializer,
)
from transactions.services.querysets import with_pending_duplicate_flag


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
                    Transaction.SourceType.CASH_RECEIPT_SALE,
                    Transaction.SourceType.TAX_INVOICE,
                    MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
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

    def test_purpose_update_accepts_business_or_personal(self):
        business = TransactionPurposeUpdateSerializer(
            data={"expense_purpose": Transaction.ExpensePurpose.BUSINESS}
        )
        personal = TransactionPurposeUpdateSerializer(
            data={"expense_purpose": Transaction.ExpensePurpose.PERSONAL}
        )

        self.assertTrue(business.is_valid(), business.errors)
        self.assertTrue(personal.is_valid(), personal.errors)

    def test_duplicate_resolution_only_accepts_terminal_status(self):
        pending = DuplicateResolutionSerializer(data={"status": TransactionDuplicate.Status.PENDING})
        confirmed = DuplicateResolutionSerializer(data={"status": TransactionDuplicate.Status.CONFIRMED})

        self.assertFalse(pending.is_valid())
        self.assertTrue(confirmed.is_valid(), confirmed.errors)

    def test_transaction_list_serialization_does_not_query_per_item(self):
        for index in range(5):
            Transaction.objects.create(
                business=self.business,
                source_type=Transaction.SourceType.CARD_PURCHASE,
                external_id=f"card-{index}",
                transaction_type=Transaction.TransactionType.PURCHASE,
                transaction_date=date(2026, 8, 3),
                total_amount=Decimal("11000.00"),
            )
        queryset = with_pending_duplicate_flag(
            Transaction.objects.filter(business=self.business)
        )

        with self.assertNumQueries(1):
            data = TransactionSerializer(queryset, many=True).data

        self.assertEqual(len(data), 5)
