from decimal import Decimal

MINOR_WITHHOLDING_THRESHOLD = 1000  # 소액부징수 기준: 세액 1,000원 미만이면 0원


def calculate_freelancer_tax(gross_pay: int) -> int:
    """3.3% 프리랜서 원천세 (CONFIRMED: 소득세 3% + 지방소득세 0.3%)"""
    tax = round(gross_pay * 0.033)
    return tax if tax >= MINOR_WITHHOLDING_THRESHOLD else 0


def calculate_simplified_tax_table(gross_pay: int) -> int:
    """간이세액표 기준 원천세 — FULL_TIME, PART_TIME 공통 사용
    TODO: 국세청 공식 간이세액표(부양가족 1인) fixture 확보 후 구현
    """
    raise NotImplementedError("간이세액표 fixture 확보 후 구현 예정")


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