from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from payroll.exceptions import PayrollServiceError
from payroll.serializers import EmployeeCreateSerializer, EmployeeListItemSerializer, EmployeeUpdateSerializer
from payroll.services import employee_service

from payroll.serializers import (
    EmployeeCreateSerializer, EmployeeListItemSerializer, EmployeeUpdateSerializer,
    PaymentCreateSerializer, PaymentListItemSerializer, PaymentUpdateSerializer,
)
from payroll.services import payment_service
from datetime import date


from django.http import HttpResponse
from payroll.services.payslip_pdf_service import generate_payslip_pdf
from payroll.services.payslip_xlsx_service import generate_payslip_xlsx


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

class PaymentListCreateView(APIView):
    def get(self, request):
        year = request.query_params.get("year")
        month = request.query_params.get("month")
        payments = payment_service.list_payments(
            year=int(year) if year else None,
            month=int(month) if month else None,
        )
        serializer = PaymentListItemSerializer(payments, many=True)
        return Response({
            "success": True,
            "code": "PAYROLL_LIST_SUCCESS",
            "message": "월별 급여 정보를 조회했습니다.",
            "data": serializer.data,
        })

    def post(self, request):
        serializer = PaymentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return _error_response(
                "INVALID_PAYROLL_DATA", "급여 정보가 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, serializer.errors,
            )
        try:
            payment = payment_service.create_payment(**serializer.validated_data)
        except PayrollServiceError as e:
            http_status = {
                "EMPLOYEE_NOT_FOUND": status.HTTP_404_NOT_FOUND,
                "PAYROLL_ALREADY_EXISTS": status.HTTP_409_CONFLICT,
                "WITHHOLDING_CALCULATION_NOT_READY": status.HTTP_501_NOT_IMPLEMENTED,
            }.get(e.code, status.HTTP_400_BAD_REQUEST)
            return _error_response(e.code, e.message, http_status)

        return Response({
            "success": True,
            "code": "PAYROLL_CREATE_SUCCESS",
            "message": "급여 정보를 등록했습니다.",
            "data": {
                "payment_id": payment.id,
                "work_hours": payment.work_hours,
                "gross_pay": payment.gross_pay,
                "withholding_tax": payment.withholding_tax,
            },
        }, status=status.HTTP_201_CREATED)


class PaymentDetailView(APIView):
    def patch(self, request, payment_id):
        serializer = PaymentUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return _error_response(
                "INVALID_PAYROLL_DATA", "급여 정보가 올바르지 않습니다.",
                status.HTTP_400_BAD_REQUEST, serializer.errors,
            )
        try:
            payment = payment_service.update_payment(payment_id, serializer.validated_data["work_hours"])
        except PayrollServiceError as e:
            http_status = {
                "PAYMENT_NOT_FOUND": status.HTTP_404_NOT_FOUND,
                "WITHHOLDING_CALCULATION_NOT_READY": status.HTTP_501_NOT_IMPLEMENTED,
            }.get(e.code, status.HTTP_400_BAD_REQUEST)
            return _error_response(e.code, e.message, http_status)

        return Response({
            "success": True,
            "code": "PAYROLL_UPDATE_SUCCESS",
            "message": "급여 정보를 수정했습니다.",
            "data": {
                "payment_id": payment.id,
                "work_hours": payment.work_hours,
                "gross_pay": payment.gross_pay,
                "withholding_tax": payment.withholding_tax,
            },
        })


class PayrollSummaryView(APIView):
    def get(self, request):
        year = request.query_params.get("year")
        month = request.query_params.get("month")
        if not year or not month:
            return _error_response(
                "INVALID_PERIOD", "조회 기간이 올바르지 않습니다.", status.HTTP_400_BAD_REQUEST
            )

        summary = payment_service.get_monthly_summary(int(year), int(month))

        # 원천세 납부 마감일: 익월 10일 (Figma "9월 10일 원천세 납부 예정" 예시와 일치)
        due_year, due_month = (int(year), int(month) + 1) if int(month) < 12 else (int(year) + 1, 1)
        payment_due_date = date(due_year, due_month, 10).isoformat()

        return Response({
            "success": True,
            "code": "PAYROLL_SUMMARY_SUCCESS",
            "message": "월별 노무 요약을 조회했습니다.",
            "data": {**summary, "payment_due_date": payment_due_date},
        })


class PaymentPayslipView(APIView):
    def get(self, request, payment_id):
        try:
            payment = payment_service.get_payment(payment_id)
        except PayrollServiceError as e:
            return _error_response(e.code, e.message, status.HTTP_404_NOT_FOUND)

        pdf_bytes = generate_payslip_pdf([payment])
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        filename = f"payslip_{payment.employee.name}_{payment.year}_{payment.month}.pdf"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class PaymentExportView(APIView):
    def post(self, request):
        year = request.data.get("year")
        month = request.data.get("month")
        export_format = request.data.get("format")

        if not year or not month or export_format not in ("pdf", "xlsx"):
            return _error_response(
                "INVALID_EXPORT_FORMAT", "지원하지 않는 파일 형식입니다.", status.HTTP_400_BAD_REQUEST
            )

        payments = payment_service.list_payments(year=int(year), month=int(month))
        if not payments.exists():
            return _error_response(
                "PAYROLL_DATA_NOT_FOUND", "해당 월의 급여 정보가 없습니다.", status.HTTP_404_NOT_FOUND
            )

        if export_format == "xlsx":
            xlsx_bytes = generate_payslip_xlsx(list(payments), int(year), int(month))
            response = HttpResponse(
                xlsx_bytes,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f'attachment; filename="payslip_{year}_{month}.xlsx"'
            return response

        pdf_bytes = generate_payslip_pdf(list(payments))
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="payslip_{year}_{month}.pdf"'
        return response