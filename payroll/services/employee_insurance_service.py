"""근로자 부담 4대보험료 계산.

사업주 부담(employer_insurance_service.py)과 요율은 대부분 동일하나:
- 국민연금/건강보험/장기요양: 노사 50:50이라 요율 동일 (4.75% / 3.595% / 13.14%)
- 고용보험: 근로자는 실업급여분(0.9%)만 부담. 고용안정·직업능력개발사업(0.25%)은 사업주 전액 부담이라 근로자 부담 없음
- 산재보험: 전액 사업주 부담 — 근로자는 한 푼도 안 냄

PART_TIME 고용보험 3개월 판정 로직은 사업주 부담과 동일하게 적용.
"""

import calendar
from datetime import date

from payroll.services.insurance_common import (
    HEALTH_INSURANCE_RATE,
    LONG_TERM_CARE_RATE,
    NATIONAL_PENSION_CAP,
    NATIONAL_PENSION_FLOOR,
    NATIONAL_PENSION_RATE,
)
EMPLOYMENT_INSURANCE_EMPLOYEE_RATE = 0.009  # 실업급여분만 (고용안정·직업능력개발사업 제외)


def calculate_national_pension_employee(gross_pay: int) -> int:
    base = max(min(gross_pay, NATIONAL_PENSION_CAP), NATIONAL_PENSION_FLOOR)
    return round(base * NATIONAL_PENSION_RATE)


def calculate_health_insurance_employee(gross_pay: int) -> int:
    return round(gross_pay * HEALTH_INSURANCE_RATE)


def calculate_long_term_care_employee(health_insurance_employee: int) -> int:
    return round(health_insurance_employee * LONG_TERM_CARE_RATE)


def calculate_employment_insurance_employee(gross_pay: int) -> int:
    return round(gross_pay * EMPLOYMENT_INSURANCE_EMPLOYEE_RATE)


def calculate_employee_insurance_breakdown(employee, gross_pay: int) -> dict:
    """근로자 부담 4대보험료를 항목별로 분리해서 반환 (임금명세서 공제 항목용)."""
    if employee.employment_type == "FREELANCER":
        return {"national_pension": 0, "health_insurance": 0, "long_term_care": 0, "employment_insurance": 0, "total": 0}

    if employee.employment_type == "PART_TIME":
        employment_insurance = calculate_employment_insurance_employee(gross_pay) if employee.is_long_term_contract else 0
        return {
            "national_pension": 0, "health_insurance": 0, "long_term_care": 0,
            "employment_insurance": employment_insurance, "total": employment_insurance,
        }

    if employee.employment_type == "FULL_TIME":
        national_pension = calculate_national_pension_employee(gross_pay)
        health_insurance = calculate_health_insurance_employee(gross_pay)
        long_term_care = calculate_long_term_care_employee(health_insurance)
        employment_insurance = calculate_employment_insurance_employee(gross_pay)
        total = national_pension + health_insurance + long_term_care + employment_insurance
        return {
            "national_pension": national_pension, "health_insurance": health_insurance,
            "long_term_care": long_term_care, "employment_insurance": employment_insurance, "total": total,
        }

    raise ValueError(f"알 수 없는 employment_type: {employee.employment_type}")