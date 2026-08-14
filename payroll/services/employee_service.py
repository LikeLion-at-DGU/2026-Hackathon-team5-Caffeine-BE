from django.apps import apps

from payroll.exceptions import EmployeeAlreadyExists, EmployeeHasPayrollData, EmployeeNotFound
from payroll.models import Employee


def create_employee(business_id: int, validated_data: dict) -> Employee:
    # TODO(assumption): 중복 판단 기준이 명세서에 명시되지 않아 '동일 사업장 내 동일 이름 존재'로 임시 정의.
    if Employee.objects.filter(business_id=business_id, name=validated_data["name"]).exists():
        raise EmployeeAlreadyExists()

    rrn_front = validated_data.pop("rrn_front", "")
    employee = Employee(business_id=business_id, **validated_data)
    employee.set_rrn_front(rrn_front)
    employee.save()
    return employee


def list_employees(business_id: int):
    return Employee.objects.filter(business_id=business_id).order_by("id")


def get_employee(business_id: int, employee_id: int) -> Employee:
    try:
        return Employee.objects.get(id=employee_id, business_id=business_id)
    except Employee.DoesNotExist:
        raise EmployeeNotFound()


def update_employee(business_id: int, employee_id: int, validated_data: dict) -> Employee:
    employee = get_employee(business_id, employee_id)
    for field, value in validated_data.items():
        setattr(employee, field, value)
    employee.save()
    return employee


def delete_employee(business_id: int, employee_id: int) -> None:
    employee = get_employee(business_id, employee_id)

    try:
        Payment = apps.get_model("payroll", "Payment")
    except LookupError:
        Payment = None

    if Payment is not None and Payment.objects.filter(employee=employee).exists():
        raise EmployeeHasPayrollData()

    employee.delete()