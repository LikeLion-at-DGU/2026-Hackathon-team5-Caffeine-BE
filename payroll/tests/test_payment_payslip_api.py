from django.test import TestCase
from rest_framework.test import APIClient

from payroll.models import Employee, Payment


class PaymentPayslipAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        employee = Employee.objects.create(
            name="장예은", employment_type="FULL_TIME", hourly_wage=10320
        )
        self.payment = Payment.objects.create(
            employee=employee, year=2026, month=8,
            work_hours=141, gross_pay=1_455_120, withholding_tax=8_734,
        )
        self.url = f"/api/payroll/payments/{self.payment.id}/payslip/"

    def test_get_single_payslip_returns_pdf(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_get_payslip_for_nonexistent_payment_returns_404(self):
        response = self.client.get("/api/payroll/payments/9999/payslip/")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "PAYMENT_NOT_FOUND")