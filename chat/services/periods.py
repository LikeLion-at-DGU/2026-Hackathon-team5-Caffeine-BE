import re


_YEAR_MONTH_PATTERN = re.compile(
    r"(?:(?P<year>20\d{2})\s*년\s*)?(?P<month>1[0-2]|0?[1-9])\s*월"
)


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def extract_requested_periods(
    message: str,
    *,
    default_year: int,
    default_month: int,
    max_periods: int = 6,
) -> list[tuple[int, int]]:
    """질문에 등장한 연월을 순서대로 추출한다.

    ``2025년 6월과 7월``처럼 뒤 월에 연도가 생략되면 앞에서 명시한
    연도를 이어받는다. 명시적 월이 없을 때는 지난달/이번달 표현을 처리한다.
    """
    periods = []
    inherited_year = default_year
    for match in _YEAR_MONTH_PATTERN.finditer(message or ""):
        if match.group("year"):
            inherited_year = int(match.group("year"))
        period = (inherited_year, int(match.group("month")))
        if period not in periods:
            periods.append(period)
        if len(periods) >= max_periods:
            return periods

    if periods:
        return periods

    normalized = (message or "").replace(" ", "")
    previous = _previous_month(default_year, default_month)
    mentions_previous = "지난달" in normalized or "저번달" in normalized
    mentions_current = "이번달" in normalized or "현재월" in normalized
    if mentions_previous and mentions_current:
        return [previous, (default_year, default_month)]
    if mentions_previous:
        return [previous]
    return [(default_year, default_month)]
