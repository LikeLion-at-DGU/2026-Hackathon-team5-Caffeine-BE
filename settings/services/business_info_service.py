"""설정 화면에서 사용하는 사업장 기본 정보 조회·수정 서비스.

사업장 정보의 원본은 `businesses.Business`로 유지하고, 이 모듈은 설정 화면에
필요한 필드만 전달한다.
"""

from businesses.models import Business


def get_business_info(business_id: int) -> dict:
    """설정 화면에 표시할 사업장 정보를 반환한다.

    Args:
        business_id: 조회할 사업장 ID.

    Returns:
        설정 화면에서 사용하는 사업장 정보.
    """
    business = Business.objects.get(id=business_id)  # 없으면 Business.DoesNotExist

    return {
        "business_name": business.business_name,
        "representative_name": business.representative_name,
        "birth_date": business.birth_date,
        "phone_number": business.phone_number,
        "business_number": business.business_number,
        "tax_type": business.tax_type,
        "industry_code": business.industry_code,
        # 업태와 종목은 의미가 달라 화면에서 필요한 방식으로 조합하도록 분리한다.
        "business_type": business.business_type,
        "business_item": business.business_item,
    }


def update_business_info(business_id: int, validated_data: dict) -> dict:
    """검증된 값으로 사업장 정보를 갱신한다.

    Args:
        business_id: 수정할 사업장 ID.
        validated_data: 저장할 검증 완료 필드.

    Returns:
        갱신된 사업장 정보.
    """
    business = Business.objects.get(id=business_id)

    for field, value in validated_data.items():
        setattr(business, field, value)
    if validated_data:
        business.save()

    return get_business_info(business_id)
