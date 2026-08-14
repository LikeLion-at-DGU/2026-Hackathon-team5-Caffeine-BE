from rest_framework import serializers

from .models import Business, TaxTypeHistory, CodefConnection


class BusinessSerializer(serializers.ModelSerializer):
    class Meta:
        model = Business
        fields = [
            "id",
            "business_name",
            "business_number",
            "industry_code",
            "business_type",
            "business_item",
            "business_status",
            "tax_type",
            "tax_type_code",
            "tax_type_changed_date",
            "is_demo",
        ]

        # CODEF 또는 서버에서 관리하는 값은 사용자가 직접 수정하지 못하도록 설정
        read_only_fields = [
            "id",
            "business_status",
            "tax_type",
            "tax_type_code",
            "tax_type_changed_date",
            "is_demo",
        ]


class TaxTypeHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TaxTypeHistory

        # 사업장 정보는 URL로 식별되므로 변경 이력만 반환
        fields = [
            "id",
            "before_code",
            "after_code",
            "effective_date",
            "source",
            "created_at",
        ]
        
class CodefAuthRequestSerializer(serializers.Serializer):
    # 모델에 정의된 연결 유형(CARD/HOMETAX)만 허용한다.
    connection_type = serializers.ChoiceField(
        choices=[c[0] for c in CodefConnection.CONNECTION_TYPES]
    )