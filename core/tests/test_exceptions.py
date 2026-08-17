from django.test import SimpleTestCase
from rest_framework.exceptions import MethodNotAllowed, NotFound, PermissionDenied, ValidationError

from core.exceptions import custom_exception_handler


class CustomExceptionHandlerTests(SimpleTestCase):
    def test_not_found_is_resource_neutral(self):
        response = custom_exception_handler(NotFound(), {})

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["code"], "NOT_FOUND")
        self.assertNotIn("사업장", response.data["message"])

    def test_validation_details_are_preserved(self):
        response = custom_exception_handler(ValidationError({"month": ["invalid"]}), {})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertIn("month", response.data["errors"])

    def test_permission_and_method_codes_are_distinct(self):
        permission = custom_exception_handler(PermissionDenied(), {})
        method = custom_exception_handler(MethodNotAllowed("TRACE"), {})

        self.assertEqual(permission.data["code"], "PERMISSION_DENIED")
        self.assertEqual(method.data["code"], "METHOD_NOT_ALLOWED")
