from django.test import SimpleTestCase

from payroll.models import Employee
from payroll.services.employee_insurance_service import calculate_employee_insurance_breakdown


def _make_employee(employment_type, is_long_term_contract=False):
    return Employee(
        name="테스트", employment_type=employment_type, hourly_wage=10320,
        is_long_term_contract=is_long_term_contract,
    )


class EmployeeInsuranceTests(SimpleTestCase):
    def test_freelancer_has_zero_insurance(self):
        employee = _make_employee("FREELANCER")
        result = calculate_employee_insurance_breakdown(employee, 2_000_000)
        self.assertEqual(result["total"], 0)

    def test_part_time_short_term_has_zero(self):
        employee = _make_employee("PART_TIME", is_long_term_contract=False)
        result = calculate_employee_insurance_breakdown(employee, 445_824)
        self.assertEqual(result["total"], 0)

    def test_part_time_long_term_has_employment_insurance_only(self):
        employee = _make_employee("PART_TIME", is_long_term_contract=True)
        result = calculate_employee_insurance_breakdown(employee, 445_824)
        self.assertEqual(result["national_pension"], 0)
        self.assertEqual(result["health_insurance"], 0)
        self.assertEqual(result["employment_insurance"], round(445_824 * 0.009))
        self.assertEqual(result["total"], round(445_824 * 0.009))

    def test_full_time_has_all_four_items(self):
        employee = _make_employee("FULL_TIME")
        gross_pay = 1_455_120
        result = calculate_employee_insurance_breakdown(employee, gross_pay)

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
        from payroll.services.employer_insurance_service import calculate_national_pension_employer
        from payroll.services.employee_insurance_service import calculate_national_pension_employee

        gross_pay = 1_455_120
        self.assertEqual(
            calculate_national_pension_employer(gross_pay),
            calculate_national_pension_employee(gross_pay),
        )

    def test_full_time_employee_pays_less_employment_insurance_than_employer(self):
        from payroll.services.employer_insurance_service import calculate_employment_insurance_employer
        from payroll.services.employee_insurance_service import calculate_employment_insurance_employee

        gross_pay = 1_455_120
        employer_amount = calculate_employment_insurance_employer(gross_pay)
        employee_amount = calculate_employment_insurance_employee(gross_pay)
        self.assertLess(employee_amount, employer_amount)

    def test_unknown_employment_type_raises(self):
        employee = _make_employee("UNKNOWN")
        with self.assertRaises(ValueError):
            calculate_employee_insurance_breakdown(employee, 1_000_000)