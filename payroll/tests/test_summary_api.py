from django.test import TestCase
from rest_framework.test import APIClient

from businesses.models import Business
from payroll.models import Employee, Payment


class PayrollSummaryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(business_name="카페비서")
        self.url = f"/api/businesses/{self.business.id}/payroll/summary/"

        self.full_timer = Employee.objects.create(
            business=self.business, name="장예은", employment_type="FULL_TIME", hourly_wage=10320
        )
        self.part_timer = Employee.objects.create(
            business=self.business, name="황사라", employment_type="PART_TIME", hourly_wage=10320
        )
        self.freelancer = Employee.objects.create(
            business=self.business, name="김프리", employment_type="FREELANCER", hourly_wage=15000
        )

        Payment.objects.create(
            employee=self.full_timer, year=2026, month=8,
            work_hours=141, gross_pay=1_455_120, withholding_tax=8_734,
        )
        Payment.objects.create(
            employee=self.part_timer, year=2026, month=8,
            work_hours=43.2, gross_pay=445_824, withholding_tax=0,
        )
        Payment.objects.create(
            employee=self.freelancer, year=2026, month=8,
            work_hours=80, gross_pay=1_200_000, withholding_tax=39_600,
        )

    def test_summary_returns_correct_employee_count(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["employee_count"], 3)

    def test_summary_total_withholding_tax_is_sum_of_all(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})
        self.assertEqual(response.data["data"]["withholding_tax"], 48_334)

    def test_summary_labor_cost_includes_employer_insurance(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})
        data = response.data["data"]

        gross_pay_sum = 1_455_120 + 445_824 + 1_200_000
        self.assertGreater(data["total_labor_cost"], gross_pay_sum)

        full_time_insurance = round(1_455_120 * 0.0475) + round(1_455_120 * 0.03595) \
            + round(round(1_455_120 * 0.03595) * 0.1314) + round(1_455_120 * 0.0115) \
            + round(1_455_120 * 0.0086)
        part_time_insurance = round(445_824 * 0.0086)
        freelancer_insurance = 0
        expected_total = gross_pay_sum + full_time_insurance + part_time_insurance + freelancer_insurance

        self.assertEqual(data["total_labor_cost"], expected_total)

    def test_summary_includes_payment_due_date(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})
        self.assertEqual(response.data["data"]["payment_due_date"], "2026-09-10")

    def test_summary_december_rolls_over_to_next_year(self):
        response = self.client.get(self.url, {"year": 2026, "month": 12})
        self.assertEqual(response.data["data"]["payment_due_date"], "2027-01-10")

    def test_summary_missing_period_returns_400(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "INVALID_PERIOD")

    def test_summary_no_data_for_period_returns_zero(self):
        response = self.client.get(self.url, {"year": 2020, "month": 1})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["employee_count"], 0)
        self.assertEqual(response.data["data"]["total_labor_cost"], 0)