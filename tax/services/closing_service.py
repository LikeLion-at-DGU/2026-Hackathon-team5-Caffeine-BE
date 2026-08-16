from datetime import date, datetime
from decimal import Decimal

from django.db import transaction as db_transaction
from django.db.models import Count, Sum
from django.utils import timezone

from transactions.models import Transaction

from ..models import DeductionReview, MonthlyClose
from .deduction_service import DeductionReviewService
from .periods import month_range
from .querysets import effective_transactions
from .vat_service import VatForecastService


class MonthAlreadyClosed(Exception):
    pass


class UnconfirmedTransactionsExist(Exception):
    pass


def _snapshot_value(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _snapshot_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_snapshot_value(item) for item in value]
    return value


class MonthlyCloseService:
    @staticmethod
    def is_closed(*, business_id, transaction_date):
        return MonthlyClose.objects.filter(
            business_id=business_id,
            year=transaction_date.year,
            month=transaction_date.month,
            status=MonthlyClose.Status.CLOSED,
        ).exists()

    @staticmethod
    def has_closed_month_between(*, business_id, start_date, end_date):
        closed_periods = MonthlyClose.objects.filter(
            business_id=business_id,
            status=MonthlyClose.Status.CLOSED,
            year__gte=start_date.year,
            year__lte=end_date.year,
        ).values_list("year", "month")
        for year, month in closed_periods:
            month_start, month_end = month_range(year, month)
            if month_start <= end_date and month_end >= start_date:
                return True
        return False

    @classmethod
    def build_summary(cls, *, business, year, month):
        start_date, end_date = month_range(year, month)
        transactions = effective_transactions(
            business=business,
            start_date=start_date,
            end_date=end_date,
        )
        purchases = transactions.filter(transaction_type=Transaction.TransactionType.PURCHASE)
        DeductionReviewService.ensure_for_queryset(purchases)
        forecast = VatForecastService.calculate(business=business, year=year, month=month)

        source_breakdown = list(
            transactions.values("source_type", "transaction_type")
            .annotate(transaction_count=Count("id"), total_amount=Sum("total_amount"))
            .order_by("source_type", "transaction_type")
        )
        deduction_breakdown = list(
            DeductionReview.objects.filter(transaction__in=purchases)
            .values("confirmed_status")
            .annotate(transaction_count=Count("id"), vat_amount=Sum("transaction__vat_amount"))
            .order_by("confirmed_status")
        )
        existing = MonthlyClose.objects.filter(
            business=business,
            year=year,
            month=month,
        ).first()
        return {
            "business_id": business.id,
            "year_month": f"{year:04d}-{month:02d}",
            "status": existing.status if existing else MonthlyClose.Status.OPEN,
            "approved_at": existing.approved_at if existing else None,
            "forecast": forecast,
            "transaction_count": transactions.count(),
            "source_breakdown": source_breakdown,
            "deduction_breakdown": deduction_breakdown,
        }

    @classmethod
    @db_transaction.atomic
    def approve(cls, *, business, year, month):
        close, _ = MonthlyClose.objects.select_for_update().get_or_create(
            business=business,
            year=year,
            month=month,
        )
        if close.status == MonthlyClose.Status.CLOSED:
            raise MonthAlreadyClosed

        summary = cls.build_summary(business=business, year=year, month=month)
        forecast = summary["forecast"]
        if forecast["unconfirmed_transaction_count"]:
            raise UnconfirmedTransactionsExist

        close.status = MonthlyClose.Status.CLOSED
        close.sales_amount = forecast["sales_amount"]
        close.purchase_amount = forecast["purchase_amount"]
        close.output_vat = forecast["output_vat"]
        close.deductible_input_vat = forecast["deductible_input_vat"]
        close.estimated_vat = forecast["estimated_vat"]
        close.approved_at = timezone.now()
        summary["status"] = MonthlyClose.Status.CLOSED
        summary["approved_at"] = close.approved_at
        close.snapshot = _snapshot_value(summary)
        close.save()
        return close.snapshot
