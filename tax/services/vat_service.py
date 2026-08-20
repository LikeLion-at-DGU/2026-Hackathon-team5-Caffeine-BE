from decimal import Decimal, ROUND_DOWN

from django.db.models import Sum

from transactions.models import MonthlySalesSummary, Transaction

from ..models import DeductionReview
from .deduction_service import DeductionReviewService
from .deemed_purchase_service import (
    LEGAL_BASIS,
    SPECIAL_RATE_VALID_THROUGH,
    estimate_deemed_purchase_deduction,
)
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

        transaction_sales_supply_amount = cls._sum(sales, "supply_amount")
        transaction_sales_amount = cls._sum(sales, "total_amount")
        transaction_output_vat = cls._sum(sales, "vat_amount")
        deductible_input_vat = cls._sum(deductible, "vat_amount")
        deemed_candidates = deductible.filter(
            vat_amount=0,
            category=Transaction.Category.RAW_MATERIAL,
            expense_purpose=Transaction.ExpensePurpose.BUSINESS,
        )
        deemed_purchase_candidate_amount = cls._sum(deemed_candidates, "total_amount")
        deemed_estimate = estimate_deemed_purchase_deduction(
            business=business,
            candidate_amount=deemed_purchase_candidate_amount,
            year=year,
        )
        card_summary = MonthlySalesSummary.objects.filter(
            business=business,
            year=year,
            month=month,
            source_type=MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
        ).first()
        card_sales_total_amount = card_summary.total_amount if card_summary else ZERO
        card_sales_estimated_output_vat = (
            card_sales_total_amount * Decimal("10") / Decimal("110")
        ).quantize(Decimal("1"), rounding=ROUND_DOWN)
        card_sales_estimated_supply_amount = (
            card_sales_total_amount - card_sales_estimated_output_vat
        )

        output_vat = transaction_output_vat + card_sales_estimated_output_vat
        sales_supply_amount = (
            transaction_sales_supply_amount + card_sales_estimated_supply_amount
        )
        sales_amount = transaction_sales_amount + card_sales_total_amount
        total_deductible_input_vat = deductible_input_vat + deemed_estimate.deduction
        estimated_vat = output_vat - total_deductible_input_vat
        payable_vat = max(estimated_vat, ZERO)
        refundable_vat = max(-estimated_vat, ZERO)

        warnings = list(deemed_estimate.warnings)
        if card_summary is not None:
            warnings.append(
                "신용카드 월 매출 집계 총액을 모두 10% 과세 매출로 가정해 총액의 10/110을 매출세액으로 추정했습니다. 면세·영세율 매출이 포함되면 실제 신고세액과 달라질 수 있습니다."
            )

        return {
            "business_id": business.id,
            "tax_type": business.tax_type,
            "year_month": f"{year:04d}-{month:02d}",
            "sales_supply_amount": sales_supply_amount,
            "sales_amount": sales_amount,
            "output_vat": output_vat,
            "transaction_sales_supply_amount": transaction_sales_supply_amount,
            "transaction_sales_amount": transaction_sales_amount,
            "transaction_output_vat": transaction_output_vat,
            "purchase_supply_amount": cls._sum(purchases, "supply_amount"),
            "purchase_amount": cls._sum(purchases, "total_amount"),
            "deductible_input_vat": deductible_input_vat,
            "deemed_purchase_candidate_amount": deemed_purchase_candidate_amount,
            "deemed_purchase_deduction": deemed_estimate.deduction,
            "deemed_purchase_rate": deemed_estimate.rate,
            "deemed_purchase_calculation_status": deemed_estimate.calculation_status,
            "deemed_purchase_rate_valid_through": (
                SPECIAL_RATE_VALID_THROUGH if deemed_estimate.rate else None
            ),
            "total_deductible_input_vat": total_deductible_input_vat,
            "legal_basis": LEGAL_BASIS,
            "calculation_assumptions": deemed_estimate.assumptions,
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
                    "estimated_supply_amount": card_sales_estimated_supply_amount,
                    "estimated_output_vat": card_sales_estimated_output_vat,
                    "included_in_vat_forecast": True,
                    "calculation_method": "TOTAL_AMOUNT_X_10_OVER_110",
                    "is_estimate": True,
                }
                if card_summary is not None
                else None
            ),
            "warnings": warnings,
            "calculation_basis": (
                "TRANSACTION_OUTPUT_VAT_PLUS_ESTIMATED_CARD_OUTPUT_VAT_"
                "MINUS_CONFIRMED_INPUT_VAT_MINUS_PROVISIONAL_DEEMED_PURCHASE_DEDUCTION"
            ),
        }
