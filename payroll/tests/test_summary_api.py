from django.test import TestCase
from rest_framework.test import APIClient

from payroll.models import Employee, Payment


class PayrollSummaryAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/payroll/summary/"

        self.full_timer = Employee.objects.create(
            name="장예은", employment_type="FULL_TIME", hourly_wage=10320
        )
        self.part_timer = Employee.objects.create(
            name="황사라", employment_type="PART_TIME", hourly_wage=10320
        )
        self.freelancer = Employee.objects.create(
            name="김프리", employment_type="FREELANCER", hourly_wage=15000
        )

        # 정직원: 141시간 -> 1,455,120원, 원천세 7,940원
        Payment.objects.create(
            employee=self.full_timer, year=2026, month=8,
            work_hours=141, gross_pay=1_455_120, withholding_tax=7_940,
        )
        # 단시간: 43.2시간 -> 445,824원, 원천세 0원 (770,000 미만)
        Payment.objects.create(
            employee=self.part_timer, year=2026, month=8,
            work_hours=43.2, gross_pay=445_824, withholding_tax=0,
        )
        # 프리랜서: 80시간 -> 1,200,000원, 원천세 39,600원
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
        # 7,940 + 0 + 39,600 = 47,540
        self.assertEqual(response.data["data"]["withholding_tax"], 47_540)

    def test_summary_labor_cost_includes_employer_insurance(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})
        data = response.data["data"]

        # 세전급여 합: 1,455,120 + 445,824 + 1,200,000 = 3,100,944
        gross_pay_sum = 1_455_120 + 445_824 + 1_200_000
        # 세전급여 합만 나오면 안 됨 — 사업주 부담 4대보험료가 더해져야 함
        self.assertGreater(data["total_labor_cost"], gross_pay_sum)

        # 정직원(전체 5종) + 단시간(산재만 0.8%) + 프리랜서(0원) 정확히 검증
        full_time_insurance = round(1_455_120 * 0.0475) + round(1_455_120 * 0.03595) \
            + round(round(1_455_120 * 0.03595) * 0.1314) + round(1_455_120 * 0.0115) \
            + round(1_455_120 * 0.008)
        part_time_insurance = round(445_824 * 0.008)
        freelancer_insurance = 0
        expected_total = gross_pay_sum + full_time_insurance + part_time_insurance + freelancer_insurance

        self.assertEqual(data["total_labor_cost"], expected_total)

    def test_summary_includes_payment_due_date(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8})
        # 8월 급여 -> 9월 10일 납부 (Figma 예시와 일치)
        self.assertEqual(response.data["data"]["payment_due_date"], "2026-09-10")

    def test_summary_december_rolls_over_to_next_year(self):
        response = self.client.get(self.url, {"year": 2026, "month": 12})
        # 12월 급여 -> 다음해 1월 10일 납부
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