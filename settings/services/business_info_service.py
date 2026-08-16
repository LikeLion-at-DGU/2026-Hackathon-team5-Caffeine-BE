from businesses.models import Business
from settings.models import BusinessProfile


def _get_or_create_profile(business: Business) -> BusinessProfile:
    profile, _created = BusinessProfile.objects.get_or_create(business=business)
    return profile


def get_business_info(business_id: int) -> dict:
    business = Business.objects.get(id=business_id)  # 없으면 Business.DoesNotExist
    profile = _get_or_create_profile(business)

    return {
        "business_name": business.business_name,
        "representative_name": profile.representative_name,
        "business_number": business.business_number,
        "tax_type": business.tax_type,
        "industry_code": business.industry_code,
    }


def update_business_info(business_id: int, validated_data: dict) -> dict:
    business = Business.objects.get(id=business_id)
    profile = _get_or_create_profile(business)

    # representative_name만 우리 쪽 테이블 소유, 나머지는 businesses.Business 소유
    if "representative_name" in validated_data:
        profile.representative_name = validated_data.pop("representative_name")
        profile.save()

    for field, value in validated_data.items():
        setattr(business, field, value)
    if validated_data:
        business.save()

    return get_business_info(business_id)