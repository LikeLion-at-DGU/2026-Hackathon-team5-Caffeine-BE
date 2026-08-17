from django.test import SimpleTestCase

from core.responses import error_response, success_response


class CommonResponseTests(SimpleTestCase):
    def test_success_shape(self):
        response = success_response(code="DONE", message="완료", data={"id": 1})

        self.assertEqual(
            response.data,
            {"success": True, "code": "DONE", "message": "완료", "data": {"id": 1}},
        )

    def test_error_shape_always_has_errors_object(self):
        response = error_response(code="FAILED", message="실패")

        self.assertEqual(
            response.data,
            {"success": False, "code": "FAILED", "message": "실패", "errors": {}},
        )
