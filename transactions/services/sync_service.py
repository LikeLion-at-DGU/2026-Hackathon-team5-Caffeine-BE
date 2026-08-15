from collections import Counter

from django.db import transaction as db_transaction

from integrations.codef.factory import get_codef_provider
from transactions.models import Transaction, TransactionDuplicate

from .classifier import RuleBasedTransactionClassifier
from .duplicate_detector import DuplicateDetector
from .ingestion_service import TransactionIngestionService
from .normalizers import (
    normalize_business_card_purchases,
    normalize_cash_receipt_sales,
    normalize_tax_invoices,
)
from .normalizers.helpers import normalized_business_number


class TransactionSourceMismatchError(ValueError):
    pass


class TransactionSyncService:
    SUPPORTED_SOURCES = (
        Transaction.SourceType.CARD_PURCHASE,
        Transaction.SourceType.CASH_RECEIPT_SALE,
        Transaction.SourceType.TAX_INVOICE,
    )

    def __init__(self, provider=None):
        self.provider = provider or get_codef_provider()
        self.ingestion = TransactionIngestionService()
        self.classifier = RuleBasedTransactionClassifier()
        self.duplicate_detector = DuplicateDetector()

    @db_transaction.atomic
    def sync(self, business, start_date, end_date, sources):
        total_created = 0
        total_updated = 0
        skipped_outside_period = 0
        source_results = []
        category_counts = Counter()
        duplicates_before = TransactionDuplicate.objects.filter(business=business).count()

        for source in sources:
            normalized_items = self._fetch_and_normalize(
                source,
                business,
                start_date,
                end_date,
            )
            self._validate_business_ownership(business, normalized_items)
            in_period = [
                item
                for item in normalized_items
                if start_date <= item.transaction_date <= end_date
            ]
            skipped_outside_period += len(normalized_items) - len(in_period)
            source_created = 0
            source_updated = 0

            for normalized in in_period:
                saved, created = self.ingestion.save(business, normalized)
                self._apply_classification(saved, normalized)
                self.duplicate_detector.detect(saved)
                category_counts[saved.category] += 1
                if created:
                    source_created += 1
                else:
                    source_updated += 1

            total_created += source_created
            total_updated += source_updated
            source_results.append(
                {
                    "source_type": source,
                    "fetched_count": len(normalized_items),
                    "in_period_count": len(in_period),
                    "created_count": source_created,
                    "updated_count": source_updated,
                }
            )

        duplicates_after = TransactionDuplicate.objects.filter(business=business).count()
        return {
            "business_id": business.id,
            "period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "source_results": source_results,
            "created_count": total_created,
            "updated_count": total_updated,
            "skipped_outside_period_count": skipped_outside_period,
            "new_duplicate_candidate_count": max(0, duplicates_after - duplicates_before),
            "duplicate_candidate_total_count": duplicates_after,
            "category_counts": dict(category_counts),
        }

    def _fetch_and_normalize(self, source, business, start_date, end_date):
        if source == Transaction.SourceType.CARD_PURCHASE:
            payload = self.provider.get_business_card_purchases(
                business,
                start_date,
                end_date,
            )
            return normalize_business_card_purchases(payload)

        if source == Transaction.SourceType.CASH_RECEIPT_SALE:
            payload = self.provider.get_cash_receipt_sales(
                business,
                start_date,
                end_date,
            )
            return normalize_cash_receipt_sales(payload)

        if source == Transaction.SourceType.TAX_INVOICE:
            purchases = self.provider.get_tax_invoice_purchases(
                business,
                start_date,
                end_date,
            )
            sales = self.provider.get_tax_invoice_sales(
                business,
                start_date,
                end_date,
            )
            return [
                *normalize_tax_invoices(
                    purchases,
                    Transaction.TransactionType.PURCHASE,
                ),
                *normalize_tax_invoices(
                    sales,
                    Transaction.TransactionType.SALE,
                ),
            ]

        raise ValueError(f"지원하지 않는 거래 동기화 소스입니다: {source}")

    @staticmethod
    def _validate_business_ownership(business, normalized_items):
        expected = normalized_business_number(business.business_number)
        if not expected:
            return

        mismatched = {
            item.owner_business_number
            for item in normalized_items
            if item.owner_business_number and item.owner_business_number != expected
        }
        if mismatched:
            raise TransactionSourceMismatchError(
                "요청한 사업자번호와 CODEF 거래 원본의 사업자번호가 일치하지 않습니다."
            )

    def _apply_classification(self, transaction, normalized):
        if transaction.classification_source == Transaction.ClassificationSource.USER:
            return

        result = self.classifier.classify(normalized)
        transaction.category = result.category
        transaction.classification_source = result.source
        transaction.classification_confidence = result.confidence
        transaction.save(
            update_fields=[
                "category",
                "classification_source",
                "classification_confidence",
                "updated_at",
            ]
        )
