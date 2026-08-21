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
    industry_name = serializers.SerializerMethodField()

    def get_industry_name(self, obj):
        parts = [p for p in [obj.business_type, obj.business_item] if p]
        return " / ".join(parts) if parts else ""

    class Meta:
        model = Business
        fields = [
            "business_id",
            "business_name",
            "representative_name",
            "birth_date",
            "phone_number",
            "business_number",
            "industry_code",
            "business_type",
            "business_item",
            "industry_name",
            "business_status",
            "tax_type",
            "tax_type_code",
            "tax_type_changed_at",
            "is_demo",
        ]

        # 외부 조회로 동기화되는 값은 사용자 수정에서 제외한다.
        read_only_fields = [
            "industry_code",
            "business_type",
            "business_item",
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
    connection_type = serializers.ChoiceField(
        choices=[c[0] for c in CodefConnection.CONNECTION_TYPES]
    )
