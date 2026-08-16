from rest_framework import serializers

from .models import Business, TaxTypeHistory, CodefConnection


class BusinessSerializer(serializers.ModelSerializer):
    business_id = serializers.IntegerField(
        source="id",
        read_only=True,
    )
    tax_type_changed_at = serializers.DateField(
        source="tax_type_changed_date",
        read_only=True,
    )

    class Meta:
        model = Business
        fields = [
            "business_id",
            "business_name",
            "representative_name",
            "business_number",
            "industry_code",
            "business_type",
            "business_item",
            "business_status",
            "tax_type",
            "tax_type_code",
            "tax_type_changed_at",
            "is_demo",
        ]

        # CODEF 또는 서버에서 관리하는 필드는 수정 불가
        read_only_fields = [
            "business_status",
            "tax_type",
            "tax_type_code",
            "is_demo",
        ]


class TaxTypeHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxTypeHistory
        fields = [
            "id",
            "before_code",
            "after_code",
            "effective_date",
            "source",
            "created_at",
        ]


class CodefAuthRequestSerializer(serializers.Serializer):
    # CARD / HOMETAX만 허용
    connection_type = serializers.ChoiceField(
        choices=[c[0] for c in CodefConnection.CONNECTION_TYPES]
    )