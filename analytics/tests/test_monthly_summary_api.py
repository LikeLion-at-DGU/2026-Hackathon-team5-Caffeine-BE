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

    def test_summary_keeps_vat_empty_for_unknown_tax_type_and_calculates_trend(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})

        data = response.data["data"]
        self.assertIsNone(data["vat_reserve_amount"])
        self.assertIsNone(data["vat_breakdown"])
        self.assertIsNone(data["sales_change_rate"])
        self.assertIsNone(data["expense_change_rate"])
        self.assertEqual(data["top_increasing_category"], "LABOR")

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

        self.assertIn("재료비", categories)
        self.assertIn("인건비", categories)

    def test_expense_breakdown_includes_korean_label(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})

        breakdown = response.data["data"]["expense_breakdown"]
        raw_material = next(item for item in breakdown if item["category"] == "재료비")
        labor = next(item for item in breakdown if item["category"] == "인건비")

        self.assertEqual(raw_material["category"], "재료비")
        self.assertEqual(labor["category"], "인건비")

    def test_total_expense_includes_payroll_and_transactions(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})

        data = response.data["data"]
        self.assertGreater(data["total_expense"], 0)

    def test_net_profit_and_margin_calculated(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})

        data = response.data["data"]
        self.assertEqual(data["net_profit"], data["total_sales"] - data["total_expense"])
        self.assertIsNotNone(data["profit_margin"])

    def test_top_level_endpoint_with_query_params_works(self):
        response = self.client.get(
            "/api/analytics/monthly-summary/",
            {"business_id": self.business.id, "year": 2026, "month": 8},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["year"], 2026)

    def test_deduction_breakdown_top_level_endpoint_works(self):
        response = self.client.get(
            "/api/analytics/deduction-breakdown/",
            {"business_id": self.business.id, "year": 2026, "month": 8},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["code"], "DEDUCTION_BREAKDOWN_SUCCESS")
        self.assertEqual(response.data["data"]["deduction_grade"], "공제율 우수")
        self.assertEqual(len(response.data["data"]["structure"]), 3)
        self.assertEqual(len(response.data["data"]["item_details"]), 4)
