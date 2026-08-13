import bisect
import json
from decimal import Decimal
from pathlib import Path

MINOR_WITHHOLDING_THRESHOLD = 1000  # 소액부징수 기준: 세액 1,000원 미만이면 0원

# 근로소득 간이세액표(부양가족 1인), 2026-03-01 시행. 국세청 홈택스 공식 다운로드 파일 기준.
_TABLE_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "simplified_tax_table_family1.json"
_brackets_cache = None


def _load_brackets() -> list[dict]:
    global _brackets_cache
    if _brackets_cache is None:
        with open(_TABLE_PATH, encoding="utf-8") as f:
            _brackets_cache = json.load(f)
    return _brackets_cache


def _apply_minor_withholding(tax: int) -> int:
    return tax if tax >= MINOR_WITHHOLDING_THRESHOLD else 0

# 정확히 10,000,000원 지점의 세액 (구간이 아닌 단일 값). 원본 표 별도 행으로 명시됨. 1,000만원 초과 누진계산의 기준값(base)으로 사용.
TAX_AT_10_MILLION = 1_507_400


def calculate_freelancer_tax(gross_pay: int) -> int:
    """3.3% 프리랜서 원천세 (CONFIRMED: 소득세 3% + 지방소득세 0.3%)"""
    tax = round(gross_pay * 0.033)
    return _apply_minor_withholding(tax)


def calculate_simplified_tax_table(gross_pay: int) -> int:
    """간이세액표 기준 원천세 (부양가족 1인 고정 가정) — FULL_TIME, PART_TIME 공통 사용.

    출처: 국세청 홈택스 공식 근로소득 간이세액표, 2026-03-01 시행분.
    770,000원 미만은 표 자체에 구간이 없어 0원으로 처리.
    10,000,000원은 표에 별도 명시된 단일 값(TAX_AT_10_MILLION) 사용.
    10,000,000원 초과는 표에 명시된 누진 계산식 적용.
    """
    if gross_pay < 770_000:
        return 0

    brackets = _load_brackets()

    if gross_pay < brackets[-1]["lt"]:
        gte_list = [b["gte"] for b in brackets]
        idx = bisect.bisect_right(gte_list, gross_pay) - 1
        return _apply_minor_withholding(brackets[idx]["tax"])

    if gross_pay == 10_000_000:
        return _apply_minor_withholding(TAX_AT_10_MILLION)

    return _calculate_over_10m(gross_pay, base_tax=TAX_AT_10_MILLION)


def _calculate_over_10m(gross_pay: int, base_tax: int) -> int:
    """1,000만원 이상 구간. 표 하단에 명시된 누진 계산식을 그대로 구현.
    TODO: 우리 서비스 실사용 범위(카페 인건비)에서 나올 가능성이 매우 낮은 구간이라 우선순위 낮게 구현함.
    반올림 방식(원 단위 처리)은 표에 명시가 없어 round()로 가정 — 실사용 전 재검증 권장.
    """
    if gross_pay <= 14_000_000:
        tax = base_tax + round((gross_pay - 10_000_000) * 0.98 * 0.35) + 25_000
    elif gross_pay <= 28_000_000:
        tax = base_tax + 1_397_000 + round((gross_pay - 14_000_000) * 0.98 * 0.38)
    elif gross_pay <= 30_000_000:
        tax = base_tax + 6_610_600 + round((gross_pay - 28_000_000) * 0.98 * 0.40)
    elif gross_pay <= 45_000_000:
        tax = base_tax + 7_394_600 + round((gross_pay - 30_000_000) * 0.40)
    elif gross_pay <= 87_000_000:
        tax = base_tax + 13_394_600 + round((gross_pay - 45_000_000) * 0.42)
    else:
        tax = base_tax + 31_034_600 + round((gross_pay - 87_000_000) * 0.45)

    return _apply_minor_withholding(tax)


def calculate_withholding_tax(employment_type: str, gross_pay: int) -> int:
    """employment_type에 따라 원천세 계산 함수를 분기."""
    if employment_type == "FREELANCER":
        return calculate_freelancer_tax(gross_pay)
    elif employment_type in ("FULL_TIME", "PART_TIME"):
        return calculate_simplified_tax_table(gross_pay)
    raise ValueError(f"알 수 없는 employment_type: {employment_type}")


def calculate_gross_pay(hourly_wage: int, work_hours: Decimal) -> int:
    """시급 × 근무시간으로 세전 급여 계산."""
    return round(hourly_wage * float(work_hours))