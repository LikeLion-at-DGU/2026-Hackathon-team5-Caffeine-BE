from django.test import SimpleTestCase

from payroll.services.employer_insurance_service import (
    calculate_employer_insurance_total,
    calculate_national_pension_employer,
)


class EmployerInsuranceTests(SimpleTestCase):
    def test_freelancer_has_zero_insurance(self):
        self.assertEqual(calculate_employer_insurance_total("FREELANCER", 2_000_000), 0)

    def test_part_time_only_has_industrial_accident(self):
        # 445,824원 * 0.8% = 3,567원 (반올림)
        result = calculate_employer_insurance_total("PART_TIME", 445_824)
        self.assertEqual(result, round(445_824 * 0.008))

    def test_full_time_sums_all_five_items(self):
        gross_pay = 1_455_120
        result = calculate_employer_insurance_total("FULL_TIME", gross_pay)
        self.assertGreater(result, 0)
        # 대략적 자릿수 검증: 사업주 부담률 총합 약 10.77% 근처인지
        self.assertAlmostEqual(result, round(gross_pay * 0.1077), delta=500)

    def test_national_pension_cap_applies_above_ceiling(self):
        # 상한액(6,370,000원) 초과 시 상한액 기준으로 고정되어야 함
        below_cap = calculate_national_pension_employer(6_370_000)
        above_cap = calculate_national_pension_employer(8_000_000)
        self.assertEqual(below_cap, above_cap)
        self.assertEqual(above_cap, round(6_370_000 * 0.0475))

    def test_national_pension_floor_applies_below_minimum(self):
        below_floor = calculate_national_pension_employer(200_000)
        self.assertEqual(below_floor, round(400_000 * 0.0475))

    def test_unknown_employment_type_raises(self):
        with self.assertRaises(ValueError):
            calculate_employer_insurance_total("UNKNOWN", 1_000_000)