from django.db import transaction
from django.utils.dateparse import parse_date

from integrations.codef.factory import get_codef_provider
from businesses.models import TaxTypeHistory


# CODEF 과세유형 코드를 서비스 내부 값으로 변환
TAX_TYPE_MAP = {
    "1": "GENERAL",      # 일반과세자
    "2": "SIMPLE",       # 간이과세자
    "3": "EXEMPT",       # 면세사업자
    "6": "NONPROFIT",    # 비영리법인
    "90": "OTHER_CORP",  # 기타법인
}

# 사업자 상태 코드 변환
BUSINESS_STATUS_MAP = {
    "4": "CLOSED",         # 폐업자
    "5": "SUSPENDED",      # 휴업자
    "98": "NOT_BUSINESS",  # 미사업자
}


class CodefResponseError(Exception):
    """CODEF 응답을 정상적으로 처리할 수 없을 때 발생하는 예외."""


class TaxTypeService:
    def sync(self, business):
        """CODEF 사업자등록상태를 조회해 사업장의 과세유형 정보를 동기화한다."""
        provider = get_codef_provider()

        with transaction.atomic():
            result = provider.get_business_status(business.business_number)

            # CODEF 조회 실패 시 기존 사업장 정보는 변경하지 않는다.
            if result["outcome"] != "SUCCESS":
                raise CodefResponseError(
                    f"CODEF 응답 실패: "
                    f"{result.get('error_code')!r} "
                    f"{result.get('error_message')!r}"
                )

            # 요청한 사업자번호와 응답의 사업자번호가 일치하는지 확인한다.
            reported_id = result.get("company_identity_no")
            if (
                business.business_number
                and reported_id
                and reported_id != business.business_number
            ):
                raise CodefResponseError(
                    f"요청한 사업자번호({business.business_number})와 응답의 "
                    f"company_identity_no({reported_id})가 다릅니다."
                )

            old_code = business.tax_type_code
            new_code = result.get("taxation_type_code", "")

            # 과세유형 코드가 없으면 기존 값을 덮어쓰지 않고 동기화를 중단한다.
            if not new_code:
                raise CodefResponseError(
                    "CODEF 응답은 성공이지만 taxation_type_code가 비어 있어 "
                    "갱신을 건너뜁니다."
                )

            # 과세유형이 실제로 변경된 경우에만 변경 이력을 저장한다.
            if old_code and old_code != new_code:
                TaxTypeHistory.objects.create(
                    business=business,
                    before_code=old_code,
                    after_code=new_code,
                    effective_date=(
                        parse_date(result["transfer_tax_type_date"])
                        if result.get("transfer_tax_type_date")
                        else None
                    ),
                )

            business.tax_type_code = new_code

            # 매핑되지 않은 과세유형 코드는 UNKNOWN으로 저장한다.
            business.tax_type = TAX_TYPE_MAP.get(new_code, "UNKNOWN")

            # 상태 코드에 따라 사업자 상태를 갱신한다.
            business.business_status = BUSINESS_STATUS_MAP.get(
                new_code,
                "ACTIVE",
            )

            if result.get("transfer_tax_type_date"):
                business.tax_type_changed_date = parse_date(
                    result["transfer_tax_type_date"]
                )

            business.save()

        return {
            "business_id": business.id,
            "tax_type": business.tax_type,
            "tax_type_code": business.tax_type_code,
            "business_status": business.business_status,
            "tax_type_changed_date": business.tax_type_changed_date,
        }