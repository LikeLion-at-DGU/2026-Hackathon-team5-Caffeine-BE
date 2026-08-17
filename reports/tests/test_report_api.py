import tempfile

from django.test import TestCase
from django.test.utils import override_settings

from businesses.models import Business
from reports.models import Report
from tax.models import MonthlyClose


class ReportFlowTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._media_directory = tempfile.TemporaryDirectory()
        cls._media_override = override_settings(MEDIA_ROOT=cls._media_directory.name)
        cls._media_override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._media_override.disable()
        cls._media_directory.cleanup()

    def setUp(self):
        self.business, _ = Business.objects.get_or_create(
            pk=1,
            defaults={"business_name": "테스트 카페"},
        )
        MonthlyClose.objects.create(
            business=self.business,
            year=2026,
            month=8,
            status=MonthlyClose.Status.CLOSED,
        )
        self.base = f"/api/businesses/{self.business.id}/reports/2026-08"

    def test_generate_creates_report_with_files(self):
        response = self.client.post(f"{self.base}/generate/")
        self.assertEqual(response.status_code, 200)
        report = Report.objects.get(business=self.business, year_month="2026-08")
        self.assertEqual(report.status, "generated")
        self.assertTrue(report.csv_file)
        self.assertTrue(report.pdf_file)

    def test_send_email_blocked_before_approval(self):
        Report.objects.create(
            business=self.business,
            year_month="2026-08",
            status="generated",
        )
        response = self.client.post(f"{self.base}/send-email/")
        self.assertEqual(response.status_code, 400)

    def test_send_email_blocked_without_accountant_email(self):
        Report.objects.create(
            business=self.business,
            year_month="2026-08",
            status="approved",
        )
        response = self.client.post(f"{self.base}/send-email/")
        self.assertEqual(response.status_code, 400)

    def test_regenerate_resets_approval(self):
        self.client.post(f"{self.base}/generate/")
        self.client.post(f"{self.base}/approve/")
        self.client.post(f"{self.base}/generate/")
        report = Report.objects.get(business=self.business, year_month="2026-08")
        self.assertEqual(report.status, "generated")
        self.assertIsNone(report.approved_at)

    def test_regenerate_resets_previous_sent_timestamp(self):
        from django.utils import timezone

        self.client.post(f"{self.base}/generate/")
        report = Report.objects.get(business=self.business, year_month="2026-08")
        report.sent_at = timezone.now()
        report.save(update_fields=["sent_at"])

        self.client.post(f"{self.base}/generate/")
        report.refresh_from_db()
        self.assertIsNone(report.sent_at)

    def test_download_rejects_unknown_file_type(self):
        self.client.post(f"{self.base}/generate/")
        response = self.client.get(f"{self.base}/download/?type=xlsx")

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "INVALID_REPORT_FILE_TYPE")

    def test_generate_requires_tax_month_close(self):
        MonthlyClose.objects.filter(
            business=self.business,
            year=2026,
            month=8,
        ).delete()

        response = self.client.post(f"{self.base}/generate/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "MONTHLY_CLOSE_REQUIRED")
