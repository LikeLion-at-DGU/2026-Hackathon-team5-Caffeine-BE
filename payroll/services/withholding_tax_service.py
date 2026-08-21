import bisect
import json
from decimal import Decimal
from pathlib import Path

# 근로소득 소득세가 기준 미만이면 원천징수하지 않는다.
MINOR_WITHHOLDING_THRESHOLD = 1000

# 간이세액표의 1,000만 원 경곗값을 초과 구간 계산의 기준으로 사용한다.
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
    """부양가족 1인 기준 간이세액표에서 소득세를 조회한다."""
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
    """간이세액표의 누진식으로 1,000만 원 초과 소득세를 계산한다.

    표에 별도 절사 규정이 없어 원 단위는 일반 반올림한다.
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
    """고용 형태별 소득세 원금액을 계산한다."""
    if employment_type == "FREELANCER":
        return round(gross_pay * 0.03)
    elif employment_type in ("FULL_TIME", "PART_TIME"):
        return _lookup_income_tax_from_table(gross_pay)
    raise ValueError(f"알 수 없는 employment_type: {employment_type}")


def calculate_local_income_tax(income_tax: int) -> int:
    """소득세의 10%를 원 단위 미만 절사해 지방소득세를 계산한다."""
    return income_tax // 10


def calculate_withholding_breakdown(employment_type: str, gross_pay: int) -> dict:
    """원천세를 소득세와 지방소득세로 나누어 반환한다.

    - 프리랜서: 인적용역 사업소득이므로 금액과 관계없이 징수
    - 근로자: 소득세가 1,000원 미만이면 소액부징수 적용
    """
    income_tax = calculate_income_tax(employment_type, gross_pay)
    local_income_tax = calculate_local_income_tax(income_tax)

    if employment_type != "FREELANCER" and income_tax < MINOR_WITHHOLDING_THRESHOLD:
        return {"income_tax": 0, "local_income_tax": 0, "total": 0}

    return {"income_tax": income_tax, "local_income_tax": local_income_tax, "total": income_tax + local_income_tax}


def calculate_withholding_tax(employment_type: str, gross_pay: int) -> int:
    """소득세와 지방소득세를 합한 원천세를 반환한다."""
    return calculate_withholding_breakdown(employment_type, gross_pay)["total"]


def calculate_freelancer_tax(gross_pay: int) -> int:
    """기존 호출부에서 사용하는 프리랜서 원천세 합계를 반환한다."""
    return calculate_withholding_tax("FREELANCER", gross_pay)


def calculate_gross_pay(hourly_wage: int, work_hours: Decimal) -> int:
    """시급과 근무시간으로 세전 급여를 계산한다."""
    return round(hourly_wage * float(work_hours))
