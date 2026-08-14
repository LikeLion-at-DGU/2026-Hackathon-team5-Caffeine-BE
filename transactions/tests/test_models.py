from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction as db_transaction
from django.test import TestCase

from businesses.models import Business
from transactions.models import Transaction, TransactionDuplicate


class TransactionModelTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(business_name="카페비서 데모카페")

    def create_transaction(self, external_id="card-001", **overrides):
        values = {
            "business": self.business,
            "source_type": Transaction.SourceType.CARD_PURCHASE,
            "external_id": external_id,
            "transaction_type": Transaction.TransactionType.PURCHASE,
            "transaction_date": date(2026, 8, 3),
            "merchant_name": "서울우유 성동대리점",
            "supply_amount": Decimal("170000.00"),
            "vat_amount": Decimal("17000.00"),
            "total_amount": Decimal("187000.00"),
        }
        values.update(overrides)
        return Transaction.objects.create(**values)

    def test_defaults_are_unclassified_and_normal(self):
        item = self.create_transaction()

        self.assertEqual(item.category, Transaction.Category.UNCLASSIFIED)
        self.assertEqual(item.classification_source, Transaction.ClassificationSource.UNCLASSIFIED)
        self.assertEqual(item.cancel_status, Transaction.CancelStatus.NORMAL)

    def test_external_id_is_unique_per_business_and_source(self):
        self.create_transaction()

        with self.assertRaises(IntegrityError), db_transaction.atomic():
            self.create_transaction()

        same_external_id_from_another_source = self.create_transaction(
            source_type=Transaction.SourceType.TAX_INVOICE,
        )
        self.assertIsNotNone(same_external_id_from_another_source.id)

    def test_transaction_cannot_be_its_own_duplicate(self):
        item = self.create_transaction("card-001")
        duplicate = TransactionDuplicate(
            business=self.business,
            primary_transaction=item,
            suspected_transaction=item,
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()

    def test_duplicate_pair_must_belong_to_same_business(self):
        other_business = Business.objects.create(business_name="다른 카페")
        first = self.create_transaction("card-001")
        second = self.create_transaction(
            "invoice-001",
            business=other_business,
            source_type=Transaction.SourceType.TAX_INVOICE,
        )

        duplicate = TransactionDuplicate(
            business=self.business,
            primary_transaction=first,
            suspected_transaction=second,
        )

        with self.assertRaises(ValidationError):
            duplicate.full_clean()
