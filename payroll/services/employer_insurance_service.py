"""사업주가 별도로 부담하는 4대보험료를 계산한다."""

from payroll.services.industrial_accident_rates import get_industrial_accident_rate
from payroll.services.insurance_common import (
    COMMUTE_ACCIDENT_RATE,
    HEALTH_INSURANCE_RATE,
    LONG_TERM_CARE_RATE,
    NATIONAL_PENSION_CAP,
    NATIONAL_PENSION_FLOOR,
    NATIONAL_PENSION_RATE,
)

EMPLOYMENT_INSURANCE_EMPLOYER_RATE = 0.009 + 0.0025  # 실업급여 + 고용안정·직업능력개발사업(150인 미만)


def calculate_national_pension_employer(gross_pay: int) -> int:
    base = max(min(gross_pay, NATIONAL_PENSION_CAP), NATIONAL_PENSION_FLOOR)
    return round(base * NATIONAL_PENSION_RATE)


def calculate_health_insurance_employer(gross_pay: int) -> int:
    return round(gross_pay * HEALTH_INSURANCE_RATE)


def calculate_long_term_care_employer(health_insurance_employer: int) -> int:
    return round(health_insurance_employer * LONG_TERM_CARE_RATE)


def calculate_employment_insurance_employer(gross_pay: int) -> int:
    return round(gross_pay * EMPLOYMENT_INSURANCE_EMPLOYER_RATE)


def calculate_industrial_accident_employer(gross_pay: int, business) -> int:
    """사업장별 산재 요율과 공통 출퇴근재해 요율을 적용한다."""
    rate = get_industrial_accident_rate(business) + COMMUTE_ACCIDENT_RATE
    return round(gross_pay * rate)


def calculate_employer_insurance_total(employee, gross_pay: int) -> int:
    """고용 형태와 계약 조건에 맞는 사업주 부담 보험료를 계산한다.

    단시간 근로자의 고용보험은 실제 경과 기간이 아니라 등록된 계약 기간을 기준으로
    적용한다. 산재보험은 계약 기간과 관계없이 사업주 부담에 포함한다.
    """
    if employee.employment_type == "FREELANCER":
        return 0

    if employee.employment_type == "PART_TIME":
        total = calculate_industrial_accident_employer(gross_pay, employee.business)
        if employee.is_long_term_contract:
            total += calculate_employment_insurance_employer(gross_pay)
        return total

    if employee.employment_type == "FULL_TIME":
        national_pension = calculate_national_pension_employer(gross_pay)
        health_insurance = calculate_health_insurance_employer(gross_pay)
        long_term_care = calculate_long_term_care_employer(health_insurance)
        employment_insurance = calculate_employment_insurance_employer(gross_pay)
        industrial_accident = calculate_industrial_accident_employer(gross_pay, employee.business)
        return national_pension + health_insurance + long_term_care + employment_insurance + industrial_accident

    raise ValueError(f"알 수 없는 employment_type: {employee.employment_type}")
