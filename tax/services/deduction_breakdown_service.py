from decimal import Decimal

from django.db.models import Sum

from transactions.models import Transaction

from ..models import DeductionReview
from .deduction_service import DeductionReviewService
from .periods import month_range
from .querysets import effective_purchase_transactions


ZERO = Decimal("0")


def _sum(queryset, field="transaction__total_amount"):
    return queryset.aggregate(total=Sum(field))["total"] or ZERO


def build_deduction_breakdown(*, business, year: int, month: int) -> dict:
    start_date, end_date = month_range(year, month)
    purchases = effective_purchase_transactions(
        business=business,
        start_date=start_date,
        end_date=end_date,
    )
    DeductionReviewService.ensure_for_queryset(purchases)
    reviews = DeductionReview.objects.filter(transaction__in=purchases)

    confirmed_deductible = reviews.filter(
        confirmed_status=DeductionReview.ConfirmedStatus.DEDUCTIBLE
    )
    taxable = confirmed_deductible.filter(transaction__vat_amount__gt=0)
    deemed_candidates = confirmed_deductible.filter(
        transaction__vat_amount=0,
        transaction__category=Transaction.Category.RAW_MATERIAL,
        transaction__expense_purpose=Transaction.ExpensePurpose.BUSINESS,
    )
    non_deductible = reviews.filter(
        confirmed_status=DeductionReview.ConfirmedStatus.NON_DEDUCTIBLE
    )
    review_required = reviews.filter(
        confirmed_status=DeductionReview.ConfirmedStatus.UNCONFIRMED
    )

    groups = [
        ("TAXABLE_DEDUCTIBLE", "과세매입(공제가능)", taxable),
        ("DEEMED_PURCHASE_CANDIDATE", "면세 원재료(의제매입 후보)", deemed_candidates),
        ("NON_DEDUCTIBLE", "비공제 지출", non_deductible),
        ("REVIEW_REQUIRED", "검토 필요", review_required),
    ]
    total_purchase_amount = _sum(reviews)
    structure = []
    for code, label, queryset in groups:
        amount = _sum(queryset)
        ratio = round(float(amount / total_purchase_amount * 100), 1) if total_purchase_amount else 0.0
        structure.append(
            {"code": code, "category": label, "amount": int(amount), "ratio": ratio}
        )

    category_labels = dict(Transaction.Category.choices)
    item_details = []
    for row in reviews.values(
        "transaction__category", "confirmed_status"
    ).annotate(
        amount=Sum("transaction__total_amount"),
        vat_amount=Sum("transaction__vat_amount"),
    ).order_by("-amount")[:8]:
        category = row["transaction__category"]
        confirmed_status = row["confirmed_status"]
        amount = row["amount"] or ZERO
        is_deemed_candidate = (
            confirmed_status == DeductionReview.ConfirmedStatus.DEDUCTIBLE
            and category == Transaction.Category.RAW_MATERIAL
            and not row["vat_amount"]
        )
        item_details.append(
            {
                "item_name": category_labels.get(category, category),
                "category": category,
                "deduction_type": (
                    "의제매입 후보"
                    if is_deemed_candidate
                    else (
                        "과세공제"
                        if confirmed_status == DeductionReview.ConfirmedStatus.DEDUCTIBLE
                        else "검토 필요" if confirmed_status == DeductionReview.ConfirmedStatus.UNCONFIRMED else "불공제"
                    )
                ),
                "amount": int(amount),
                "rate": round(float(amount / total_purchase_amount * 100), 1)
                if total_purchase_amount
                else 0.0,
            }
        )

    normal_input_vat = _sum(taxable, "transaction__vat_amount")
    unconfirmed_count = review_required.count()
    return {
        "business_id": business.id,
        "year_month": f"{year:04d}-{month:02d}",
        "deduction_grade": "검토 필요" if unconfirmed_count else "공제 검토 완료",
        "total_deductible_amount": int(normal_input_vat),
        "normal_input_vat": int(normal_input_vat),
        "deemed_purchase_candidate_amount": int(_sum(deemed_candidates)),
        "deemed_purchase_deduction": 0,
        "unconfirmed_transaction_count": unconfirmed_count,
        "structure": structure,
        "item_details": item_details,
        "warnings": [
            "의제매입 후보 금액은 표시만 하며 공제율을 적용한 세액은 아직 계산하지 않습니다."
        ],
    }
