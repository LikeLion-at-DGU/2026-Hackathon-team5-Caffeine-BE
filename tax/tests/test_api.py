from datetime import date
from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from businesses.models import Business
from transactions.models import Transaction

from tax.models import DeductionReview, MonthlyClose


class TaxApiTests(APITestCase):
    def setUp(self):
        self.business = Business.objects.create(
            business_name="카페비서 데모카페",
            tax_type="GENERAL",
        )
        self.purchase = self.create_transaction(
            "purchase-001",
            Transaction.TransactionType.PURCHASE,
            source_deduction_status=Transaction.SourceDeductionStatus.DEDUCTIBLE,
        )
        self.sale = self.create_transaction("sale-001", Transaction.TransactionType.SALE)

    def create_transaction(self, external_id, transaction_type, **overrides):
        values = {
            "business": self.business,
            "source_type": Transaction.SourceType.CARD_PURCHASE,
            "external_id": external_id,
            "transaction_type": transaction_type,
            "transaction_date": date(2026, 8, 3),
            "merchant_name": "테스트 거래처",
            "total_amount": Decimal("110000.00"),
            "supply_amount": Decimal("100000.00"),
            "vat_amount": Decimal("10000.00"),
        }
        values.update(overrides)
        return Transaction.objects.create(**values)

    def test_deduction_list_creates_rule_review(self):
        response = self.client.get(
            reverse("tax-deduction-list"),
            {"business_id": self.business.id, "year_month": "2026-08"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["code"], "DEDUCTION_LIST_SUCCESS")
        self.assertEqual(response.data["data"]["pagination"]["total_count"], 1)
        item = response.data["data"]["items"][0]
        self.assertEqual(item["transaction"]["transaction_id"], self.purchase.id)
        self.assertEqual(item["suggestion"]["source"], DeductionReview.SuggestionSource.CODEF)

    def test_confirm_deduction(self):
        response = self.client.patch(
            reverse("tax-deduction-confirm", kwargs={"transaction_id": self.purchase.id}),
            {"confirmed_status": DeductionReview.ConfirmedStatus.DEDUCTIBLE},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["code"], "DEDUCTION_CONFIRMED")
        self.assertEqual(
            response.data["data"]["confirmation"]["status"],
            DeductionReview.ConfirmedStatus.DEDUCTIBLE,
        )

    def test_vat_forecast_uses_confirmed_purchase(self):
        DeductionReview.objects.create(
            transaction=self.purchase,
            confirmed_status=DeductionReview.ConfirmedStatus.DEDUCTIBLE,
        )

        response = self.client.get(
            reverse("tax-vat-forecast"),
            {"business_id": self.business.id, "year_month": "2026-08"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["estimated_vat"], Decimal("0.00"))
        self.assertEqual(response.data["data"]["unconfirmed_transaction_count"], 0)

    def test_forecast_rejects_unknown_tax_type(self):
        self.business.tax_type = "UNKNOWN"
        self.business.save()

        response = self.client.get(
            reverse("tax-vat-forecast"),
            {"business_id": self.business.id, "year_month": "2026-08"},
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["code"], "UNSUPPORTED_TAX_TYPE")

    def test_close_rejects_unconfirmed_purchases(self):
        response = self.client.post(
            reverse("tax-monthly-close-approve", kwargs={"year_month": "2026-08"}),
            {"business_id": self.business.id},
            format="json",
        )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data["code"], "UNCONFIRMED_TRANSACTIONS_EXIST")
        self.assertFalse(MonthlyClose.objects.exists())

    def test_approve_close_blocks_later_transaction_edit(self):
        DeductionReview.objects.create(
            transaction=self.purchase,
            confirmed_status=DeductionReview.ConfirmedStatus.DEDUCTIBLE,
        )
        response = self.client.post(
            reverse("tax-monthly-close-approve", kwargs={"year_month": "2026-08"}),
            {"business_id": self.business.id},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        edit_response = self.client.patch(
            reverse("transaction-category", kwargs={"transaction_id": self.purchase.id}),
            {"category": Transaction.Category.RAW_MATERIAL},
            format="json",
        )

        self.assertEqual(edit_response.status_code, 409)
        self.assertEqual(edit_response.data["code"], "MONTH_ALREADY_CLOSED")

    def test_ai_endpoint_is_explicitly_disabled(self):
        response = self.client.post(
            reverse("tax-deduction-ai-suggest", kwargs={"transaction_id": self.purchase.id}),
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.data["code"], "AI_SUGGESTION_NOT_CONFIGURED")

    def test_transaction_sync_rejects_period_overlapping_closed_month(self):
        MonthlyClose.objects.create(
            business=self.business,
            year=2026,
            month=8,
            status=MonthlyClose.Status.CLOSED,
        )

        response = self.client.post(
            reverse("transaction-sync"),
            {
                "business_id": self.business.id,
                "start_date": "2026-07-15",
                "end_date": "2026-08-05",
                "sources": [Transaction.SourceType.CARD_PURCHASE],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "MONTH_ALREADY_CLOSED")
