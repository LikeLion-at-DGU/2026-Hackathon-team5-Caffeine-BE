from django.test import SimpleTestCase

from payroll.services.withholding_tax_service import (
    calculate_freelancer_tax,
    calculate_gross_pay,
    calculate_withholding_tax,
    calculate_withholding_breakdown,
)


def calculate_simplified_tax_table(gross_pay):
    """테스트 편의용 래퍼 — employment_type 없이 표 기반 세액(소득세+지방소득세)만 확인."""
    return calculate_withholding_tax("FULL_TIME", gross_pay)


class FreelancerTaxTests(SimpleTestCase):
    def test_calculates_3_3_percent(self):
        # 1,200,000원 × 3.3% = 39,600원
        self.assertEqual(calculate_freelancer_tax(1_200_000), 39_600)

    def test_rounds_to_nearest_won(self):
        # 100,000원 × 3.3% = 3,300원 (반올림 확인용 케이스)
        self.assertEqual(calculate_freelancer_tax(100_000), 3_300)

    def test_minor_withholding_below_threshold_stays_zero(self):
        # 30,304원: 소득세 909원 + 지방소득세 90원 = 999원 -> 소액부징수로 0원
        self.assertEqual(calculate_freelancer_tax(30_304), 0)

    def test_minor_withholding_at_threshold_is_collected(self):
        # 30,317원: 소득세 910원 + 지방소득세 91원 = 1,001원 -> 징수
        self.assertEqual(calculate_freelancer_tax(30_317), 1_001)

    def test_zero_gross_pay_returns_zero(self):
        self.assertEqual(calculate_freelancer_tax(0), 0)


class DispatcherTests(SimpleTestCase):
    def test_freelancer_dispatches_correctly(self):
        self.assertEqual(calculate_withholding_tax("FREELANCER", 1_200_000), 39_600)

    def test_full_time_dispatches_to_simplified_table(self):
        self.assertEqual(calculate_withholding_tax("FULL_TIME", 1_455_120), 8_734)

    def test_part_time_dispatches_to_simplified_table(self):
        self.assertEqual(calculate_withholding_tax("PART_TIME", 1_455_120), 8_734)

    def test_unknown_type_raises_value_error(self):
        with self.assertRaises(ValueError):
            calculate_withholding_tax("UNKNOWN", 1_200_000)


class GrossPayTests(SimpleTestCase):
    def test_calculates_hourly_wage_times_hours(self):
        # 10,320원 × 141시간 = 1,455,120원 (Figma 예시와 일치 확인)
        self.assertEqual(calculate_gross_pay(10_320, 141), 1_455_120)

    def test_handles_decimal_hours(self):
        # 10,320원 × 43.2시간 = 445,824원 (Figma 예시와 일치 확인)
        from decimal import Decimal
        self.assertEqual(calculate_gross_pay(10_320, Decimal("43.2")), 445_824)

class SimplifiedTaxTableTests(SimpleTestCase):
    def test_below_table_minimum_returns_zero(self):
        self.assertEqual(calculate_simplified_tax_table(500_000), 0)

    def test_below_1_060_000_returns_zero(self):
        self.assertEqual(calculate_simplified_tax_table(1_059_000), 0)

    def test_just_above_1_060_000_starts_taxing(self):
        # 소득세 1,040원 + 지방소득세 104원 = 1,144원
        self.assertEqual(calculate_simplified_tax_table(1_062_000), 1_144)

    def test_matches_figma_full_time_example_gross_pay(self):
        # 소득세 7,940원 + 지방소득세 794원 = 8,734원
        self.assertEqual(calculate_simplified_tax_table(1_455_120), 8_734)

    def test_matches_official_table_upper_known_value(self):
        # 소득세 1,503,990원 + 지방소득세 150,399원 = 1,654,389원
        self.assertEqual(calculate_simplified_tax_table(9_999_000), 1_654_389)

    def test_over_10_million_uses_formula(self):
        # 소득세 1,507,400원 + 지방소득세 150,740원 = 1,658,140원
        self.assertEqual(calculate_simplified_tax_table(10_000_000), 1_658_140)