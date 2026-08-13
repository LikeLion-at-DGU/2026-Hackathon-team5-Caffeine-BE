from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from payroll.exceptions import PayrollServiceError
from payroll.serializers import EmployeeCreateSerializer, EmployeeListItemSerializer, EmployeeUpdateSerializer
from payroll.services import employee_service


def _error_response(code: str, message: str, http_status: int, errors: dict | None = None) -> Response:
    return Response(
        {"success": False, "code": code, "message": message, "errors": errors or {}},
        status=http_status,
    )


class EmployeeListCreateView(APIView):
    def get(self, request):
        employees = employee_service.list_employees()
        serializer = EmployeeListItemSerializer(employees, many=True)
        return Response({
            "success": True,
            "code": "EMPLOYEE_LIST_SUCCESS",
            "message": "직원 목록을 조회했습니다.",
            "data": serializer.data,
        })

    def post(self, request):
        serializer = EmployeeCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return _error_response(
                "INVALID_EMPLOYEE_DATA", "직원 정보가 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, serializer.errors,
            )
        try:
            employee = employee_service.create_employee(serializer.validated_data)
        except PayrollServiceError as e:
            return _error_response(e.code, e.message, status.HTTP_409_CONFLICT)

        return Response({
            "success": True,
            "code": "EMPLOYEE_CREATE_SUCCESS",
            "message": "직원을 등록했습니다.",
            "data": {"employee_id": employee.id},
        }, status=status.HTTP_201_CREATED)


class EmployeeDetailView(APIView):
    def patch(self, request, employee_id):
        serializer = EmployeeUpdateSerializer(data=request.data, partial=True)
        if not serializer.is_valid():
            return _error_response(
                "INVALID_EMPLOYEE_DATA", "직원 정보가 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, serializer.errors,
            )
        try:
            employee = employee_service.update_employee(employee_id, serializer.validated_data)
        except PayrollServiceError as e:
            return _error_response(e.code, e.message, status.HTTP_404_NOT_FOUND)

        return Response({
            "success": True,
            "code": "EMPLOYEE_UPDATE_SUCCESS",
            "message": "직원 정보를 수정했습니다.",
            "data": {"employee_id": employee.id},
        })

    def delete(self, request, employee_id):
        try:
            employee_service.delete_employee(employee_id)
        except PayrollServiceError as e:
            http_status = status.HTTP_404_NOT_FOUND if e.code == "EMPLOYEE_NOT_FOUND" else status.HTTP_409_CONFLICT
            return _error_response(e.code, e.message, http_status)

        return Response(status=status.HTTP_204_NO_CONTENT)