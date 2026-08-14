from django.apps import apps

from payroll.exceptions import EmployeeAlreadyExists, EmployeeHasPayrollData, EmployeeNotFound
from payroll.models import Employee


def create_employee(validated_data: dict) -> Employee:
    # TODO(assumption): 중복 판단 기준이 명세서에 명시되지 않아 '동일 이름 존재'로 임시 정의.
    # 팀 확인 후 사업자번호/직원번호 등 다른 기준으로 바뀔 수 있음.
    if Employee.objects.filter(name=validated_data["name"]).exists():
        raise EmployeeAlreadyExists()

    rrn_front = validated_data.pop("rrn_front", "")
    employee = Employee(**validated_data)
    employee.set_rrn_front(rrn_front)
    employee.save()
    return employee


def list_employees():
    return Employee.objects.all().order_by("id")


def get_employee(employee_id: int) -> Employee:
    try:
        return Employee.objects.get(id=employee_id)
    except Employee.DoesNotExist:
        raise EmployeeNotFound()


def update_employee(employee_id: int, validated_data: dict) -> Employee:
    employee = get_employee(employee_id)
    for field, value in validated_data.items():
        setattr(employee, field, value)
    employee.save()
    return employee


def delete_employee(employee_id: int) -> None:
    employee = get_employee(employee_id)

    # Payment 모델이 아직 없는 시점에도 안전하게 동작하도록 동적으로 조회.
    # Payment 모델이 추가되면 이 코드 수정 없이 자동으로 검증이 걸림.
    try:
        Payment = apps.get_model("payroll", "Payment")
    except LookupError:
        Payment = None

    if Payment is not None and Payment.objects.filter(employee=employee).exists():
        raise EmployeeHasPayrollData()

    employee.delete()