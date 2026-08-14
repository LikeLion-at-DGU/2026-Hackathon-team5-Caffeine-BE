from rest_framework import serializers

from businesses.models import Business

from .models import Transaction, TransactionDuplicate


class TransactionSyncRequestSerializer(serializers.Serializer):
    business_id = serializers.PrimaryKeyRelatedField(
        source="business",
        queryset=Business.objects.all(),
    )
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    sources = serializers.ListField(
        child=serializers.ChoiceField(choices=Transaction.SourceType.choices),
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


class TransactionSerializer(serializers.ModelSerializer):
    business_id = serializers.IntegerField()

    class Meta:
        model = Transaction
        fields = [
            "id",
            "business_id",
            "source_type",
            "external_id",
            "transaction_type",
            "transaction_date",
            "transaction_time",
            "merchant_name",
            "merchant_business_number",
            "supply_amount",
            "vat_amount",
            "total_amount",
            "approval_no",
            "cancel_status",
            "category",
            "classification_source",
            "classification_confidence",
            "raw_data",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TransactionCategoryUpdateSerializer(serializers.Serializer):
    category = serializers.ChoiceField(choices=Transaction.Category.choices)


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
