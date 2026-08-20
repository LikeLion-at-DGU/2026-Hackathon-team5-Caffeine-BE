from datetime import date, time
from decimal import Decimal

from django.test import SimpleTestCase

from integrations.codef.mock import load_fixture
from transactions.models import MonthlySalesSummary, Transaction
from transactions.services.normalizers import (
    normalize_business_card_purchases,
    normalize_cash_receipt_sales,
    normalize_credit_card_sales_summaries,
    normalize_tax_invoices,
)
from transactions.services.normalizers.helpers import (
    TransactionNormalizationError,
    ensure_success,
)


class CodefTransactionNormalizerTests(SimpleTestCase):
    def test_missing_result_code_is_rejected(self):
        with self.assertRaises(TransactionNormalizationError) as context:
            ensure_success({"result": {"message": "코드 누락"}})

        self.assertIn("MISSING_RESULT_CODE", str(context.exception))

    def test_business_card_purchase_fixture_is_normalized_per_usage(self):
        items = normalize_business_card_purchases(
            load_fixture("business_card_purchase_success.json")
        )

        self.assertEqual(len(items), 21)
        first = items[0]
        self.assertEqual(first.source_type, Transaction.SourceType.CARD_PURCHASE)
        self.assertEqual(first.transaction_type, Transaction.TransactionType.PURCHASE)
        self.assertEqual(first.transaction_date, date(2026, 3, 12))
        self.assertEqual(first.merchant_business_number, "1018612345")
        self.assertTrue(
            first.external_id.startswith("CARD_PURCHASE:91120001")
            or first.external_id.startswith("CARD_PURCHASE:HASH:")
        )
        self.assertEqual(
            sum(
                item.source_deduction_status
                == Transaction.SourceDeductionStatus.DEDUCTIBLE
                for item in items
            ),
            17,
        )

    def test_card_hash_external_id_is_stable(self):
        payload = load_fixture("business_card_purchase_success.json")
        first_run = normalize_business_card_purchases(payload)
        payload["data"]["resDetailList"][0]["resNote"] = "나중에 변경된 참고 메모"
        second_run = normalize_business_card_purchases(payload)

        self.assertEqual(
            [item.external_id for item in first_run],
            [item.external_id for item in second_run],
        )

    def test_cash_receipt_sales_are_individual_sales(self):
        items = normalize_cash_receipt_sales(load_fixture("cash_receipt_sales_success.json"))

        self.assertEqual(len(items), 14)
        self.assertTrue(all(item.transaction_type == Transaction.TransactionType.SALE for item in items))
        self.assertEqual(items[0].transaction_time, time(12, 15, 30))
        self.assertEqual(items[0].approval_no, "081120001")
        self.assertEqual(items[0].merchant_name, "")

    def test_tax_invoice_purchase_and_sale_shapes_are_both_supported(self):
        purchases = normalize_tax_invoices(
            load_fixture("tax_invoice_purchase_success.json"),
            Transaction.TransactionType.PURCHASE,
        )
        sales = normalize_tax_invoices(
            load_fixture("tax_invoice_sales_success.json"),
            Transaction.TransactionType.SALE,
        )

        self.assertEqual(len(purchases), 10)
        self.assertEqual(len(sales), 3)
        self.assertEqual(purchases[0].merchant_name, "일리카페 로스팅컴퍼니")
        self.assertEqual(sales[0].merchant_name, "넥스트소프트웨어")

    def test_credit_card_sales_are_normalized_as_monthly_summaries(self):
        items = normalize_credit_card_sales_summaries(
            load_fixture("credit_card_sales_success.json")
        )

        self.assertEqual(len(items), 6)
        self.assertEqual(
            items[0].source_type,
            MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
        )
        self.assertEqual((items[0].year, items[0].month), (2026, 3))
        self.assertEqual(items[0].transaction_count, 563)
        self.assertEqual(items[0].total_amount, Decimal("9428500"))
        self.assertEqual((items[5].year, items[5].month), (2026, 8))
        self.assertEqual(items[5].transaction_count, 867)
        self.assertEqual(items[5].total_amount, Decimal("14562300"))
