"""사업장 기본정보 조회/수정.

2026-08-16: representative_name이 businesses.Business에 정식 필드로 추가되면서
(PR #18), settings 자체 임시 테이블(BusinessProfile)은 더 이상 쓰지 않음.
이제 businesses.Business를 그대로 읽고 쓴다 — settings는 businesses의 데이터를
감싸서 보여주는 역할만 함.
"""

from businesses.models import Business


def get_business_info(business_id: int) -> dict:
    business = Business.objects.get(id=business_id)  # 없으면 Business.DoesNotExist

    return {
        "business_name": business.business_name,
        "representative_name": business.representative_name,
        "business_number": business.business_number,
        "tax_type": business.tax_type,
        "industry_code": business.industry_code,
    }


def update_business_info(business_id: int, validated_data: dict) -> dict:
    business = Business.objects.get(id=business_id)

    for field, value in validated_data.items():
        setattr(business, field, value)
    if validated_data:
        business.save()

    return get_business_info(business_id)