from django.test import TestCase

from payroll.models import Employee, Payment
from payroll.services.payment_service import get_payslip_data


class PayslipDataTests(TestCase):
    def test_freelancer_payslip_has_only_income_tax_deduction(self):
        employee = Employee.objects.create(
            name="김프리", employment_type="FREELANCER", hourly_wage=15000
        )
        payment = Payment.objects.create(
            employee=employee, year=2026, month=8,
            work_hours=80, gross_pay=1_200_000, withholding_tax=39_600,
        )
        data = get_payslip_data(payment)

        self.assertEqual(data["income_tax"], 36_000)
        self.assertEqual(data["local_income_tax"], 3_600)
        self.assertEqual(data["national_pension"], 0)
        self.assertEqual(data["health_insurance"], 0)
        self.assertEqual(data["deductions_total"], 39_600)
        self.assertEqual(data["net_pay"], 1_200_000 - 39_600)

    def test_full_time_payslip_has_all_deductions(self):
        employee = Employee.objects.create(
            name="장예은", employment_type="FULL_TIME", hourly_wage=10320
        )
        payment = Payment.objects.create(
            employee=employee, year=2026, month=8,
            work_hours=141, gross_pay=1_455_120, withholding_tax=8_734,
        )
        data = get_payslip_data(payment)

        self.assertEqual(data["employee_id"], employee.id)
        self.assertEqual(data["income_tax"], 7_940)
        self.assertEqual(data["local_income_tax"], 794)
        self.assertGreater(data["national_pension"], 0)
        self.assertGreater(data["health_insurance"], 0)
        self.assertGreater(data["long_term_care"], 0)
        self.assertGreater(data["employment_insurance"], 0)

        expected_deductions = (
            data["income_tax"] + data["local_income_tax"] + data["national_pension"]
            + data["health_insurance"] + data["long_term_care"] + data["employment_insurance"]
        )
        self.assertEqual(data["deductions_total"], expected_deductions)
        self.assertEqual(data["net_pay"], payment.gross_pay - expected_deductions)

    def test_part_time_without_start_date_has_minimal_deductions(self):
        employee = Employee.objects.create(
            name="황사라", employment_type="PART_TIME", hourly_wage=10320
        )
        payment = Payment.objects.create(
            employee=employee, year=2026, month=8,
            work_hours=43.2, gross_pay=445_824, withholding_tax=0,
        )
        data = get_payslip_data(payment)

        # 770,000원 미만이라 원천세 0원 + 근속 3개월 미만이라 4대보험도 0원
        self.assertEqual(data["deductions_total"], 0)
        self.assertEqual(data["net_pay"], 445_824)
        