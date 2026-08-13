class PayrollServiceError(Exception):
    """payroll 서비스 레이어 공통 예외."""
    code = "PAYROLL_ERROR"
    message = "처리 중 오류가 발생했습니다."


class EmployeeNotFound(PayrollServiceError):
    code = "EMPLOYEE_NOT_FOUND"
    message = "직원을 찾을 수 없습니다."


class EmployeeAlreadyExists(PayrollServiceError):
    code = "EMPLOYEE_ALREADY_EXISTS"
    message = "이미 등록된 직원입니다."


class EmployeeHasPayrollData(PayrollServiceError):
    code = "EMPLOYEE_HAS_PAYROLL_DATA"
    message = "급여 기록이 존재하는 직원은 삭제할 수 없습니다."