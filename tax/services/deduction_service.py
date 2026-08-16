from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone

from transactions.models import Transaction

from ..models import DeductionReview
from .querysets import effective_purchase_transactions


class DeductionReviewService:
    @staticmethod
    def _suggest(transaction):
        if transaction.expense_purpose == Transaction.ExpensePurpose.PERSONAL:
            return {
                "suggested_status": DeductionReview.SuggestedStatus.NON_DEDUCTIBLE_CANDIDATE,
                "suggestion_source": DeductionReview.SuggestionSource.RULE,
                "suggestion_reason": "개인 지출로 분류된 거래입니다.",
                "confidence": Decimal("1.0000"),
            }

        if transaction.source_deduction_status == Transaction.SourceDeductionStatus.DEDUCTIBLE:
            return {
                "suggested_status": DeductionReview.SuggestedStatus.DEDUCTIBLE_CANDIDATE,
                "suggestion_source": DeductionReview.SuggestionSource.CODEF,
                "suggestion_reason": "원본 거래 데이터에 공제 대상으로 표시되어 있습니다.",
                "confidence": Decimal("0.9500"),
            }

        if transaction.source_deduction_status == Transaction.SourceDeductionStatus.NON_DEDUCTIBLE:
            return {
                "suggested_status": DeductionReview.SuggestedStatus.NON_DEDUCTIBLE_CANDIDATE,
                "suggestion_source": DeductionReview.SuggestionSource.CODEF,
                "suggestion_reason": "원본 거래 데이터에 불공제 대상으로 표시되어 있습니다.",
                "confidence": Decimal("0.9500"),
            }

        return {
            "suggested_status": DeductionReview.SuggestedStatus.REVIEW_REQUIRED,
            "suggestion_source": DeductionReview.SuggestionSource.RULE,
            "suggestion_reason": "공제 여부를 확정할 원본 정보가 부족합니다.",
            "confidence": None,
        }

    @classmethod
    def get_or_create(cls, transaction):
        suggestion = cls._suggest(transaction)
        review, created = DeductionReview.objects.get_or_create(
            transaction=transaction,
            defaults=suggestion,
        )
        if not created and review.confirmed_status == DeductionReview.ConfirmedStatus.UNCONFIRMED:
            changed = any(getattr(review, key) != value for key, value in suggestion.items())
            if changed:
                for key, value in suggestion.items():
                    setattr(review, key, value)
                review.save(update_fields=[*suggestion.keys(), "updated_at"])
        return review

    @classmethod
    def ensure_for_queryset(cls, queryset):
        return [cls.get_or_create(item) for item in queryset]

    @classmethod
    @db_transaction.atomic
    def confirm(cls, *, review, confirmed_status):
        review = DeductionReview.objects.select_for_update().get(pk=review.pk)
        review.confirmed_status = confirmed_status
        review.confirmed_at = timezone.now()
        review.save(update_fields=["confirmed_status", "confirmed_at", "updated_at"])
        return review

    @classmethod
    def ensure_for_period(cls, *, business, start_date, end_date):
        queryset = effective_purchase_transactions(
            business=business,
            start_date=start_date,
            end_date=end_date,
        )
        cls.ensure_for_queryset(queryset)
        return queryset
