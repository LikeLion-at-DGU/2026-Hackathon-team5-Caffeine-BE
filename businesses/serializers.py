from rest_framework import serializers

from .models import Business


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

        # 조회만 가능하고 사용자가 직접 수정할 수 없는 필드
        # - business_status, tax_type 관련 값: CODEF 동기화 API에서만 변경
        # - is_demo: 서버에서 관리하는 값
        # - id: 자동 생성되는 식별자
        read_only_fields = [
            "id",
            "business_status",
            "tax_type",
            "tax_type_code",
            "tax_type_changed_date",
            "is_demo",
        ]