import calendar
import re
from datetime import date


YEAR_MONTH_PATTERN = re.compile(r"^(?P<year>\d{4})-(?P<month>0[1-9]|1[0-2])$")


class InvalidYearMonth(ValueError):
    pass


def parse_year_month(value):
    match = YEAR_MONTH_PATTERN.fullmatch(value or "")
    if match is None:
        raise InvalidYearMonth("year_month는 YYYY-MM 형식이어야 합니다.")
    return int(match.group("year")), int(match.group("month"))


def month_range(year, month):
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
