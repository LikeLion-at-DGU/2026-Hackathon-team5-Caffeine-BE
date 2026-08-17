from datetime import date
from decimal import Decimal

from django.test import TestCase

from businesses.models import Business
from transactions.models import Transaction, TransactionDuplicate

from tax.models import DeductionReview
from tax.services.deduction_service import DeductionReviewService
from tax.services.vat_service import VatForecastService


class TaxServiceTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            business_name="카페비서 데모카페",
            tax_type="GENERAL",
        )

    def create_transaction(self, external_id, transaction_type, **overrides):
        values = {
            "business": self.business,
            "source_type": Transaction.SourceType.CARD_PURCHASE,
            "external_id": external_id,
            "transaction_type": transaction_type,
            "transaction_date": date(2026, 8, 3),
            "total_amount": Decimal("110000.00"),
            "supply_amount": Decimal("100000.00"),
            "vat_amount": Decimal("10000.00"),
        }
        values.update(overrides)
        return Transaction.objects.create(**values)

    def test_personal_expense_is_suggested_as_non_deductible(self):
        purchase = self.create_transaction(
            "personal-001",
            Transaction.TransactionType.PURCHASE,
            expense_purpose=Transaction.ExpensePurpose.PERSONAL,
        )

        review = DeductionReviewService.get_or_create(purchase)

        self.assertEqual(
            review.suggested_status,
            DeductionReview.SuggestedStatus.NON_DEDUCTIBLE_CANDIDATE,
        )
        self.assertEqual(review.suggestion_source, DeductionReview.SuggestionSource.RULE)

    def test_codef_deduction_status_has_priority_for_candidate(self):
        purchase = self.create_transaction(
            "codef-001",
            Transaction.TransactionType.PURCHASE,
            source_deduction_status=Transaction.SourceDeductionStatus.DEDUCTIBLE,
        )

        review = DeductionReviewService.get_or_create(purchase)

        self.assertEqual(
            review.suggested_status,
            DeductionReview.SuggestedStatus.DEDUCTIBLE_CANDIDATE,
        )
        self.assertEqual(review.suggestion_source, DeductionReview.SuggestionSource.CODEF)

    def test_forecast_uses_only_confirmed_deductible_vat(self):
        self.create_transaction("sale-001", Transaction.TransactionType.SALE)
        confirmed = self.create_transaction("purchase-001", Transaction.TransactionType.PURCHASE)
        self.create_transaction("purchase-002", Transaction.TransactionType.PURCHASE)
        review = DeductionReviewService.get_or_create(confirmed)
        DeductionReviewService.confirm(
            review=review,
            confirmed_status=DeductionReview.ConfirmedStatus.DEDUCTIBLE,
        )

        result = VatForecastService.calculate(business=self.business, year=2026, month=8)

        self.assertEqual(result["output_vat"], Decimal("10000.00"))
        self.assertEqual(result["deductible_input_vat"], Decimal("10000.00"))
        self.assertEqual(result["estimated_vat"], Decimal("0.00"))
        self.assertEqual(result["review_required_input_vat"], Decimal("10000.00"))
        self.assertEqual(result["unconfirmed_transaction_count"], 1)

    def test_forecast_excludes_confirmed_duplicate_suspected_side(self):
        primary = self.create_transaction("purchase-001", Transaction.TransactionType.PURCHASE)
        suspected = self.create_transaction(
            "invoice-001",
            Transaction.TransactionType.PURCHASE,
            source_type=Transaction.SourceType.TAX_INVOICE,
        )
        TransactionDuplicate.objects.create(
            business=self.business,
            primary_transaction=primary,
            suspected_transaction=suspected,
            status=TransactionDuplicate.Status.CONFIRMED,
        )

        result = VatForecastService.calculate(business=self.business, year=2026, month=8)

        self.assertEqual(result["purchase_amount"], Decimal("110000.00"))
        self.assertEqual(result["unconfirmed_transaction_count"], 1)
