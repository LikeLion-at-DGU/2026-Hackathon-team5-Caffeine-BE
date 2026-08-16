from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction as db_transaction
from django.test import TestCase

from businesses.models import Business
from transactions.models import Transaction

from tax.models import DeductionReview, MonthlyClose


class TaxModelTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            business_name="카페비서 데모카페",
            tax_type="GENERAL",
        )
        self.transaction = Transaction.objects.create(
            business=self.business,
            source_type=Transaction.SourceType.CARD_PURCHASE,
            external_id="purchase-001",
            transaction_type=Transaction.TransactionType.PURCHASE,
            transaction_date=date(2026, 8, 3),
            total_amount=Decimal("110000.00"),
            supply_amount=Decimal("100000.00"),
            vat_amount=Decimal("10000.00"),
        )

    def test_review_is_one_to_one_with_transaction(self):
        DeductionReview.objects.create(transaction=self.transaction)

        with self.assertRaises(IntegrityError), db_transaction.atomic():
            DeductionReview.objects.create(transaction=self.transaction)

    def test_monthly_close_is_unique_per_business_and_month(self):
        MonthlyClose.objects.create(business=self.business, year=2026, month=8)

        with self.assertRaises(IntegrityError), db_transaction.atomic():
            MonthlyClose.objects.create(business=self.business, year=2026, month=8)

    def test_year_month_is_formatted(self):
        close = MonthlyClose.objects.create(business=self.business, year=2026, month=8)

        self.assertEqual(close.year_month, "2026-08")
