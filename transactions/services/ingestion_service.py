from collections.abc import Iterable

from django.db import transaction as db_transaction

from businesses.models import Business

from ..models import MonthlySalesSummary, Transaction
from .types import NormalizedMonthlySalesSummary, NormalizedTransaction


class TransactionIngestionService:
    """정규화가 끝난 거래를 재실행에 안전하게 저장한다."""

    @db_transaction.atomic
    def save(
        self,
        business: Business,
        normalized: NormalizedTransaction,
    ) -> tuple[Transaction, bool]:
        defaults = {
            "transaction_type": normalized.transaction_type,
            "transaction_date": normalized.transaction_date,
            "transaction_time": normalized.transaction_time,
            "merchant_name": normalized.merchant_name,
            "merchant_business_number": normalized.merchant_business_number,
            "supply_amount": normalized.supply_amount,
            "vat_amount": normalized.vat_amount,
            "total_amount": normalized.total_amount,
            "approval_no": normalized.approval_no,
            "cancel_status": normalized.cancel_status,
            "source_deduction_status": normalized.source_deduction_status,
            "raw_data": normalized.raw_data,
        }
        return Transaction.objects.update_or_create(
            business=business,
            source_type=normalized.source_type,
            external_id=normalized.external_id,
            defaults=defaults,
        )

    @db_transaction.atomic
    def save_many(
        self,
        business: Business,
        normalized_transactions: Iterable[NormalizedTransaction],
    ) -> list[tuple[Transaction, bool]]:
        return [self.save(business, item) for item in normalized_transactions]


class MonthlySalesSummaryIngestionService:
    @db_transaction.atomic
    def save(
        self,
        business: Business,
        normalized: NormalizedMonthlySalesSummary,
    ) -> tuple[MonthlySalesSummary, bool]:
        return MonthlySalesSummary.objects.update_or_create(
            business=business,
            source_type=normalized.source_type,
            year=normalized.year,
            month=normalized.month,
            defaults={
                "transaction_count": normalized.transaction_count,
                "total_amount": normalized.total_amount,
                "raw_data": normalized.raw_data,
            },
        )
