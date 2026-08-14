from payroll.exceptions import PayrollAlreadyExists, PaymentNotFound
from payroll.models import Employee, Payment
from payroll.services import employee_service
from payroll.services.employee_insurance_service import calculate_employee_insurance_breakdown
from payroll.services.employer_insurance_service import calculate_employer_insurance_total
from payroll.services.withholding_tax_service import (
    calculate_gross_pay,
    calculate_withholding_breakdown,
    calculate_withholding_tax,
)


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


def create_payment(business_id: int, employee_id: int, year: int, month: int, work_hours) -> Payment:
    employee = employee_service.get_employee(business_id, employee_id)  # 없으면 EmployeeNotFound 발생

    if Payment.objects.filter(employee=employee, year=year, month=month).exists():
        raise PayrollAlreadyExists()

    data = _calculate_and_build(employee, year, month, work_hours)
    payment = Payment.objects.create(employee=employee, **data)
    return payment


def update_payment(business_id: int, payment_id: int, work_hours) -> Payment:
    payment = get_payment(business_id, payment_id)
    data = _calculate_and_build(payment.employee, payment.year, payment.month, work_hours)

    payment.work_hours = data["work_hours"]
    payment.gross_pay = data["gross_pay"]
    payment.withholding_tax = data["withholding_tax"]
    payment.save()
    return payment


def get_payment(business_id: int, payment_id: int) -> Payment:
    try:
        return Payment.objects.get(id=payment_id, employee__business_id=business_id)
    except Payment.DoesNotExist:
        raise PaymentNotFound()


def list_payments(business_id: int, year: int | None = None, month: int | None = None):
    qs = Payment.objects.filter(employee__business_id=business_id).select_related("employee").order_by("employee_id")
    if year is not None:
        qs = qs.filter(year=year)
    if month is not None:
        qs = qs.filter(month=month)
    return qs


def get_monthly_summary(business_id: int, year: int, month: int) -> dict:
    payments = list_payments(business_id, year=year, month=month)
    total_labor_cost = 0
    total_withholding_tax = 0
    for payment in payments:
        total_labor_cost += payment.gross_pay
        total_labor_cost += calculate_employer_insurance_total(payment.employee, payment.gross_pay)
        total_withholding_tax += payment.withholding_tax

    return {
        "employee_count": payments.count(),
        "total_labor_cost": total_labor_cost,
        "withholding_tax": total_withholding_tax,
    }


def get_payslip_data(payment) -> dict:
    """임금명세서/지급명세서에 필요한 전체 데이터 (소득세/지방소득세/4대보험 항목별 분리 + 실수령액)."""
    employee = payment.employee
    breakdown = calculate_withholding_breakdown(employee.employment_type, payment.gross_pay)
    insurance = calculate_employee_insurance_breakdown(employee, payment.gross_pay)

    deductions_total = breakdown["total"] + insurance["total"]
    net_pay = payment.gross_pay - deductions_total

    return {
        "employee_id": employee.id,
        "employee_name": employee.name,
        "employment_type": employee.employment_type,
        "year": payment.year,
        "month": payment.month,
        "work_hours": payment.work_hours,
        "hourly_wage": employee.hourly_wage,
        "gross_pay": payment.gross_pay,
        "income_tax": breakdown["income_tax"],
        "local_income_tax": breakdown["local_income_tax"],
        "national_pension": insurance["national_pension"],
        "health_insurance": insurance["health_insurance"],
        "long_term_care": insurance["long_term_care"],
        "employment_insurance": insurance["employment_insurance"],
        "deductions_total": deductions_total,
        "net_pay": net_pay,
    }