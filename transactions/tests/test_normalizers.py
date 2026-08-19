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

        self.assertEqual(len(items), 12)
        self.assertEqual(sum(item.total_amount for item in items), Decimal("803000"))
        first = items[0]
        self.assertEqual(first.source_type, Transaction.SourceType.CARD_PURCHASE)
        self.assertEqual(first.transaction_type, Transaction.TransactionType.PURCHASE)
        self.assertEqual(first.transaction_date, date(2026, 8, 3))
        self.assertEqual(first.merchant_business_number, "3012245678")
        self.assertTrue(first.external_id.startswith("CARD_PURCHASE:HASH:"))
        self.assertEqual(
            sum(
                item.source_deduction_status
                == Transaction.SourceDeductionStatus.DEDUCTIBLE
                for item in items
            ),
            11,
        )
        self.assertEqual(
            items[-1].source_deduction_status,
            Transaction.SourceDeductionStatus.NON_DEDUCTIBLE,
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

        self.assertEqual(len(items), 10)
        self.assertTrue(all(item.transaction_type == Transaction.TransactionType.SALE for item in items))
        self.assertEqual(items[0].transaction_time, time(9, 15, 23))
        self.assertEqual(items[0].approval_no, "095040641")
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

        self.assertEqual(len(purchases), 6)
        self.assertEqual(len(sales), 1)
        self.assertEqual(purchases[0].merchant_name, "브라운빈커피컴퍼니")
        self.assertIn("에티오피아 예가체프 원두", purchases[0].classification_hints)
        self.assertEqual(sales[0].merchant_name, "스튜디오 온")
        self.assertEqual(sales[0].classification_hints, ())

    def test_credit_card_sales_are_normalized_as_monthly_summaries(self):
        items = normalize_credit_card_sales_summaries(
            load_fixture("credit_card_sales_success.json")
        )

        self.assertEqual(len(items), 2)
        self.assertEqual(
            items[0].source_type,
            MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
        )
        self.assertEqual((items[0].year, items[0].month), (2026, 7))
        self.assertEqual(items[0].transaction_count, 612)
        self.assertEqual(items[0].total_amount, Decimal("8340000"))
        self.assertEqual((items[1].year, items[1].month), (2026, 8))
        self.assertEqual(items[1].transaction_count, 651)
        self.assertEqual(items[1].total_amount, Decimal("9120000"))
