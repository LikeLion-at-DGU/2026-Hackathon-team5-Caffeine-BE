from django.test import TestCase
from businesses.models import Business
from .models import Report


class ReportFlowTests(TestCase):
    def setUp(self):
        self.business, _ = Business.objects.get_or_create(pk=1, defaults={"business_name": "테스트 카페"})
        self.base = f"/api/businesses/{self.business.id}/reports/2026-08"

    def test_generate_creates_report_with_files(self):
        response = self.client.post(f"{self.base}/generate/")
        self.assertEqual(response.status_code, 200)
        report = Report.objects.get(business=self.business, year_month="2026-08")
        self.assertEqual(report.status, "generated")
        self.assertTrue(report.csv_file)
        self.assertTrue(report.pdf_file)

    def test_send_email_blocked_before_approval(self):
        Report.objects.create(business=self.business, year_month="2026-08", status="generated")
        response = self.client.post(f"{self.base}/send-email/")
        self.assertEqual(response.status_code, 400)

    def test_send_email_blocked_without_accountant_email(self):
        Report.objects.create(business=self.business, year_month="2026-08", status="approved")
        response = self.client.post(f"{self.base}/send-email/")
        self.assertEqual(response.status_code, 400)

    def test_regenerate_resets_approval(self):
        self.client.post(f"{self.base}/generate/")
        self.client.post(f"{self.base}/approve/")
        self.client.post(f"{self.base}/generate/")
        report = Report.objects.get(business=self.business, year_month="2026-08")
        self.assertEqual(report.status, "generated")
        self.assertIsNone(report.approved_at)