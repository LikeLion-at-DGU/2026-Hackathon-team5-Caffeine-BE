from django.test import TestCase
from rest_framework.test import APIClient

from businesses.models import Business
from payroll.models import Employee, Payment


class BusinessScopeTests(TestCase):
    """다른 사업장의 데이터가 서로 섞이지 않는지 검증 (이슈 #7 핵심 요건)."""

    def setUp(self):
        self.client = APIClient()
        self.business_a = Business.objects.create(business_name="카페비서")
        self.business_b = Business.objects.create(business_name="옆동네카페")

        self.employee_a = Employee.objects.create(
            business=self.business_a, name="장예은", employment_type="FULL_TIME", hourly_wage=10320
        )
        self.employee_b = Employee.objects.create(
            business=self.business_b, name="다른직원", employment_type="FULL_TIME", hourly_wage=10320
        )

        self.payment_a = Payment.objects.create(
            employee=self.employee_a, year=2026, month=8,
            work_hours=141, gross_pay=1_455_120, withholding_tax=8_734,
        )
        self.payment_b = Payment.objects.create(
            employee=self.employee_b, year=2026, month=8,
            work_hours=100, gross_pay=1_032_000, withholding_tax=0,
        )

    def test_employee_list_only_shows_own_business(self):
        response = self.client.get(f"/api/businesses/{self.business_a.id}/payroll/employees/")

        names = [item["name"] for item in response.data["data"]]
        self.assertIn("장예은", names)
        self.assertNotIn("다른직원", names)

    def test_employee_detail_from_other_business_returns_404(self):
        # 사업장 A 경로로 사업장 B 직원의 employee_id를 조회 시도
        response = self.client.get(
            f"/api/businesses/{self.business_a.id}/payroll/employees/{self.employee_b.id}/"
        )
        # GET 단건 조회 endpoint가 없으므로 PATCH로 존재 여부 검증
        response = self.client.patch(
            f"/api/businesses/{self.business_a.id}/payroll/employees/{self.employee_b.id}/",
            {"hourly_wage": 99999}, format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "EMPLOYEE_NOT_FOUND")

        # 실제로 안 바뀌었는지 DB에서도 확인
        self.employee_b.refresh_from_db()
        self.assertEqual(self.employee_b.hourly_wage, 10320)

    def test_employee_delete_from_other_business_returns_404(self):
        response = self.client.delete(
            f"/api/businesses/{self.business_a.id}/payroll/employees/{self.employee_b.id}/"
        )
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Employee.objects.filter(id=self.employee_b.id).exists())

    def test_payment_list_only_shows_own_business(self):
        response = self.client.get(f"/api/businesses/{self.business_a.id}/payroll/payments/")

        payment_ids = [item["payment_id"] for item in response.data["data"]]
        self.assertIn(self.payment_a.id, payment_ids)
        self.assertNotIn(self.payment_b.id, payment_ids)

    def test_payment_detail_from_other_business_returns_404(self):
        response = self.client.patch(
            f"/api/businesses/{self.business_a.id}/payroll/payments/{self.payment_b.id}/",
            {"work_hours": 50}, format="json",
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "PAYMENT_NOT_FOUND")

    def test_payslip_from_other_business_returns_404(self):
        response = self.client.get(
            f"/api/businesses/{self.business_a.id}/payroll/payments/{self.payment_b.id}/payslip/"
        )
        self.assertEqual(response.status_code, 404)

    def test_summary_only_counts_own_business(self):
        response = self.client.get(
            f"/api/businesses/{self.business_a.id}/payroll/summary/", {"year": 2026, "month": 8}
        )
        # 사업장 A에는 직원 1명만 등록되어 있으므로, 사업장 B 데이터가 섞이면 2명으로 잘못 나옴
        self.assertEqual(response.data["data"]["employee_count"], 1)

    def test_create_employee_with_duplicate_name_across_businesses_is_allowed(self):
        # 이름 중복 검증은 같은 사업장 내에서만 적용되어야 함 — 다른 사업장이면 같은 이름도 허용
        payload = {"name": "다른직원", "employment_type": "PART_TIME", "hourly_wage": 10000}
        response = self.client.post(
            f"/api/businesses/{self.business_a.id}/payroll/employees/", payload, format="json"
        )
        self.assertEqual(response.status_code, 201)