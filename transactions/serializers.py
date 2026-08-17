from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

from businesses.models import Business

from .models import MonthlySalesSummary, Transaction, TransactionDuplicate


TRANSACTION_SYNC_SOURCE_CHOICES = [
    (Transaction.SourceType.CARD_PURCHASE, Transaction.SourceType.CARD_PURCHASE.label),
    (Transaction.SourceType.CASH_RECEIPT_SALE, Transaction.SourceType.CASH_RECEIPT_SALE.label),
    (Transaction.SourceType.TAX_INVOICE, Transaction.SourceType.TAX_INVOICE.label),
    (
        MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
        MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY.label,
    ),
]


class TransactionSyncRequestSerializer(serializers.Serializer):
    business_id = serializers.PrimaryKeyRelatedField(
        source="business",
        queryset=Business.objects.all(),
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    sources = serializers.ListField(
        child=serializers.ChoiceField(choices=TRANSACTION_SYNC_SOURCE_CHOICES),
        allow_empty=False,
    )

    def validate(self, attrs):
        if attrs["start_date"] > attrs["end_date"]:
            raise serializers.ValidationError({"end_date": "end_date는 start_date보다 빠를 수 없습니다."})
        return attrs

    def validate_sources(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("sources에는 같은 데이터 소스를 중복해서 넣을 수 없습니다.")
        return value


class TransactionListQuerySerializer(serializers.Serializer):
    business_id = serializers.PrimaryKeyRelatedField(
        source="business",
        queryset=Business.objects.all(),
    )
    start_date = serializers.DateField(required=False)
    end_date = serializers.DateField(required=False)
    transaction_type = serializers.ChoiceField(
        choices=Transaction.TransactionType.choices,
        required=False,
    )
    source_type = serializers.ChoiceField(choices=Transaction.SourceType.choices, required=False)
    category = serializers.ChoiceField(choices=Transaction.Category.choices, required=False)
    expense_purpose = serializers.ChoiceField(
        choices=Transaction.ExpensePurpose.choices,
        required=False,
    )
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)

    def validate(self, attrs):
        if attrs.get("start_date") and attrs.get("end_date"):
            if attrs["start_date"] > attrs["end_date"]:
                raise serializers.ValidationError(
                    {"end_date": "end_date는 start_date보다 빠를 수 없습니다."}
                )
        return attrs


class DuplicateListQuerySerializer(serializers.Serializer):
    business_id = serializers.PrimaryKeyRelatedField(
        source="business",
        queryset=Business.objects.all(),
    )
    status = serializers.ChoiceField(
        choices=TransactionDuplicate.Status.choices,
        default=TransactionDuplicate.Status.PENDING,
    )
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)


class BusinessScopeQuerySerializer(serializers.Serializer):
    business_id = serializers.PrimaryKeyRelatedField(
        source="business",
        queryset=Business.objects.all(),
    )


class TransactionSerializer(serializers.ModelSerializer):
    transaction_id = serializers.IntegerField(source="id", read_only=True)
    business_id = serializers.IntegerField()
    source = serializers.SerializerMethodField()
    date = serializers.DateField(source="transaction_date", read_only=True)
    time = serializers.TimeField(source="transaction_time", read_only=True, allow_null=True)
    category = serializers.SerializerMethodField()
    expense_purpose = serializers.SerializerMethodField()
    duplicate = serializers.SerializerMethodField()
    deduction = serializers.SerializerMethodField()
    is_deemed = serializers.SerializerMethodField()

    class Meta:
        model = Transaction
        fields = [
            "transaction_id",
            "business_id",
            "source",
            "source_type",
            "external_id",
            "transaction_type",
            "date",
            "time",
            "merchant_name",
            "merchant_business_number",
            "supply_amount",
            "vat_amount",
            "total_amount",
            "approval_no",
            "cancel_status",
            "category",
            "expense_purpose",
            "source_deduction_status",
            "duplicate",
            "deduction",
            "is_deemed",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    @staticmethod
    def get_source(obj):
        return {
            Transaction.SourceType.CARD_PURCHASE: "CARD",
            Transaction.SourceType.CASH_RECEIPT_PURCHASE: "CASH_RECEIPT",
            Transaction.SourceType.CASH_RECEIPT_SALE: "CASH_RECEIPT",
            Transaction.SourceType.TAX_INVOICE: "TAX_INVOICE",
        }.get(obj.source_type, obj.source_type)

    @staticmethod
    def get_category(obj):
        confidence = obj.classification_confidence
        return {
            "code": obj.category,
            "label": obj.get_category_display(),
            "source": obj.classification_source,
            "confidence": float(confidence) if confidence is not None else None,
        }

    @staticmethod
    def get_expense_purpose(obj):
        return {
            "code": obj.expense_purpose,
            "label": obj.get_expense_purpose_display(),
            "source": obj.expense_purpose_source,
        }

    @staticmethod
    def get_duplicate(obj):
        return {"is_suspected": bool(getattr(obj, "has_pending_duplicate", False))}

    @staticmethod
    def get_deduction(obj):
        try:
            review = obj.deduction_review
        except ObjectDoesNotExist:
            return {
                "status": "REVIEW_REQUIRED",
                "source": "RULE",
                "is_confirmed": False,
            }
        is_confirmed = review.confirmed_status != "UNCONFIRMED"
        return {
            "status": review.confirmed_status if is_confirmed else review.suggested_status,
            "source": "USER" if is_confirmed else review.suggestion_source,
            "is_confirmed": is_confirmed,
            "reason": review.suggestion_reason,
        }

    @staticmethod
    def get_is_deemed(obj):
        try:
            review = obj.deduction_review
        except ObjectDoesNotExist:
            return False
        return bool(
            obj.transaction_type == Transaction.TransactionType.PURCHASE
            and obj.expense_purpose == Transaction.ExpensePurpose.BUSINESS
            and obj.category == Transaction.Category.RAW_MATERIAL
            and obj.vat_amount == 0
            and review.confirmed_status == "DEDUCTIBLE"
        )


class TransactionCategoryUpdateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=Transaction.Category.choices)


class TransactionPurposeUpdateSerializer(serializers.Serializer):
    expense_purpose = serializers.ChoiceField(
        choices=[
            Transaction.ExpensePurpose.BUSINESS,
            Transaction.ExpensePurpose.PERSONAL,
            Transaction.ExpensePurpose.UNCLASSIFIED,
        ]
    )


class TransactionDuplicateSerializer(serializers.ModelSerializer):
    business_id = serializers.IntegerField()
    primary_transaction = TransactionSerializer(read_only=True)
    suspected_transaction = TransactionSerializer(read_only=True)

    class Meta:
        model = TransactionDuplicate
        fields = [
            "id",
            "business_id",
            "primary_transaction",
            "suspected_transaction",
            "status",
            "confidence",
            "detection_reason",
            "resolved_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class DuplicateResolutionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            TransactionDuplicate.Status.CONFIRMED,
            TransactionDuplicate.Status.DISMISSED,
        ]
    )
