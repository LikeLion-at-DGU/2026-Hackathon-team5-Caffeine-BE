"""사업주/근로자 부담 4대보험료 계산에서 공통으로 쓰는 상수와 유틸.

출처(2026년 기준):
- 국민연금: 4.75%(각 부담), 기준소득월액 상한 6,370,000원 / 하한 400,000원
- 건강보험: 3.595%(각 부담)
- 장기요양보험: 건강보험(각 부담분) x 13.14%
- 산재보험: 0.8% (도소매·음식·숙박업, 전액 사업주 부담)

가정 (팀 확인 필요):
- 업종은 "도소매·음식·숙박업"으로 고정.
- 건강보험 상한액 미적용.
- PART_TIME의 국민연금(월소득 220만원↑ 가입)·건강보험(월60시간↑ 가입) 조건은 미구현.
"""

import calendar
from datetime import date

NATIONAL_PENSION_RATE = 0.0475
NATIONAL_PENSION_CAP = 6_370_000
NATIONAL_PENSION_FLOOR = 400_000

HEALTH_INSURANCE_RATE = 0.03595
LONG_TERM_CARE_RATE = 0.1314

INDUSTRIAL_ACCIDENT_RATE = 0.008  # 도소매·음식·숙박업, 전액 사업주 부담


def period_end_date(period_year: int, period_month: int) -> date:
    """급여 대상 월의 말일 — 고용보험 3개월 경과 여부 판정 기준일로 사용."""
    last_day = calendar.monthrange(period_year, period_month)[1]
    return date(period_year, period_month, last_day)


def has_worked_three_months_or_more(work_started_at: date | None, reference_date: date) -> bool:
    """근무시작일 기준 3개월 이상 경과했는지 판정.
    work_started_at이 없으면(미입력) 보수적으로 False 처리.
    """
    if work_started_at is None:
        return False

    year = work_started_at.year + (work_started_at.month - 1 + 3) // 12
    month = (work_started_at.month - 1 + 3) % 12 + 1
    day = min(work_started_at.day, calendar.monthrange(year, month)[1])
    three_months_later = date(year, month, day)

    return reference_date >= three_months_later