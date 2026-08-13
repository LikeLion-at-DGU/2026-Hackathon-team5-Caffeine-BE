import calendar
from datetime import date

"""사업주 부담 4대보험료 계산.

출처(2026년 기준):
- 국민연금: 4.75% (사업주분), 기준소득월액 상한 6,370,000원 / 하한 400,000원
- 건강보험: 3.595% (사업주분)
- 장기요양보험: 건강보험(사업주분) x 13.14%
- 고용보험: 실업급여 0.9% + 고용안정·직업능력개발사업 0.25%(150인 미만 사업장 기준) = 1.15%
- 산재보험: 0.8% (도소매·음식·숙박업 기준, 전액 사업주 부담)

주의 (하드코딩 가정 — 팀 확인 필요):
- 업종은 "도소매·음식·숙박업"으로 고정. 실제로는 Business.business_type/business_item에
  따라 근로복지공단이 다른 사업종류 코드를 부여할 수 있음 (TODO: Business 연동 후 동적 적용).
- 건강보험은 상한액 미적용 (상한액이 매우 높아 카페 인건비 규모에서 도달 가능성 낮다고 판단).
- PART_TIME(초단시간근로자)의 고용보험(3개월 이상 근로 시 가입)·국민연금(월소득 220만원 이상 시
  가입) 예외조건은 미구현 — 우리 서비스에 근속기간 추적 필드가 없어 범위 밖으로 판단.
  법적으로는 조건 충족 시 추가 부담이 발생할 수 있음.
"""

NATIONAL_PENSION_RATE = 0.0475
NATIONAL_PENSION_CAP = 6_370_000
NATIONAL_PENSION_FLOOR = 400_000

HEALTH_INSURANCE_RATE = 0.03595
LONG_TERM_CARE_RATE = 0.1314  # 건강보험(사업주분)에 곱함

EMPLOYMENT_INSURANCE_RATE = 0.009 + 0.0025  # 실업급여 + 고용안정·직업능력개발사업(150인 미만)

INDUSTRIAL_ACCIDENT_RATE = 0.008  # 도소매·음식·숙박업


def calculate_national_pension_employer(gross_pay: int) -> int:
    base = max(min(gross_pay, NATIONAL_PENSION_CAP), NATIONAL_PENSION_FLOOR)
    return round(base * NATIONAL_PENSION_RATE)


def calculate_health_insurance_employer(gross_pay: int) -> int:
    return round(gross_pay * HEALTH_INSURANCE_RATE)


def calculate_long_term_care_employer(health_insurance_employer: int) -> int:
    return round(health_insurance_employer * LONG_TERM_CARE_RATE)


def calculate_employment_insurance_employer(gross_pay: int) -> int:
    return round(gross_pay * EMPLOYMENT_INSURANCE_RATE)


def calculate_industrial_accident_employer(gross_pay: int) -> int:
    return round(gross_pay * INDUSTRIAL_ACCIDENT_RATE)


def _period_end_date(period_year: int, period_month: int) -> date:
    """급여 대상 월의 말일 — 고용보험 3개월 경과 여부 판정 기준일로 사용."""
    last_day = calendar.monthrange(period_year, period_month)[1]
    return date(period_year, period_month, last_day)


def _has_worked_three_months_or_more(work_started_at: date | None, reference_date: date) -> bool:
    """근무시작일 기준 3개월 이상 경과했는지 판정.
    work_started_at이 없으면(미입력) 보수적으로 False 처리 — 데이터 없이 고용보험을 부과하지 않음.
    """
    if work_started_at is None:
        return False

    year = work_started_at.year + (work_started_at.month - 1 + 3) // 12
    month = (work_started_at.month - 1 + 3) % 12 + 1
    day = min(work_started_at.day, calendar.monthrange(year, month)[1])
    three_months_later = date(year, month, day)

    return reference_date >= three_months_later


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

        reference_date = _period_end_date(period_year, period_month)
        if _has_worked_three_months_or_more(employee.work_started_at, reference_date):
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