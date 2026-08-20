from datetime import date
from decimal import Decimal

from django.test import TestCase

from businesses.models import Business
from transactions.models import MonthlySalesSummary, Transaction, TransactionDuplicate

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

    def test_forecast_subtracts_provisional_deemed_purchase_deduction(self):
        self.business.business_type = "음식점업"
        self.business.business_item = "커피전문점 및 음료"
        self.business.save(update_fields=["business_type", "business_item"])
        self.create_transaction("sale-001", Transaction.TransactionType.SALE)
        purchase = self.create_transaction(
            "milk-001",
            Transaction.TransactionType.PURCHASE,
            merchant_name="매일유업",
            total_amount=Decimal("109000.00"),
            supply_amount=Decimal("109000.00"),
            vat_amount=Decimal("0.00"),
            category=Transaction.Category.RAW_MATERIAL,
            expense_purpose=Transaction.ExpensePurpose.BUSINESS,
        )
        review = DeductionReviewService.get_or_create(purchase)
        DeductionReviewService.confirm(
            review=review,
            confirmed_status=DeductionReview.ConfirmedStatus.DEDUCTIBLE,
        )

        result = VatForecastService.calculate(business=self.business, year=2026, month=8)

        self.assertEqual(result["deemed_purchase_candidate_amount"], Decimal("109000.00"))
        self.assertEqual(result["deemed_purchase_deduction"], Decimal("9000"))
        self.assertEqual(result["deemed_purchase_rate"], "9/109")
        self.assertEqual(result["estimated_vat"], Decimal("1000.00"))
        self.assertEqual(result["deemed_purchase_calculation_status"], "PROVISIONAL_UNCAPPED")

    def test_forecast_does_not_guess_rate_for_non_food_service_business(self):
        purchase = self.create_transaction(
            "material-001",
            Transaction.TransactionType.PURCHASE,
            total_amount=Decimal("109000.00"),
            supply_amount=Decimal("109000.00"),
            vat_amount=Decimal("0.00"),
            category=Transaction.Category.RAW_MATERIAL,
            expense_purpose=Transaction.ExpensePurpose.BUSINESS,
        )
        review = DeductionReviewService.get_or_create(purchase)
        DeductionReviewService.confirm(
            review=review,
            confirmed_status=DeductionReview.ConfirmedStatus.DEDUCTIBLE,
        )

        result = VatForecastService.calculate(business=self.business, year=2026, month=8)

        self.assertEqual(result["deemed_purchase_deduction"], Decimal("0"))
        self.assertEqual(result["deemed_purchase_calculation_status"], "REVIEW_REQUIRED")

    def test_forecast_includes_estimated_vat_from_monthly_card_sales(self):
        self.create_transaction("cash-sale-001", Transaction.TransactionType.SALE)
        MonthlySalesSummary.objects.create(
            business=self.business,
            source_type=MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
            year=2026,
            month=8,
            transaction_count=120,
            total_amount=Decimal("11000000.00"),
        )

        result = VatForecastService.calculate(business=self.business, year=2026, month=8)

        self.assertEqual(result["transaction_output_vat"], Decimal("10000.00"))
        self.assertEqual(result["card_sales_summary"]["estimated_output_vat"], Decimal("1000000"))
        self.assertEqual(result["card_sales_summary"]["estimated_supply_amount"], Decimal("10000000.00"))
        self.assertTrue(result["card_sales_summary"]["included_in_vat_forecast"])
        self.assertEqual(result["output_vat"], Decimal("1010000.00"))
        self.assertEqual(result["sales_amount"], Decimal("11110000.00"))
        self.assertEqual(result["estimated_vat"], Decimal("1010000.00"))
