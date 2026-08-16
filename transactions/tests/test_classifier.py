from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from transactions.models import Transaction
from transactions.services.classifier import RuleBasedTransactionClassifier
from transactions.services.types import NormalizedTransaction


class RuleBasedTransactionClassifierTests(SimpleTestCase):
    def item(self, *hints, transaction_type=Transaction.TransactionType.PURCHASE):
        return NormalizedTransaction(
            source_type=Transaction.SourceType.CARD_PURCHASE,
            external_id="test",
            transaction_type=transaction_type,
            transaction_date=date(2026, 8, 1),
            total_amount=Decimal("1000"),
            classification_hints=hints,
        )

    def test_clear_food_business_item_is_raw_material(self):
        result = RuleBasedTransactionClassifier().classify(
            self.item("도매 및 소매업", "식료품 및 유제품")
        )

        self.assertEqual(result.category, Transaction.Category.RAW_MATERIAL)
        self.assertEqual(result.source, Transaction.ClassificationSource.RULE)
        self.assertEqual(result.confidence, Decimal("0.9500"))

    def test_marketplace_without_item_context_stays_unclassified(self):
        result = RuleBasedTransactionClassifier().classify(self.item("쿠팡", "도매 및 소매업"))

        self.assertEqual(result.category, Transaction.Category.UNCLASSIFIED)
        self.assertIsNone(result.confidence)

    def test_tied_mixed_invoice_stays_unclassified(self):
        result = RuleBasedTransactionClassifier().classify(
            self.item("원두", "종이컵")
        )

        self.assertEqual(result.category, Transaction.Category.UNCLASSIFIED)

    def test_sales_are_not_expense_classified(self):
        result = RuleBasedTransactionClassifier().classify(
            self.item("원두", transaction_type=Transaction.TransactionType.SALE)
        )

        self.assertEqual(result.category, Transaction.Category.UNCLASSIFIED)
