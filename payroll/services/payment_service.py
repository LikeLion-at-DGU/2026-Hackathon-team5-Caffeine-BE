from payroll.exceptions import PayrollAlreadyExists, PaymentNotFound, WithholdingCalculationNotReady
from payroll.models import Employee, Payment
from payroll.services import employee_service
from payroll.services.withholding_tax_service import calculate_gross_pay, calculate_withholding_tax


def _calculate_and_build(employee: Employee, year: int, month: int, work_hours) -> dict:
    gross_pay = calculate_gross_pay(employee.hourly_wage, work_hours)
    withholding_tax = calculate_withholding_tax(employee.employment_type, gross_pay)

    return {
        "year": year,
        "month": month,
        "work_hours": work_hours,
        "gross_pay": gross_pay,
        "withholding_tax": withholding_tax,
    }


def create_payment(employee_id: int, year: int, month: int, work_hours) -> Payment:
    employee = employee_service.get_employee(employee_id)  # 없으면 EmployeeNotFound 발생

    if Payment.objects.filter(employee=employee, year=year, month=month).exists():
        raise PayrollAlreadyExists()

    data = _calculate_and_build(employee, year, month, work_hours)
    payment = Payment.objects.create(employee=employee, **data)
    return payment


def update_payment(payment_id: int, work_hours) -> Payment:
    payment = get_payment(payment_id)
    data = _calculate_and_build(payment.employee, payment.year, payment.month, work_hours)

    payment.work_hours = data["work_hours"]
    payment.gross_pay = data["gross_pay"]
    payment.withholding_tax = data["withholding_tax"]
    payment.save()
    return payment


def get_payment(payment_id: int) -> Payment:
    try:
        return Payment.objects.get(id=payment_id)
    except Payment.DoesNotExist:
        raise PaymentNotFound()


def list_payments(year: int | None = None, month: int | None = None):
    qs = Payment.objects.select_related("employee").order_by("employee_id")
    if year is not None:
        qs = qs.filter(year=year)
    if month is not None:
        qs = qs.filter(month=month)
    return qs