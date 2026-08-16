from rest_framework import serializers

from businesses.models import Business
from transactions.serializers import TransactionSerializer

from .models import DeductionReview
from .services.periods import InvalidYearMonth, parse_year_month


class YearMonthField(serializers.CharField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            parse_year_month(value)
        except InvalidYearMonth as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value


class BusinessPeriodQuerySerializer(serializers.Serializer):
    business_id = serializers.PrimaryKeyRelatedField(
        source="business",
        queryset=Business.objects.all(),
    )
    year_month = YearMonthField()


class TaxBusinessScopeSerializer(serializers.Serializer):
    business_id = serializers.PrimaryKeyRelatedField(
        source="business",
        queryset=Business.objects.all(),
    )


class DeductionListQuerySerializer(BusinessPeriodQuerySerializer):
    suggested_status = serializers.ChoiceField(
        choices=DeductionReview.SuggestedStatus.choices,
        required=False,
    )
    confirmed_status = serializers.ChoiceField(
        choices=DeductionReview.ConfirmedStatus.choices,
        required=False,
    )
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)


class DeductionConfirmSerializer(serializers.Serializer):
    confirmed_status = serializers.ChoiceField(
        choices=[
            DeductionReview.ConfirmedStatus.DEDUCTIBLE,
            DeductionReview.ConfirmedStatus.NON_DEDUCTIBLE,
        ]
    )


class DeductionReviewSerializer(serializers.ModelSerializer):
    deduction_id = serializers.IntegerField(source="id", read_only=True)
    transaction = TransactionSerializer(read_only=True)
    suggestion = serializers.SerializerMethodField()
    confirmation = serializers.SerializerMethodField()

    class Meta:
        model = DeductionReview
        fields = ["deduction_id", "transaction", "suggestion", "confirmation", "updated_at"]

    @staticmethod
    def get_suggestion(obj):
        return {
            "status": obj.suggested_status,
            "label": obj.get_suggested_status_display(),
            "source": obj.suggestion_source,
            "reason": obj.suggestion_reason,
            "confidence": float(obj.confidence) if obj.confidence is not None else None,
        }

    @staticmethod
    def get_confirmation(obj):
        return {
            "status": obj.confirmed_status,
            "label": obj.get_confirmed_status_display(),
            "confirmed_at": obj.confirmed_at,
        }
