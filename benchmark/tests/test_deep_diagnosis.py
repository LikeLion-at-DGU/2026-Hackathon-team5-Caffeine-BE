from django.test import TestCase
from rest_framework.test import APIClient
from businesses.models import Business
from transactions.models import MonthlySalesSummary, Transaction
from payroll.models import Employee, Payment


class DeepDiagnosisApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(
            business_name="수아네 커피집",
            business_number="2148678901",
            tax_type="GENERAL",
        )
        MonthlySalesSummary.objects.create(
            business=self.business,
            source_type="CREDIT_CARD_SALES_SUMMARY",
            year=2026,
            month=8,
            total_amount=14562300,
        )

    def test_deep_diagnosis_endpoint_returns_200(self):
        url = f"/api/businesses/{self.business.id}/benchmark/deep-diagnosis/?year=2026&month=8"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["business_id"], self.business.id)
        self.assertIn("overall_summary", data)
        self.assertIn("cost_structure_diagnosis", data)
        self.assertIn("cost_saving_simulation", data)
        self.assertIn("management_insights", data)
        self.assertIn("priority_action_tasks", data)
