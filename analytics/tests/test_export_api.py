from django.test import TestCase
from rest_framework.test import APIClient

from analytics.models import MonthlyClose
from businesses.models import Business
from payroll.models import Employee, Payment


class ExportAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(business_name="카페비서")
        self.url = f"/api/businesses/{self.business.id}/analytics/export/"

        employee = Employee.objects.create(
            business=self.business, name="장예은", employment_type="FULL_TIME", hourly_wage=10320
        )
        Payment.objects.create(
            employee=employee, year=2026, month=8,
            work_hours=141, gross_pay=1_455_120, withholding_tax=8_734,
        )

    def test_export_without_close_returns_409(self):
        response = self.client.get(self.url, {"year": 2026, "month": 8, "file_type": "pdf"})

        self.assertEqual(response.status_code, 409)

    def test_export_pdf_after_close_succeeds(self):
        MonthlyClose.objects.create(business=self.business, year=2026, month=8)

        response = self.client.get(self.url, {"year": 2026, "month": 8, "file_type": "pdf"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_export_xlsx_after_close_succeeds(self):
        MonthlyClose.objects.create(business=self.business, year=2026, month=8)

        response = self.client.get(self.url, {"year": 2026, "month": 8, "file_type": "xlsx"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        self.assertTrue(response.content.startswith(b"PK"))

    def test_export_invalid_format_returns_400(self):
        MonthlyClose.objects.create(business=self.business, year=2026, month=8)

        response = self.client.get(self.url, {"year": 2026, "month": 8, "file_type": "hwp"})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "INVALID_EXPORT_FORMAT")

    def test_export_missing_period_returns_400(self):
        response = self.client.get(self.url, {"file_type": "pdf"})
        self.assertEqual(response.status_code, 400)

    def test_export_only_counts_own_business(self):
        # 다른 사업장은 마감 여부와 무관하게 별개로 취급되는지 확인
        other_business = Business.objects.create(business_name="옆동네카페")
        MonthlyClose.objects.create(business=self.business, year=2026, month=8)

        response = self.client.get(
            f"/api/businesses/{other_business.id}/analytics/export/",
            {"year": 2026, "month": 8, "file_type": "pdf"},
        )

        self.assertEqual(response.status_code, 409)