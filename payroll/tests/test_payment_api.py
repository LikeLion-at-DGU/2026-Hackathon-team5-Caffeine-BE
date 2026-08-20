from django.test import TestCase
from rest_framework.test import APIClient

from businesses.models import Business
from payroll.models import Employee, Payment


class PaymentCreateAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(business_name="카페비서")
        self.url = f"/api/businesses/{self.business.id}/payroll/payments/"
        self.freelancer = Employee.objects.create(
            business=self.business, name="김프리", employment_type="FREELANCER", hourly_wage=15000
        )
        self.full_timer = Employee.objects.create(
            business=self.business, name="장예은", employment_type="FULL_TIME", hourly_wage=10320
        )
        self.part_timer = Employee.objects.create(
            business=self.business, name="황사라", employment_type="PART_TIME", hourly_wage=10320
        )

    def test_create_payment_for_freelancer_succeeds(self):
        payload = {"employee_id": self.freelancer.id, "year": 2026, "month": 8, "work_hours": 80}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["gross_pay"], 1_200_000)
        self.assertEqual(response.data["data"]["withholding_tax"], 39_600)

    def test_create_payment_for_full_time_calculates_simplified_tax(self):
        payload = {"employee_id": self.full_timer.id, "year": 2026, "month": 8, "work_hours": 141}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["gross_pay"], 1_455_120)
        self.assertEqual(response.data["data"]["withholding_tax"], 8_734)

    def test_create_payment_for_part_time_below_minimum_returns_zero_tax(self):
        payload = {"employee_id": self.part_timer.id, "year": 2026, "month": 8, "work_hours": 43.2}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["gross_pay"], 445_824)
        self.assertEqual(response.data["data"]["withholding_tax"], 0)

    def test_full_time_income_under_770k_returns_zero_tax(self):
        payload = {"employee_id": self.full_timer.id, "year": 2026, "month": 9, "work_hours": 70}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["withholding_tax"], 0)

    def test_full_time_income_at_bracket_boundary(self):
        payload = {"employee_id": self.full_timer.id, "year": 2026, "month": 10, "work_hours": 102.7}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["withholding_tax"], 0)

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
        payload = {"employee_id": self.freelancer.id, "year": 2026, "month": 8, "work_hours": 43.2}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["data"]["gross_pay"], 648_000)


class PaymentListAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(business_name="카페비서")
        employee = Employee.objects.create(
            business=self.business, name="김프리", employment_type="FREELANCER", hourly_wage=15000
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
        response = self.client.get(f"/api/businesses/{self.business.id}/payroll/payments/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 2)

    def test_list_filtered_by_year_month(self):
        response = self.client.get(
            f"/api/businesses/{self.business.id}/payroll/payments/", {"year": 2026, "month": 8}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 1)
        self.assertEqual(response.data["data"][0]["work_hours"], "80.0")

    def test_part_time_insurance_status_changes_deductions_not_withholding_tax(self):
        insured = Employee.objects.create(
            business=self.business,
            name="고용보험 적용",
            employment_type="PART_TIME",
            hourly_wage=10_320,
            is_long_term_contract=True,
        )
        uninsured = Employee.objects.create(
            business=self.business,
            name="고용보험 미적용",
            employment_type="PART_TIME",
            hourly_wage=10_320,
            is_long_term_contract=False,
        )
        for employee in (insured, uninsured):
            Payment.objects.create(
                employee=employee,
                year=2026,
                month=8,
                work_hours=141,
                gross_pay=1_455_120,
                withholding_tax=8_734,
            )

        response = self.client.get(
            f"/api/businesses/{self.business.id}/payroll/payments/",
            {"year": 2026, "month": 8},
        )
        rows = {row["employee_name"]: row for row in response.data["data"]}
        insured_row = rows["고용보험 적용"]
        uninsured_row = rows["고용보험 미적용"]

        # 같은 고용형태/세전급여이면 원천세는 같고, 고용보험과 실수령액만 달라진다.
        self.assertEqual(insured_row["withholding_tax"], uninsured_row["withholding_tax"])
        self.assertEqual(insured_row["employment_insurance"], round(1_455_120 * 0.009))
        self.assertEqual(uninsured_row["employment_insurance"], 0)
        self.assertGreater(insured_row["deductions_total"], uninsured_row["deductions_total"])
        self.assertLess(insured_row["net_pay"], uninsured_row["net_pay"])


class PaymentUpdateAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(business_name="카페비서")
        self.employee = Employee.objects.create(
            business=self.business, name="김프리", employment_type="FREELANCER", hourly_wage=15000
        )
        self.payment = Payment.objects.create(
            employee=self.employee, year=2026, month=8,
            work_hours=80, gross_pay=1_200_000, withholding_tax=39_600,
        )
        self.url = f"/api/businesses/{self.business.id}/payroll/payments/{self.payment.id}/"

    def test_update_recalculates_gross_pay_and_tax(self):
        response = self.client.patch(self.url, {"work_hours": 100}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["gross_pay"], 1_500_000)
        self.assertEqual(response.data["data"]["withholding_tax"], 49_500)

    def test_update_nonexistent_payment_returns_404(self):
        response = self.client.patch(
            f"/api/businesses/{self.business.id}/payroll/payments/9999/", {"work_hours": 100}, format="json"
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "PAYMENT_NOT_FOUND")
