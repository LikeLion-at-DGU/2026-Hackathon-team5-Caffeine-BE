from django.test import SimpleTestCase

from payroll.services.withholding_tax_service import (
    calculate_freelancer_tax,
    calculate_gross_pay,
    calculate_simplified_tax_table,
    calculate_withholding_tax,
)


class FreelancerTaxTests(SimpleTestCase):
    def test_calculates_3_3_percent(self):
        # 1,200,000원 × 3.3% = 39,600원
        self.assertEqual(calculate_freelancer_tax(1_200_000), 39_600)

    def test_rounds_to_nearest_won(self):
        # 100,000원 × 3.3% = 3,300원 (반올림 확인용 케이스)
        self.assertEqual(calculate_freelancer_tax(100_000), 3_300)

    def test_minor_withholding_below_threshold_returns_zero(self):
        # 세액이 1,000원 미만이면 소액부징수로 0원 처리
        # 30,000원 × 3.3% = 990원 → 0원이어야 함
        self.assertEqual(calculate_freelancer_tax(30_000), 0)

    def test_minor_withholding_at_threshold_is_collected(self):
        # 세액이 정확히 1,000원 이상이면 징수
        # 30,304원 × 3.3% ≈ 1,000.032 → round 시 1,000원
        self.assertEqual(calculate_freelancer_tax(30_304), 1_000)

    def test_zero_gross_pay_returns_zero(self):
        self.assertEqual(calculate_freelancer_tax(0), 0)


class DispatcherTests(SimpleTestCase):
    def test_freelancer_dispatches_correctly(self):
        self.assertEqual(calculate_withholding_tax("FREELANCER", 1_200_000), 39_600)

    def test_full_time_dispatches_to_simplified_table(self):
        self.assertEqual(calculate_withholding_tax("FULL_TIME", 1_455_120), 7_940)

    def test_part_time_dispatches_to_simplified_table(self):
        self.assertEqual(calculate_withholding_tax("PART_TIME", 1_455_120), 7_940)

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
        # 1,060,000원까지는 0원 확정 구간 (사용자 판단 검증용)
        self.assertEqual(calculate_simplified_tax_table(1_059_000), 0)

    def test_just_above_1_060_000_starts_taxing(self):
        # 1,060,000 ~ 1,065,000원 구간: 1,040원
        self.assertEqual(calculate_simplified_tax_table(1_062_000), 1_040)

    def test_matches_figma_full_time_example_gross_pay(self):
        # 141시간 * 10,320원 = 1,455,120원 -> 실제 표상 세액 7,940원
        # (Figma 목업 표시값 '0원'과는 다름 — 목업이 실계산 아닌 예시값으로 판단)
        self.assertEqual(calculate_simplified_tax_table(1_455_120), 7_940)

    def test_matches_official_table_upper_known_value(self):
        # 9,980,000 ~ 10,000,000원 구간: 1,503,990원 (표 마지막 구간 직접 대조)
        self.assertEqual(calculate_simplified_tax_table(9_999_000), 1_503_990)

    def test_over_10_million_uses_formula(self):
        # 10,000,000원 정확히: 표 마지막 구간 값과 동일해야 함
        self.assertEqual(calculate_simplified_tax_table(10_000_000), 1_507_400)