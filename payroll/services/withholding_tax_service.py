import bisect
import json
from decimal import Decimal
from pathlib import Path

MINOR_WITHHOLDING_THRESHOLD = 1000  # 소액부징수 기준: 원천징수세액(소득세+지방소득세) 합계 1,000원 미만이면 0원

# 정확히 10,000,000원 지점의 소득세 (구간이 아닌 단일 값). 원본 표 별도 행으로 명시됨.
TAX_AT_10_MILLION = 1_507_400

_TABLE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "simplified_tax_table_family1.json"
_brackets_cache = None


def _load_brackets() -> list[dict]:
    global _brackets_cache
    if _brackets_cache is None:
        with open(_TABLE_PATH, encoding="utf-8") as f:
            _brackets_cache = json.load(f)
    return _brackets_cache


def _lookup_income_tax_from_table(gross_pay: int) -> int:
    """간이세액표(부양가족 1인)에서 소득세만 조회. 지방소득세 미포함, 소액부징수 미적용."""
    if gross_pay < 770_000:
        return 0

    brackets = _load_brackets()

    if gross_pay < brackets[-1]["lt"]:
        gte_list = [b["gte"] for b in brackets]
        idx = bisect.bisect_right(gte_list, gross_pay) - 1
        return brackets[idx]["tax"]

    if gross_pay == 10_000_000:
        return TAX_AT_10_MILLION

    return _calculate_income_tax_over_10m(gross_pay)


def _calculate_income_tax_over_10m(gross_pay: int) -> int:
    """1,000만원 초과 구간 소득세. 표 하단에 명시된 누진 계산식 그대로 구현.
    TODO: 카페 인건비 규모에서 나올 가능성이 매우 낮은 구간. 반올림 방식은 표에 명시 없어 round()로 가정.
    """
    base = TAX_AT_10_MILLION
    if gross_pay <= 14_000_000:
        return base + round((gross_pay - 10_000_000) * 0.98 * 0.35) + 25_000
    elif gross_pay <= 28_000_000:
        return base + 1_397_000 + round((gross_pay - 14_000_000) * 0.98 * 0.38)
    elif gross_pay <= 30_000_000:
        return base + 6_610_600 + round((gross_pay - 28_000_000) * 0.98 * 0.40)
    elif gross_pay <= 45_000_000:
        return base + 7_394_600 + round((gross_pay - 30_000_000) * 0.40)
    elif gross_pay <= 87_000_000:
        return base + 13_394_600 + round((gross_pay - 45_000_000) * 0.42)
    else:
        return base + 31_034_600 + round((gross_pay - 87_000_000) * 0.45)


def calculate_income_tax(employment_type: str, gross_pay: int) -> int:
    """소득세만 계산 (지방소득세 미포함, 소액부징수 미적용 — 순수 소득세 원본 값)."""
    if employment_type == "FREELANCER":
        return round(gross_pay * 0.03)
    elif employment_type in ("FULL_TIME", "PART_TIME"):
        return _lookup_income_tax_from_table(gross_pay)
    raise ValueError(f"알 수 없는 employment_type: {employment_type}")


def calculate_local_income_tax(income_tax: int) -> int:
    """지방소득세 = 소득세의 10%. 원단위 미만 버림 (통상 관행 가정)."""
    return income_tax // 10


def calculate_withholding_breakdown(employment_type: str, gross_pay: int) -> dict:
    """원천세를 소득세/지방소득세로 분리해서 반환.

    소액부징수(원천징수세액 1,000원 미만 시 미징수) 규칙:
    - FREELANCER(인적용역 사업소득): 2024.7.1. 지급분부터 소액부징수 적용 제외
      (국세청 확인, 계속적·반복적 인적용역 대가는 금액과 무관하게 항상 징수)
    - FULL_TIME/PART_TIME(근로소득, 간이세액표): 소득세(국세) 단독 1,000원 미만
      여부로 판정 — 지방소득세를 더한 합계 기준이 아님
    """
    income_tax = calculate_income_tax(employment_type, gross_pay)
    local_income_tax = calculate_local_income_tax(income_tax)

    if employment_type != "FREELANCER" and income_tax < MINOR_WITHHOLDING_THRESHOLD:
        return {"income_tax": 0, "local_income_tax": 0, "total": 0}

    return {"income_tax": income_tax, "local_income_tax": local_income_tax, "total": income_tax + local_income_tax}


def calculate_withholding_tax(employment_type: str, gross_pay: int) -> int:
    """원천세 합계(소득세+지방소득세)만 필요할 때 사용."""
    return calculate_withholding_breakdown(employment_type, gross_pay)["total"]


def calculate_freelancer_tax(gross_pay: int) -> int:
    """프리랜서 3.3% 원천세 (하위 호환용 wrapper)."""
    return calculate_withholding_tax("FREELANCER", gross_pay)


def calculate_gross_pay(hourly_wage: int, work_hours: Decimal) -> int:
    """시급 × 근무시간으로 세전 급여 계산."""
    return round(hourly_wage * float(work_hours))