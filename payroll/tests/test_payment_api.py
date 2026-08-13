from django.test import TestCase
from rest_framework.test import APIClient

from payroll.models import Employee, Payment


class PaymentCreateAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/payroll/payments/"
        self.freelancer = Employee.objects.create(
            name="김프리", employment_type="FREELANCER", hourly_wage=15000
        )
        self.full_timer = Employee.objects.create(
            name="장예은", employment_type="FULL_TIME", hourly_wage=10320
        )
        self.part_timer = Employee.objects.create(
            name="황사라", employment_type="PART_TIME", hourly_wage=10320
        )

    def test_create_payment_for_freelancer_succeeds(self):
        payload = {"employee_id": self.freelancer.id, "year": 2026, "month": 8, "work_hours": 80}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        # 15000 * 80 = 1,200,000 / 원천세 1,200,000 * 3.3% = 39,600
        self.assertEqual(response.data["data"]["gross_pay"], 1_200_000)
        self.assertEqual(response.data["data"]["withholding_tax"], 39_600)

    def test_create_payment_for_full_time_returns_not_implemented(self):
        # 간이세액표 미구현 상태 — 501로 명확히 안내되어야 함
        payload = {"employee_id": self.full_timer.id, "year": 2026, "month": 8, "work_hours": 141}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.data["code"], "WITHHOLDING_CALCULATION_NOT_READY")
        # 계산 실패 시 DB에 저장되면 안 됨
        self.assertFalse(Payment.objects.filter(employee=self.full_timer).exists())

    def test_create_payment_for_part_time_returns_not_implemented(self):
        payload = {"employee_id": self.part_timer.id, "year": 2026, "month": 8, "work_hours": 43.2}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.data["code"], "WITHHOLDING_CALCULATION_NOT_READY")

    def test_create_payment_for_nonexistent_employee_returns_404(self):
        payload = {"employee_id": 9999, "year": 2026, "month": 8, "work_hours": 80}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "EMPLOYEE_NOT_FOUND")

    def test_create_duplicate_month_payment_returns_409(self):
        Payment.objects.create(
            employee=self.freelancer, year=2026, month=8,
            work_hours=80, gross_pay=1_200_000, withholding_tax=39_600,
        )
        payload = {"employee_id": self.freelancer.id, "year": 2026, "month": 8, "work_hours": 100}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "PAYROLL_ALREADY_EXISTS")

    def test_create_payment_with_decimal_work_hours(self):
        # Figma 예시(황사라 43.2시간)는 정직원/단시간이라 501이 나므로,
        # 프리랜서로 소수 근무시간 처리만 별도 검증
        payload = {"employee_id": self.freelancer.id, "year": 2026, "month": 8, "work_hours": 43.2}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["gross_pay"], 648_000)  # 15000 * 43.2


class PaymentListAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        employee = Employee.objects.create(
            name="김프리", employment_type="FREELANCER", hourly_wage=15000
        )
        Payment.objects.create(
            employee=employee, year=2026, month=8,
            work_hours=80, gross_pay=1_200_000, withholding_tax=39_600,
        )
        Payment.objects.create(
            employee=employee, year=2026, month=7,
            work_hours=60, gross_pay=900_000, withholding_tax=29_700,
        )

    def test_list_all_payments(self):
        response = self.client.get("/api/payroll/payments/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 2)

    def test_list_filtered_by_year_month(self):
        response = self.client.get("/api/payroll/payments/", {"year": 2026, "month": 8})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["work_hours"], "80.0")


class PaymentUpdateAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.employee = Employee.objects.create(
            name="김프리", employment_type="FREELANCER", hourly_wage=15000
        )
        self.payment = Payment.objects.create(
            employee=self.employee, year=2026, month=8,
            work_hours=80, gross_pay=1_200_000, withholding_tax=39_600,
        )
        self.url = f"/api/payroll/payments/{self.payment.id}/"

    def test_update_recalculates_gross_pay_and_tax(self):
        response = self.client.patch(self.url, {"work_hours": 100}, format="json")

        self.assertEqual(response.status_code, 200)
        # 15000 * 100 = 1,500,000 / 1,500,000 * 3.3% = 49,500
        self.assertEqual(response.data["data"]["gross_pay"], 1_500_000)
        self.assertEqual(response.data["data"]["withholding_tax"], 49_500)

    def test_update_nonexistent_payment_returns_404(self):
        response = self.client.patch(
            "/api/payroll/payments/9999/", {"work_hours": 100}, format="json"
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "PAYMENT_NOT_FOUND")