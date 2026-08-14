from decimal import Decimal

from django.db.models import Q

from ..models import Transaction, TransactionDuplicate


class DuplicateDetector:
    """서로 다른 source에서 들어온 동일 비용 후보를 보수적으로 찾는다."""

    BUSINESS_NUMBER_CONFIDENCE = Decimal("0.9500")
    MERCHANT_NAME_CONFIDENCE = Decimal("0.8000")

    def detect(self, transaction: Transaction) -> list[TransactionDuplicate]:
        if transaction.cancel_status == Transaction.CancelStatus.CANCELLED:
            return []

        candidates = Transaction.objects.filter(
            business=transaction.business,
            transaction_date=transaction.transaction_date,
            total_amount=transaction.total_amount,
        ).exclude(id=transaction.id).exclude(source_type=transaction.source_type)

        if transaction.merchant_business_number:
            candidates = candidates.filter(
                merchant_business_number=transaction.merchant_business_number
            )
            confidence = self.BUSINESS_NUMBER_CONFIDENCE
            matched_by = "merchant_business_number"
        elif transaction.merchant_name:
            candidates = candidates.filter(merchant_name__iexact=transaction.merchant_name)
            confidence = self.MERCHANT_NAME_CONFIDENCE
            matched_by = "merchant_name"
        else:
            return []

        results = []
        for candidate in candidates:
            existing = TransactionDuplicate.objects.filter(
                Q(primary_transaction=candidate, suspected_transaction=transaction)
                | Q(primary_transaction=transaction, suspected_transaction=candidate)
            ).first()
            if existing:
                results.append(existing)
                continue

            results.append(
                TransactionDuplicate.objects.create(
                    business=transaction.business,
                    primary_transaction=candidate,
                    suspected_transaction=transaction,
                    confidence=confidence,
                    detection_reason={
                        "matched_by": ["transaction_date", "total_amount", matched_by],
                        "source_types": [candidate.source_type, transaction.source_type],
                    },
                )
            )
        return results
