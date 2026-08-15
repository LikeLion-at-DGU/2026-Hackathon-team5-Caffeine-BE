from django.test import TestCase
from rest_framework.test import APIClient

from businesses.models import Business
from payroll.models import Employee, Payment


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

    def test_summary_expense_breakdown_has_payroll_only(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})

        breakdown = response.data["data"]["expense_breakdown"]
        self.assertEqual(len(breakdown), 1)
        self.assertEqual(breakdown[0]["category"], "인건비")
        # 사업주 부담 4대보험료가 포함된 total_labor_cost 참조이므로 gross_pay보다 커야 함
        self.assertGreater(breakdown[0]["amount"], 1_455_120)

    def test_summary_pending_fields_are_null(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})

        data = response.data["data"]
        self.assertIsNone(data["total_sales"])
        self.assertIsNone(data["vat_reserve_amount"])
        self.assertIsNone(data["net_profit"])

    def test_summary_missing_period_returns_400(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "INVALID_PERIOD")

    def test_summary_no_payroll_data_returns_zero_labor_cost(self):
        response = self.client.get(self.url, {"year": 2020, "month": 1})

        self.assertEqual(response.status_code, 200)
        breakdown = response.data["data"]["expense_breakdown"]
        self.assertEqual(breakdown[0]["amount"], 0)