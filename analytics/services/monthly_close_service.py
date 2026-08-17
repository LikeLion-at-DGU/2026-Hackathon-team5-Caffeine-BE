from analytics.exceptions import AlreadyClosed, CloseNotReady
from businesses.models import Business
from tax.models import MonthlyClose
from tax.services.closing_service import (
    MonthAlreadyClosed,
    MonthlyCloseService,
    UnconfirmedTransactionsExist,
)
from tax.services.vat_service import UnsupportedTaxType


def close_month(business_id: int, year: int, month: int) -> MonthlyClose:
    business = Business.objects.get(pk=business_id)
    try:
        MonthlyCloseService.approve(business=business, year=year, month=month)
    except MonthAlreadyClosed:
        raise AlreadyClosed()
    except (UnconfirmedTransactionsExist, UnsupportedTaxType) as exc:
        raise CloseNotReady() from exc
    return MonthlyClose.objects.get(business_id=business_id, year=year, month=month)


def is_month_closed(business_id: int, year: int, month: int) -> bool:
    return MonthlyClose.objects.filter(
        business_id=business_id,
        year=year,
        month=month,
        status=MonthlyClose.Status.CLOSED,
    ).exists()
