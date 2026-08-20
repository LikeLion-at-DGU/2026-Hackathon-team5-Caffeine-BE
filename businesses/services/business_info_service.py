from django.db import transaction

from integrations.codef.factory import get_codef_provider


class BusinessInfoSyncError(Exception):
    """CODEF 사업자 정보 동기화 실패."""


class BusinessInfoService:
    def sync(self, business):
        provider = get_codef_provider()

        result = provider.get_business_registration_info(
            business
        )

        if result["outcome"] != "SUCCESS":
            raise BusinessInfoSyncError(
                f"CODEF 응답 실패: "
                f"{result.get('error_code')!r} "
                f"{result.get('error_message')!r}"
            )

        industry_code = result.get(
            "industry_code",
            "",
        )

        business_type = result.get(
            "business_type",
            "",
        )

        business_item = result.get(
            "business_item",
            "",
        )

        if not industry_code:
            raise BusinessInfoSyncError(
                "CODEF 응답은 성공이지만 "
                "industry_code가 비어 있습니다."
            )

        with transaction.atomic():
            business.industry_code = industry_code
            business.business_type = business_type
            business.business_item = business_item

            business.save(
                update_fields=[
                    "industry_code",
                    "business_type",
                    "business_item",
                    "updated_at",
                ]
            )

        industry_name = " · ".join(
            value
            for value in [
                business.business_type,
                business.business_item,
            ]
            if value
        )
        return {
            "business_id": business.id,
            "industry_code": business.industry_code,
            "industry_name": industry_name,

            # 일단 API에는 같이 남겨도 됨
            "business_type": business.business_type,
            "business_item": business.business_item,
        }