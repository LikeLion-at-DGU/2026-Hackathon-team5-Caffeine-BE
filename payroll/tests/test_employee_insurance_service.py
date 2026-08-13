from datetime import date

from django.test import SimpleTestCase

from payroll.models import Employee
from payroll.services.employee_insurance_service import calculate_employee_insurance_breakdown


def _make_employee(employment_type, work_started_at=None):
    return Employee(
        name="테스트", employment_type=employment_type, hourly_wage=10320,
        work_started_at=work_started_at,
    )


class EmployeeInsuranceTests(SimpleTestCase):
    def test_freelancer_has_zero_insurance(self):
        employee = _make_employee("FREELANCER")
        result = calculate_employee_insurance_breakdown(employee, 2_000_000, 2026, 8)
        self.assertEqual(result["total"], 0)

    def test_part_time_without_start_date_has_zero(self):
        employee = _make_employee("PART_TIME", work_started_at=None)
        result = calculate_employee_insurance_breakdown(employee, 445_824, 2026, 8)
        self.assertEqual(result["total"], 0)

    def test_part_time_over_three_months_has_employment_insurance_only(self):
        employee = _make_employee("PART_TIME", work_started_at=date(2026, 4, 1))
        result = calculate_employee_insurance_breakdown(employee, 445_824, 2026, 8)
        self.assertEqual(result["national_pension"], 0)
        self.assertEqual(result["health_insurance"], 0)
        self.assertEqual(result["employment_insurance"], round(445_824 * 0.009))
        self.assertEqual(result["total"], round(445_824 * 0.009))

    def test_full_time_has_all_four_items(self):
        employee = _make_employee("FULL_TIME")
        gross_pay = 1_455_120
        result = calculate_employee_insurance_breakdown(employee, gross_pay, 2026, 8)

        self.assertGreater(result["national_pension"], 0)
        self.assertGreater(result["health_insurance"], 0)
        self.assertGreater(result["long_term_care"], 0)
        self.assertGreater(result["employment_insurance"], 0)
        self.assertEqual(
            result["total"],
            result["national_pension"] + result["health_insurance"]
            + result["long_term_care"] + result["employment_insurance"],
        )

    def test_full_time_employer_and_employee_pay_same_national_pension(self):
        # 국민연금/건강보험은 노사 50:50 -> 사업주 부담과 근로자 부담이 같아야 함
        from payroll.services.employer_insurance_service import calculate_national_pension_employer
        from payroll.services.employee_insurance_service import calculate_national_pension_employee

        gross_pay = 1_455_120
        self.assertEqual(
            calculate_national_pension_employer(gross_pay),
            calculate_national_pension_employee(gross_pay),
        )

    def test_full_time_employee_pays_less_employment_insurance_than_employer(self):
        # 근로자는 실업급여분(0.9%)만, 사업주는 +고용안정직업능력개발사업(0.25%) 추가
        from payroll.services.employer_insurance_service import calculate_employment_insurance_employer
        from payroll.services.employee_insurance_service import calculate_employment_insurance_employee

        gross_pay = 1_455_120
        employer_amount = calculate_employment_insurance_employer(gross_pay)
        employee_amount = calculate_employment_insurance_employee(gross_pay)
        self.assertLess(employee_amount, employer_amount)

    def test_unknown_employment_type_raises(self):
        employee = _make_employee("UNKNOWN")
        with self.assertRaises(ValueError):
            calculate_employee_insurance_breakdown(employee, 1_000_000, 2026, 8)