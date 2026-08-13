from django.test import TestCase
from rest_framework.test import APIClient

from payroll.models import Employee


class EmployeeCreateAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = "/api/payroll/employees/"

    def test_create_employee_success(self):
        payload = {
            "name": "김민지",
            "employment_type": "PART_TIME",
            "hourly_wage": 12000,
            "monthly_contracted_hours": 80,
            "rrn_front": "990101-1",
        }
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["code"], "EMPLOYEE_CREATE_SUCCESS")
        self.assertIn("employee_id", response.data["data"])

    def test_create_employee_stores_encrypted_rrn(self):
        payload = {
            "name": "김민지",
            "employment_type": "PART_TIME",
            "hourly_wage": 12000,
            "rrn_front": "990101-1",
        }
        self.client.post(self.url, payload, format="json")

        employee = Employee.objects.get(name="김민지")
        # 평문 그대로 저장되면 안 됨
        self.assertNotEqual(employee.rrn_front_encrypted, "990101-1")
        # 복호화하면 원본이 나와야 함
        self.assertEqual(employee.get_rrn_front(), "990101-1")

    def test_create_employee_without_rrn_is_optional(self):
        payload = {
            "name": "황사라",
            "employment_type": "FULL_TIME",
            "hourly_wage": 10320,
        }
        response = self.client.post(self.url, payload, format="json")
        self.assertEqual(response.status_code, 201)

    def test_create_employee_missing_required_field_fails(self):
        payload = {"employment_type": "FULL_TIME", "hourly_wage": 10320}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])
        self.assertEqual(response.data["code"], "INVALID_EMPLOYEE_DATA")

    def test_create_duplicate_name_returns_409(self):
        Employee.objects.create(name="장예은", employment_type="FULL_TIME", hourly_wage=10320)
        payload = {"name": "장예은", "employment_type": "FULL_TIME", "hourly_wage": 10320}
        response = self.client.post(self.url, payload, format="json")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "EMPLOYEE_ALREADY_EXISTS")


class EmployeeListAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        Employee.objects.create(name="장예은", employment_type="FULL_TIME", hourly_wage=10320)
        Employee.objects.create(name="황사라", employment_type="PART_TIME", hourly_wage=10320)

    def test_list_employees_success(self):
        response = self.client.get("/api/payroll/employees/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 2)

    def test_list_does_not_expose_rrn_front(self):
        response = self.client.get("/api/payroll/employees/")
        for item in response.data["data"]:
            self.assertNotIn("rrn_front", item)
            self.assertNotIn("rrn_front_encrypted", item)


class EmployeeDetailAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.employee = Employee.objects.create(
            name="장예은", employment_type="FULL_TIME", hourly_wage=10320
        )
        self.url = f"/api/payroll/employees/{self.employee.id}/"

    def test_update_employee_success(self):
        response = self.client.patch(self.url, {"hourly_wage": 11000}, format="json")

        self.assertEqual(response.status_code, 200)
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.hourly_wage, 11000)

    def test_update_nonexistent_employee_returns_404(self):
        response = self.client.patch(
            "/api/payroll/employees/9999/", {"hourly_wage": 11000}, format="json"
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "EMPLOYEE_NOT_FOUND")

    def test_delete_employee_success(self):
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Employee.objects.filter(id=self.employee.id).exists())

    def test_delete_nonexistent_employee_returns_404(self):
        response = self.client.delete("/api/payroll/employees/9999/")
        self.assertEqual(response.status_code, 404)