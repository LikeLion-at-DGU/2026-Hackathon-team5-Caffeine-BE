from analytics.exceptions import AlreadyClosed
from analytics.models import MonthlyClose


def close_month(business_id: int, year: int, month: int) -> MonthlyClose:
    if MonthlyClose.objects.filter(business_id=business_id, year=year, month=month).exists():
        raise AlreadyClosed()

    return MonthlyClose.objects.create(business_id=business_id, year=year, month=month)


def is_month_closed(business_id: int, year: int, month: int) -> bool:
    return MonthlyClose.objects.filter(business_id=business_id, year=year, month=month).exists()