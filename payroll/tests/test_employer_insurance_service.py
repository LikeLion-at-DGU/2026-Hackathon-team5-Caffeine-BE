from django.test import SimpleTestCase

from businesses.models import Business
from payroll.models import Employee
from payroll.services.employer_insurance_service import (
    calculate_employer_insurance_total,
    calculate_national_pension_employer,
)


def _make_employee(business, employment_type, is_long_term_contract=False):
    return Employee(
        business=business, name="테스트", employment_type=employment_type, hourly_wage=10320,
        is_long_term_contract=is_long_term_contract,
    )


class EmployerInsuranceTests(SimpleTestCase):
    def setUp(self):
        self.business = Business(business_name="카페비서", business_type="음식점업", business_item="커피전문점")

    def test_freelancer_has_zero_insurance(self):
        employee = _make_employee(self.business, "FREELANCER")
        self.assertEqual(calculate_employer_insurance_total(employee, 2_000_000), 0)

    def test_part_time_short_term_has_only_industrial_accident(self):
        # 계약이 3개월 미만(is_long_term_contract=False)이면 고용보험 미적용
        employee = _make_employee(self.business, "PART_TIME", is_long_term_contract=False)
        result = calculate_employer_insurance_total(employee, 445_824)
        self.assertEqual(result, round(445_824 * 0.0086))

    def test_part_time_long_term_includes_employment_insurance(self):
        # 계약이 3개월 이상/무기한(is_long_term_contract=True)이면 첫 달부터 고용보험 적용
        employee = _make_employee(self.business, "PART_TIME", is_long_term_contract=True)
        result = calculate_employer_insurance_total(employee, 445_824)
        expected = round(445_824 * 0.0086) + round(445_824 * 0.0115)
        self.assertEqual(result, expected)

    def test_full_time_sums_all_five_items(self):
        employee = _make_employee(self.business, "FULL_TIME")
        gross_pay = 1_455_120
        result = calculate_employer_insurance_total(employee, gross_pay)
        self.assertGreater(result, 0)
        # 사업주 부담률 총합: 국민연금4.75+건강3.595+장기요양0.4724+고용1.15+산재0.86 ≈ 10.83%
        self.assertAlmostEqual(result, round(gross_pay * 0.1083), delta=500)

    def test_national_pension_cap_applies_above_ceiling(self):
        # 2026-07-01~2027-06-30 기준 상한액 6,590,000원
        below_cap = calculate_national_pension_employer(6_590_000)
        above_cap = calculate_national_pension_employer(8_000_000)
        self.assertEqual(below_cap, above_cap)
        self.assertEqual(above_cap, round(6_590_000 * 0.0475))

    def test_national_pension_floor_applies_below_minimum(self):
        # 2026-07-01~2027-06-30 기준 하한액 410,000원
        below_floor = calculate_national_pension_employer(200_000)
        self.assertEqual(below_floor, round(410_000 * 0.0475))

    def test_unknown_employment_type_raises(self):
        employee = _make_employee(self.business, "UNKNOWN")
        with self.assertRaises(ValueError):
            calculate_employer_insurance_total(employee, 1_000_000)