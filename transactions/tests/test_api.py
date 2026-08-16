from datetime import date
from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from businesses.models import Business
from transactions.models import Transaction, TransactionDuplicate


class TransactionApiTests(APITestCase):
    def setUp(self):
        self.business = Business.objects.create(business_name="카페비서 데모카페")
        self.card = self.create_transaction(
            external_id="card-001",
            source_type=Transaction.SourceType.CARD_PURCHASE,
        )
        self.invoice = self.create_transaction(
            external_id="invoice-001",
            source_type=Transaction.SourceType.TAX_INVOICE,
        )
        self.duplicate = TransactionDuplicate.objects.create(
            business=self.business,
            primary_transaction=self.card,
            suspected_transaction=self.invoice,
            confidence=Decimal("0.9500"),
            detection_reason={"matched_by": ["transaction_date", "total_amount"]},
        )

    def create_transaction(self, *, external_id, source_type):
        return Transaction.objects.create(
            business=self.business,
            source_type=source_type,
            external_id=external_id,
            transaction_type=Transaction.TransactionType.PURCHASE,
            transaction_date=date(2026, 8, 3),
            merchant_name="서울우유 성동대리점",
            merchant_business_number="1234567890",
            supply_amount=Decimal("170000.00"),
            vat_amount=Decimal("17000.00"),
            total_amount=Decimal("187000.00"),
        )

    def test_list_requires_business_id(self):
        response = self.client.get(reverse("transaction-list"))

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["code"], "INVALID_TRANSACTION_QUERY")

    def test_list_returns_paginated_transactions(self):
        response = self.client.get(
            reverse("transaction-list"),
            {"business_id": self.business.id, "page": 1, "page_size": 1},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(len(response.data["data"]["items"]), 1)
        self.assertEqual(response.data["data"]["pagination"]["total_count"], 2)
        self.assertEqual(response.data["data"]["pagination"]["total_pages"], 2)

    def test_detail_returns_transaction(self):
        response = self.client.get(
            reverse("transaction-detail", kwargs={"transaction_id": self.card.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["transaction_id"], self.card.id)
        self.assertEqual(response.data["data"]["business_id"], self.business.id)
        self.assertEqual(response.data["data"]["source"], "CARD")
        self.assertEqual(
            response.data["data"]["expense_purpose"],
            {
                "code": Transaction.ExpensePurpose.UNCLASSIFIED,
                "label": "미분류",
                "source": Transaction.ClassificationSource.UNCLASSIFIED,
            },
        )
        self.assertNotIn("raw_data", response.data["data"])

    def test_category_patch_marks_source_as_user(self):
        self.card.classification_confidence = Decimal("0.8000")
        self.card.classification_source = Transaction.ClassificationSource.AI
        self.card.save()

        response = self.client.patch(
            reverse("transaction-category", kwargs={"transaction_id": self.card.id}),
            {"category": Transaction.Category.RAW_MATERIAL},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.card.refresh_from_db()
        self.assertEqual(self.card.category, Transaction.Category.RAW_MATERIAL)
        self.assertEqual(self.card.classification_source, Transaction.ClassificationSource.USER)
        self.assertIsNone(self.card.classification_confidence)

    def test_purpose_patch_marks_source_as_user(self):
        response = self.client.patch(
            reverse("transaction-purpose", kwargs={"transaction_id": self.card.id}),
            {"expense_purpose": Transaction.ExpensePurpose.BUSINESS},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["code"], "TRANSACTION_PURPOSE_UPDATED")
        self.card.refresh_from_db()
        self.assertEqual(self.card.expense_purpose, Transaction.ExpensePurpose.BUSINESS)
        self.assertEqual(
            self.card.expense_purpose_source,
            Transaction.ClassificationSource.USER,
        )

    def test_list_filters_by_expense_purpose(self):
        self.card.expense_purpose = Transaction.ExpensePurpose.BUSINESS
        self.card.expense_purpose_source = Transaction.ClassificationSource.USER
        self.card.save()

        response = self.client.get(
            reverse("transaction-list"),
            {
                "business_id": self.business.id,
                "expense_purpose": Transaction.ExpensePurpose.BUSINESS,
            },
        )

        self.assertEqual(response.status_code, 200)
        items = response.data["data"]["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["transaction_id"], self.card.id)

    def test_duplicate_list_defaults_to_pending(self):
        response = self.client.get(
            reverse("transaction-duplicate-list"),
            {"business_id": self.business.id},
        )

        self.assertEqual(response.status_code, 200)
        item = response.data["data"]["items"][0]
        self.assertEqual(item["id"], self.duplicate.id)
        self.assertEqual(item["primary_transaction"]["transaction_id"], self.card.id)
        self.assertEqual(item["suspected_transaction"]["transaction_id"], self.invoice.id)

    def test_duplicate_patch_resolves_status(self):
        response = self.client.patch(
            reverse(
                "transaction-duplicate-resolution",
                kwargs={"duplicate_id": self.duplicate.id},
            ),
            {"status": TransactionDuplicate.Status.CONFIRMED},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.duplicate.refresh_from_db()
        self.assertEqual(self.duplicate.status, TransactionDuplicate.Status.CONFIRMED)
        self.assertIsNotNone(self.duplicate.resolved_at)

    def test_duplicate_patch_rejects_pending_status(self):
        response = self.client.patch(
            reverse(
                "transaction-duplicate-resolution",
                kwargs={"duplicate_id": self.duplicate.id},
            ),
            {"status": TransactionDuplicate.Status.PENDING},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "INVALID_DUPLICATE_STATUS")
