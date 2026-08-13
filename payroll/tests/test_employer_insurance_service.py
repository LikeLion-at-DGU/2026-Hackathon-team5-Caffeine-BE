from datetime import date

from django.test import SimpleTestCase

from payroll.models import Employee
from payroll.services.employer_insurance_service import (
    calculate_employer_insurance_total,
    calculate_national_pension_employer,
)


def _make_employee(employment_type, work_started_at=None):
    return Employee(
        name="테스트", employment_type=employment_type, hourly_wage=10320,
        work_started_at=work_started_at,
    )


class EmployerInsuranceTests(SimpleTestCase):
    def test_freelancer_has_zero_insurance(self):
        employee = _make_employee("FREELANCER")
        self.assertEqual(calculate_employer_insurance_total(employee, 2_000_000, 2026, 8), 0)

    def test_part_time_without_start_date_has_only_industrial_accident(self):
        employee = _make_employee("PART_TIME", work_started_at=None)
        result = calculate_employer_insurance_total(employee, 445_824, 2026, 8)
        self.assertEqual(result, round(445_824 * 0.008))

    def test_part_time_under_three_months_excludes_employment_insurance(self):
        # 2026-07-01 입사, 2026-08 급여 기준 -> 아직 3개월 안 지남
        employee = _make_employee("PART_TIME", work_started_at=date(2026, 7, 1))
        result = calculate_employer_insurance_total(employee, 445_824, 2026, 8)
        self.assertEqual(result, round(445_824 * 0.008))

    def test_part_time_over_three_months_includes_employment_insurance(self):
        # 2026-04-01 입사, 2026-08 급여 기준 -> 3개월 이상 경과
        employee = _make_employee("PART_TIME", work_started_at=date(2026, 4, 1))
        result = calculate_employer_insurance_total(employee, 445_824, 2026, 8)
        expected = round(445_824 * 0.008) + round(445_824 * 0.0115)
        self.assertEqual(result, expected)

    def test_part_time_exactly_at_three_month_boundary_includes(self):
        # 2026-05-08 입사 -> 2026-08-08이 3개월째. 2026년 8월 급여(월말 기준)는 포함되어야 함
        employee = _make_employee("PART_TIME", work_started_at=date(2026, 5, 8))
        result = calculate_employer_insurance_total(employee, 445_824, 2026, 8)
        expected = round(445_824 * 0.008) + round(445_824 * 0.0115)
        self.assertEqual(result, expected)

    def test_full_time_sums_all_five_items(self):
        employee = _make_employee("FULL_TIME")
        gross_pay = 1_455_120
        result = calculate_employer_insurance_total(employee, gross_pay, 2026, 8)
        self.assertGreater(result, 0)
        self.assertAlmostEqual(result, round(gross_pay * 0.1077), delta=500)

    def test_national_pension_cap_applies_above_ceiling(self):
        below_cap = calculate_national_pension_employer(6_370_000)
        above_cap = calculate_national_pension_employer(8_000_000)
        self.assertEqual(below_cap, above_cap)
        self.assertEqual(above_cap, round(6_370_000 * 0.0475))

    def test_national_pension_floor_applies_below_minimum(self):
        below_floor = calculate_national_pension_employer(200_000)
        self.assertEqual(below_floor, round(400_000 * 0.0475))

    def test_unknown_employment_type_raises(self):
        employee = _make_employee("UNKNOWN")
        with self.assertRaises(ValueError):
            calculate_employer_insurance_total(employee, 1_000_000, 2026, 8)