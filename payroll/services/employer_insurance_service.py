"""사업주 부담 4대보험료 계산.

세부 요율/가정은 payroll/services/insurance_common.py 참고.

- 국민연금/건강보험/장기요양: insurance_common의 공통 요율/상수 사용
- 고용보험: 실업급여 0.9% + 고용안정·직업능력개발사업 0.25%(150인 미만 사업장 기준) = 1.15% (사업주만 부담하는 항목이라 이 파일에 별도 정의)
- 산재보험: insurance_common의 INDUSTRIAL_ACCIDENT_RATE 사용, 전액 사업주 부담
"""

from payroll.services.insurance_common import (
    HEALTH_INSURANCE_RATE,
    INDUSTRIAL_ACCIDENT_RATE,
    LONG_TERM_CARE_RATE,
    NATIONAL_PENSION_CAP,
    NATIONAL_PENSION_FLOOR,
    NATIONAL_PENSION_RATE,
    has_worked_three_months_or_more,
    period_end_date,
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


def calculate_employer_insurance_total(employee, gross_pay: int, period_year: int, period_month: int) -> int:
    """직원 고용형태·근무기간에 따른 사업주 부담 4대보험료 합계.

    PART_TIME: 산재보험은 항상 포함. 고용보험은 근무시작일 기준 3개월 이상 경과 시에만 포함.
    국민연금(월소득 220만원 이상 시 가입)·건강보험(월 60시간 이상 시 가입) 조건은 미구현 —
    카페 인건비 규모에서 해당 가능성이 낮다고 판단해 범위에서 제외 (2026-08-13 팀 결정).
    """
    if employee.employment_type == "FREELANCER":
        return 0

    if employee.employment_type == "PART_TIME":
        total = calculate_industrial_accident_employer(gross_pay)

        reference_date = period_end_date(period_year, period_month)
        if has_worked_three_months_or_more(employee.work_started_at, reference_date):
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