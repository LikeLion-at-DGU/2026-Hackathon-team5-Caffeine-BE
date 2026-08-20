from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN


ZERO = Decimal("0")
SPECIAL_RATE_NUMERATOR = Decimal("9")
SPECIAL_RATE_DENOMINATOR = Decimal("109")
SPECIAL_RATE_LABEL = "9/109"
SPECIAL_RATE_VALID_THROUGH = "2026-12-31"
LEGAL_BASIS = ["부가가치세법 제42조", "부가가치세법 시행령 제84조"]


@dataclass(frozen=True)
class DeemedPurchaseEstimate:
    candidate_amount: Decimal
    deduction: Decimal
    rate: str | None
    calculation_status: str
    assumptions: list[str]
    warnings: list[str]


def _is_food_service_business(business) -> bool:
    business_text = " ".join(
        filter(
            None,
            [
                getattr(business, "business_type", ""),
                getattr(business, "business_item", ""),
            ],
        )
    )
    return any(keyword in business_text for keyword in ("음식점", "커피", "카페", "음료"))


def estimate_deemed_purchase_deduction(*, business, candidate_amount, year: int) -> DeemedPurchaseEstimate:
    """면세 원재료 후보액에 대한 의제매입세액을 보수적으로 추정한다.

    현재 Business 모델에는 개인/법인 구분과 과세기간 과세표준 누계가 없다.
    따라서 2026년 음식점업 데모에 적용되는 9/109 특례율로 *추정액*만 계산하고,
    법정 공제한도와 최종 적격성은 적용하지 않았음을 응답 메타데이터에 명시한다.
    """
    amount = max(Decimal(candidate_amount or ZERO), ZERO)
    if amount == ZERO:
        return DeemedPurchaseEstimate(
            candidate_amount=ZERO,
            deduction=ZERO,
            rate=None,
            calculation_status="NO_CANDIDATE",
            assumptions=[],
            warnings=[],
        )

    if year != 2026 or not _is_food_service_business(business):
        return DeemedPurchaseEstimate(
            candidate_amount=amount,
            deduction=ZERO,
            rate=None,
            calculation_status="REVIEW_REQUIRED",
            assumptions=[],
            warnings=[
                "현재 자동 추정은 2026년 음식점업 사업장만 지원합니다. 사업자 유형과 적용 공제율을 확인해 주세요."
            ],
        )

    # 먼저 나눈 근사 Decimal을 곱하면 109,000원이 8,999원으로 잘릴 수 있다.
    # 분자 곱셈 후 분모로 나눠 법정 분수율을 그대로 유지한다.
    deduction = (amount * SPECIAL_RATE_NUMERATOR / SPECIAL_RATE_DENOMINATOR).quantize(
        Decimal("1"), rounding=ROUND_DOWN
    )
    return DeemedPurchaseEstimate(
        candidate_amount=amount,
        deduction=deduction,
        rate=SPECIAL_RATE_LABEL,
        calculation_status="PROVISIONAL_UNCAPPED",
        assumptions=[
            "음식점업을 경영하는 개인사업자",
            "해당 과세기간 과세표준 2억원 이하",
            "후보 거래가 실제 면세농산물등이며 과세 음식용역의 원재료로 사용됨",
        ],
        warnings=[
            "의제매입세액은 2026년 9/109 특례율을 적용한 추정액입니다.",
            "개인/법인 구분과 과세기간 과세표준 누계가 없어 법정 공제한도는 적용하지 않았습니다. 신고 전 적격 증빙과 한도를 확인해 주세요.",
        ],
    )
