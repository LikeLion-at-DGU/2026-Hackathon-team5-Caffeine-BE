from decimal import Decimal

from django.db.models import Sum

from transactions.models import MonthlySalesSummary, Transaction

from ..models import DeductionReview
from .deduction_service import DeductionReviewService
from .periods import month_range
from transactions.services.querysets import effective_transactions


ZERO = Decimal("0.00")


class UnsupportedTaxType(ValueError):
    pass


class VatForecastService:
    SUPPORTED_TAX_TYPE = "GENERAL"

    @staticmethod
    def _sum(queryset, field):
        return queryset.aggregate(value=Sum(field))["value"] or ZERO

    @classmethod
    def calculate(cls, *, business, year, month):
        if business.tax_type != cls.SUPPORTED_TAX_TYPE:
            raise UnsupportedTaxType(
                "현재 예상 부가세 계산은 일반과세자(GENERAL)만 지원합니다."
            )

        start_date, end_date = month_range(year, month)
        transactions = effective_transactions(
            business=business,
            start_date=start_date,
            end_date=end_date,
        )
        purchases = transactions.filter(transaction_type=Transaction.TransactionType.PURCHASE)
        sales = transactions.filter(transaction_type=Transaction.TransactionType.SALE)
        DeductionReviewService.ensure_for_queryset(purchases)

        deductible = purchases.filter(
            deduction_review__confirmed_status=DeductionReview.ConfirmedStatus.DEDUCTIBLE
        )
        non_deductible = purchases.filter(
            deduction_review__confirmed_status=DeductionReview.ConfirmedStatus.NON_DEDUCTIBLE
        )
        unconfirmed = purchases.filter(
            deduction_review__confirmed_status=DeductionReview.ConfirmedStatus.UNCONFIRMED
        )

        output_vat = cls._sum(sales, "vat_amount")
        deductible_input_vat = cls._sum(deductible, "vat_amount")
        estimated_vat = output_vat - deductible_input_vat
        payable_vat = max(estimated_vat, ZERO)
        refundable_vat = max(-estimated_vat, ZERO)

        card_summary = MonthlySalesSummary.objects.filter(
            business=business,
            year=year,
            month=month,
            source_type=MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
        ).first()
        warnings = []
        if card_summary is not None:
            warnings.append(
                "신용카드 매출 집계는 공급가액과 세액이 분리되지 않아 예상 부가세에 직접 합산하지 않았습니다."
            )

        return {
            "business_id": business.id,
            "tax_type": business.tax_type,
            "year_month": f"{year:04d}-{month:02d}",
            "sales_supply_amount": cls._sum(sales, "supply_amount"),
            "sales_amount": cls._sum(sales, "total_amount"),
            "output_vat": output_vat,
            "purchase_supply_amount": cls._sum(purchases, "supply_amount"),
            "purchase_amount": cls._sum(purchases, "total_amount"),
            "deductible_input_vat": deductible_input_vat,
            "review_required_input_vat": cls._sum(unconfirmed, "vat_amount"),
            "non_deductible_input_vat": cls._sum(non_deductible, "vat_amount"),
            "estimated_vat": estimated_vat,
            "payable_vat": payable_vat,
            "refundable_vat": refundable_vat,
            "unconfirmed_transaction_count": unconfirmed.count(),
            "card_sales_summary": (
                {
                    "transaction_count": card_summary.transaction_count,
                    "total_amount": card_summary.total_amount,
                    "included_in_vat_forecast": False,
                }
                if card_summary is not None
                else None
            ),
            "warnings": warnings,
            "calculation_basis": "OUTPUT_VAT_MINUS_CONFIRMED_INPUT_VAT",
        }
