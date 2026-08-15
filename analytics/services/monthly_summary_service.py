"""월별 세무 현황 결산 조합 서비스.

원칙: analytics는 계산하지 않는다. 각 앱(payroll/transactions/tax)의 결과를
그대로 참조해서 조합만 한다. 같은 값을 analytics에서 다시 계산하면 두 곳의
숫자가 어긋날 위험이 있기 때문이다.

지금은 payroll만 완성되어 있어서, 인건비/원천세 항목만 채우고 나머지는
transactions/tax 완료 시점에 이어서 채운다 (아래 TODO 참고).
"""

from payroll.services.payment_service import get_monthly_summary as get_payroll_summary


def get_monthly_tax_summary(business_id: int, year: int, month: int) -> dict:
    payroll_summary = get_payroll_summary(business_id, year, month)

    expense_breakdown = [
        {
            "category": "인건비",
            "amount": payroll_summary["total_labor_cost"],
            "ratio": None,  # 전체 지출 대비 비율 — transactions 완료 후 계산 가능
        },
        # TODO: transactions 완료되면 재료비/임차료·관리비/기타경비 항목 추가
    ]

    return {
        "year": year,
        "month": month,
        # TODO: tax 완료되면 채움
        "vat_reserve_amount": None,
        "vat_breakdown": None,
        "vat_filing_due_date": None,
        "tax_type": None,
        # TODO: transactions 완료되면 채움
        "total_sales": None,
        "total_expense": None,
        "net_profit": None,
        "profit_margin": None,
        "expense_breakdown": expense_breakdown,
        # payroll 참조로 지금 확실히 채울 수 있는 값
        "payroll_withholding_tax": payroll_summary["withholding_tax"],
        "payroll_employee_count": payroll_summary["employee_count"],
    }