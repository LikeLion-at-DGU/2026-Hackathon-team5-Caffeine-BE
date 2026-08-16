from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from businesses.models import Business
from payroll.models import Employee, Payment
from transactions.models import MonthlySalesSummary, Transaction


class MonthlySummaryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(business_name="카페비서")
        self.url = f"/api/businesses/{self.business.id}/analytics/monthly-summary/"

        employee = Employee.objects.create(
            business=self.business, name="장예은", employment_type="FULL_TIME", hourly_wage=10320
        )
        Payment.objects.create(
            employee=employee, year=2026, month=8,
            work_hours=141, gross_pay=1_455_120, withholding_tax=8_734,
        )

    def test_summary_includes_payroll_data(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})

        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertEqual(data["payroll_employee_count"], 1)
        self.assertEqual(data["payroll_withholding_tax"], 8_734)

    def test_summary_pending_vat_fields_are_null(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})

        data = response.data["data"]
        self.assertIsNone(data["vat_reserve_amount"])
        self.assertIsNone(data["vat_breakdown"])
        self.assertIsNone(data["sales_change_rate"])
        self.assertIsNone(data["expense_change_rate"])
        self.assertIsNone(data["top_increasing_category"])

    def test_summary_missing_period_returns_400(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "INVALID_PERIOD")

    def test_summary_no_data_for_period_returns_zero(self):
        response = self.client.get(self.url, {"year": 2020, "month": 1})

        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertEqual(data["total_sales"], 0)
        self.assertEqual(data["total_expense"], 0)


class MonthlySummaryWithTransactionsAPITests(TestCase):
    """transactions 데이터까지 포함한 실제 매출/지출 계산 검증."""

    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(business_name="카페비서")
        self.url = f"/api/businesses/{self.business.id}/analytics/monthly-summary/"

        employee = Employee.objects.create(
            business=self.business, name="장예은", employment_type="FULL_TIME", hourly_wage=10320
        )
        Payment.objects.create(
            employee=employee, year=2026, month=8,
            work_hours=141, gross_pay=1_455_120, withholding_tax=8_734,
        )

        # 현금영수증 매출 (개별 Transaction)
        Transaction.objects.create(
            business=self.business, source_type="CASH_RECEIPT_SALE", external_id="cr-1",
            transaction_type="SALE", transaction_date="2026-08-05",
            total_amount=Decimal("500000"),
        )
        # 신용카드 매출 (월별 집계, Transaction이 아니라 MonthlySalesSummary)
        MonthlySalesSummary.objects.create(
            business=self.business, source_type="CREDIT_CARD_SALES_SUMMARY",
            year=2026, month=8, transaction_count=100, total_amount=Decimal("9000000"),
        )
        # 사업 지출로 분류된 매입 (재료비)
        Transaction.objects.create(
            business=self.business, source_type="CARD_PURCHASE", external_id="cp-1",
            transaction_type="PURCHASE", transaction_date="2026-08-06",
            total_amount=Decimal("300000"), category="RAW_MATERIAL",
            expense_purpose="BUSINESS",
        )
        # 개인 지출 — 집계에서 제외되어야 함
        Transaction.objects.create(
            business=self.business, source_type="CARD_PURCHASE", external_id="cp-2",
            transaction_type="PURCHASE", transaction_date="2026-08-07",
            total_amount=Decimal("999999"), category="OTHER",
            expense_purpose="PERSONAL",
        )
        # 취소된 거래 — 집계에서 제외되어야 함
        Transaction.objects.create(
            business=self.business, source_type="CARD_PURCHASE", external_id="cp-3",
            transaction_type="PURCHASE", transaction_date="2026-08-08",
            total_amount=Decimal("999999"), category="RAW_MATERIAL",
            expense_purpose="BUSINESS", cancel_status="CANCELLED",
        )

    def test_total_sales_combines_individual_and_summary_sources(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})

        # 현금영수증 500,000원 + 신용카드 집계 9,000,000원
        self.assertEqual(response.data["data"]["total_sales"], 9500000)

    def test_expense_breakdown_excludes_personal_and_cancelled(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})

        breakdown = response.data["data"]["expense_breakdown"]
        categories = {item["category"]: item["amount"] for item in breakdown}

        self.assertEqual(categories["RAW_MATERIAL"], 300_000)
        self.assertIn("LABOR", categories)
        # 개인지출(999,999원)이나 취소건이 원재료비에 섞이면 안 됨
        self.assertEqual(categories["RAW_MATERIAL"], 300_000)

    def test_expense_breakdown_includes_korean_label(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})

        breakdown = response.data["data"]["expense_breakdown"]
        raw_material = next(item for item in breakdown if item["category"] == "RAW_MATERIAL")
        labor = next(item for item in breakdown if item["category"] == "LABOR")

        self.assertEqual(raw_material["label"], "원재료")
        self.assertEqual(labor["label"], "인건비")

    def test_total_expense_includes_payroll_and_transactions(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})

        data = response.data["data"]
        # 재료비 300,000 + 인건비(총 1,616,690원 근처, 사업주부담4대보험 포함)
        self.assertGreater(data["total_expense"], 300000 + 1455120)

    def test_net_profit_and_margin_calculated(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})

        data = response.data["data"]
        self.assertEqual(data["net_profit"], data["total_sales"] - data["total_expense"])
        self.assertIsNotNone(data["profit_margin"])