from django.test import SimpleTestCase

from chat.services.periods import extract_requested_periods


class RequestedPeriodsTests(SimpleTestCase):
    def test_inherits_explicit_year_for_following_month(self):
        self.assertEqual(
            extract_requested_periods(
                "2025년 6월과 7월 인건비를 비교해줘",
                default_year=2026,
                default_month=8,
            ),
            [(2025, 6), (2025, 7)],
        )

    def test_extracts_two_months_in_same_year(self):
        self.assertEqual(
            extract_requested_periods(
                "6월, 7월 급여 차이가 얼마야?",
                default_year=2026,
                default_month=8,
            ),
            [(2026, 6), (2026, 7)],
        )

    def test_previous_and_current_month_across_year_boundary(self):
        self.assertEqual(
            extract_requested_periods(
                "지난달과 이번달을 비교해줘",
                default_year=2026,
                default_month=1,
            ),
            [(2025, 12), (2026, 1)],
        )
