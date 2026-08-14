"""사업주 부담 4대보험료 계산.

세부 요율/가정은 payroll/services/insurance_common.py 참고.
"""

from payroll.services.insurance_common import (
    HEALTH_INSURANCE_RATE,
    INDUSTRIAL_ACCIDENT_RATE,
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


def calculate_industrial_accident_employer(gross_pay: int) -> int:
    return round(gross_pay * INDUSTRIAL_ACCIDENT_RATE)


def calculate_employer_insurance_total(employee, gross_pay: int) -> int:
    """직원 고용형태·계약조건에 따른 사업주 부담 4대보험료 합계.

    PART_TIME: 산재보험은 항상 포함. 고용보험은 근로계약이 3개월 이상(또는 무기한)으로
    등록된 경우에만 포함 — '실제 경과시간'이 아니라 '계약 조건' 기준 (2026-08-14 수정).
    법적 근거: 고용보험법 시행령 제3조 관련 유권해석 — "3개월 이상 계속근로"는 실근무기간이
    아니라 근로계약 기간을 기준으로 판단하며, 요건 충족 시 최초 근무일부터 소급 적용됨.
    국민연금(월소득 220만원 이상 시 가입)·건강보험(월 60시간 이상 시 가입) 조건은 미구현.
    """
    if employee.employment_type == "FREELANCER":
        return 0

    if employee.employment_type == "PART_TIME":
        total = calculate_industrial_accident_employer(gross_pay)
        if employee.is_long_term_contract:
            total += calculate_employment_insurance_employer(gross_pay)
        return total

    if employee.employment_type == "FULL_TIME":
        national_pension = calculate_national_pension_employer(gross_pay)
        health_insurance = calculate_health_insurance_employer(gross_pay)
        long_term_care = calculate_long_term_care_employer(health_insurance)
        employment_insurance = calculate_employment_insurance_employer(gross_pay)
        industrial_accident = calculate_industrial_accident_employer(gross_pay)
        return national_pension + health_insurance + long_term_care + employment_insurance + industrial_accident

    raise ValueError(f"알 수 없는 employment_type: {employee.employment_type}")