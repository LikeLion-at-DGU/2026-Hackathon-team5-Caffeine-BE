from django.test import TestCase
from rest_framework.test import APIClient

from payroll.models import Employee, Payment


class PaymentExportAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/payroll/payments/export/"
        employee = Employee.objects.create(
            name="장예은", employment_type="FULL_TIME", hourly_wage=10320
        )
        Payment.objects.create(
            employee=employee, year=2026, month=8,
            work_hours=141, gross_pay=1_455_120, withholding_tax=8_734,
        )

    def test_export_pdf_returns_pdf_file(self):
        response = self.client.post(self.url, {"year": 2026, "month": 8, "format": "pdf"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertGreater(len(response.content), 0)
        # PDF 파일은 항상 %PDF로 시작함
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_export_xlsx_returns_xlsx_file(self):
        response = self.client.post(self.url, {"year": 2026, "month": 8, "format": "xlsx"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertGreater(len(response.content), 0)
        # XLSX(zip 기반 포맷)는 항상 PK로 시작함
        self.assertTrue(response.content.startswith(b"PK"))

    def test_export_invalid_format_returns_400(self):
        response = self.client.post(self.url, {"year": 2026, "month": 8, "format": "hwp"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "INVALID_EXPORT_FORMAT")

    def test_export_no_data_for_period_returns_404(self):
        response = self.client.post(self.url, {"year": 2020, "month": 1, "format": "pdf"}, format="json")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "PAYROLL_DATA_NOT_FOUND")