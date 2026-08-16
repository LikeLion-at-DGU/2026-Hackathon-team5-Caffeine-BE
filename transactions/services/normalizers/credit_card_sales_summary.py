from transactions.models import MonthlySalesSummary
from transactions.services.types import NormalizedMonthlySalesSummary

from .helpers import (
    as_list,
    ensure_success,
    parse_decimal,
    parse_integer,
    parse_year_month,
)


def normalize_credit_card_sales_summaries(payload):
    ensure_success(payload)
    data = payload.get("data") or {}
    results = []

    for record in as_list(data.get("resSalesHistoryList")):
        year, month = parse_year_month(record.get("resYearMonth"))
        results.append(
            NormalizedMonthlySalesSummary(
                source_type=(
                    MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY
                ),
                year=year,
                month=month,
                transaction_count=parse_integer(record.get("resCount")),
                total_amount=parse_decimal(record.get("resTotalAmount")),
                raw_data=record,
            )
        )

    return results
