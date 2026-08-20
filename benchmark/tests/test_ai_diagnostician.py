from decimal import Decimal
from unittest.mock import MagicMock
from django.test import TestCase, override_settings

from businesses.models import Business
from benchmark.services.calculator import BenchmarkCalculator
from benchmark.services.ai_diagnostician import AIDiagnostician, RuleBasedDiagnostician
from transactions.models import MonthlySalesSummary


class AIDiagnosticianTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            business_name="카페비서 1호점",
            business_number="1234567890",
        )
        self.calc = BenchmarkCalculator.calculate(self.business, year=2026, month=8)

    def test_rule_based_fallback_returns_structured_diagnosis(self):
        result = RuleBasedDiagnostician.diagnose(self.calc)

        # 데이터가 전혀 없는 매장을 상위 매장으로 오판하지 않는다.
        self.assertEqual(result.score, 45)
        self.assertEqual(result.grade_label, "위험 — 비용 구조 개선 필요")
        self.assertEqual(len(result.prescriptions), 3)
        self.assertEqual(len(result.summary_points), 3)
        self.assertTrue(result.is_fallback)

    @override_settings(OPENAI_API_KEY="")
    def test_diagnose_without_api_key_falls_back_gracefully(self):
        diagnostician = AIDiagnostician()
        result = diagnostician.diagnose(self.calc)

        self.assertTrue(result.is_fallback)
        self.assertEqual(len(result.prescriptions), 3)

    @override_settings(OPENAI_API_KEY="mock-openai-key")
    def test_diagnose_with_mock_openai_success(self):
        MonthlySalesSummary.objects.create(
            business=self.business,
            year=2026,
            month=8,
            source_type=MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
            total_amount=20_000_000,
            transaction_count=100,
        )
        self.calc = BenchmarkCalculator.calculate(self.business, year=2026, month=8)
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = """{
            "score": 88,
            "grade_label": "우수 — 상위 10% 매장",
            "prescriptions": [
                {"id": 1, "type": "COST_REDUCTION", "title": "원두 납품단가 조정"},
                {"id": 2, "type": "REVENUE_BOOST", "title": "피크타임 세트메뉴 도입"},
                {"id": 3, "type": "TAX_SAVING", "title": "면세계산서 수취"}
            ],
            "summary_points": ["요약1", "요약2", "요약3"]
        }"""
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        diagnostician = AIDiagnostician(client=mock_client)
        result = diagnostician.diagnose(self.calc)

        self.assertFalse(result.is_fallback)
        self.assertEqual(result.score, 88)
        self.assertEqual(result.grade_label, "우수 — 상위 10% 매장")
        self.assertEqual(len(result.prescriptions), 3)
