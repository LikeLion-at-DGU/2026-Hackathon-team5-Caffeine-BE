from datetime import date
from decimal import Decimal

from django.db.models import Sum

from businesses.models import Business
from payroll.services.payment_service import get_monthly_summary as get_payroll_summary
from tax.services.periods import month_range
from transactions.services.querysets import effective_transactions
from transactions.models import Transaction

from .monthly_summary_service import get_monthly_tax_summary


ZERO = Decimal("0")


def _shift_month(year: int, month: int, offset: int) -> tuple[int, int]:
    month_index = year * 12 + (month - 1) + offset
    return month_index // 12, month_index % 12 + 1


def get_cost_ratio(*, business_id: int, year: int, month: int) -> dict:
    summary = get_monthly_tax_summary(business_id, year, month)
    return {
        "business_id": business_id,
        "year_month": f"{year:04d}-{month:02d}",
        "total_expense": summary["total_expense"],
        "items": summary.get("raw_expense_breakdown", summary["expense_breakdown"]),
    }


def _category_amount(*, business, category: str, year: int, month: int) -> Decimal:
    if category == "LABOR":
        return Decimal(str(get_payroll_summary(business.id, year, month)["total_labor_cost"]))

    start_date, end_date = month_range(year, month)
    return effective_transactions(
        business=business,
        start_date=start_date,
        end_date=end_date,
    ).filter(
        transaction_type=Transaction.TransactionType.PURCHASE,
        expense_purpose=Transaction.ExpensePurpose.BUSINESS,
        category=category,
    ).aggregate(total=Sum("total_amount"))["total"] or ZERO


def get_category_trend(
    *,
    business_id: int,
    category: str,
    end_year: int | None = None,
    end_month: int | None = None,
    months: int = 6,
) -> dict:
    business = Business.objects.get(pk=business_id)
    today = date.today()
    end_year = end_year or today.year
    end_month = end_month or today.month
    values = []
    previous = None
    for offset in range(-(months - 1), 1):
        year, month = _shift_month(end_year, end_month, offset)
        amount = _category_amount(
            business=business,
            category=category,
            year=year,
            month=month,
        )
        change_rate = None
        if previous:
            change_rate = round((float(amount) - float(previous)) / float(previous) * 100, 1)
        values.append(
            {
                "year_month": f"{year:04d}-{month:02d}",
                "amount": int(amount),
                "change_rate": change_rate,
            }
        )
        previous = amount

    labels = dict([*Transaction.Category.choices, ("LABOR", "인건비")])
    return {
        "business_id": business_id,
        "category": category,
        "label": labels[category],
        "items": values,
        "latest_change_rate": values[-1]["change_rate"],
    }
