from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Sum

from analytics.services.monthly_summary_service import get_monthly_tax_summary
from transactions.models import Transaction

from tax.models import DeductionReview
from tax.services.deduction_service import DeductionReviewService
from tax.services.periods import month_range
from transactions.services.querysets import effective_purchase_transactions, effective_transactions
from tax.services.vat_service import UnsupportedTaxType, VatForecastService


ZERO = Decimal("0.00")


@dataclass
class ChatReply:
    content: str
    metadata: dict


def _won(value):
    return f"{int(value or ZERO):,}원"


class RuleBasedChatResponder:
    """실제 DB 숫자를 설명하는 MVP responder.

    산술 계산은 서비스/ORM이 수행하고 이 클래스는 결과를 문장으로 바꾼다.
    실제 LLM responder는 동일한 reply 인터페이스로 나중에 교체할 수 있다.
    """

    name = "RULE_BASED"

    VAT_KEYWORDS = ("부가세", "세금", "납부", "환급")
    DEDUCTION_KEYWORDS = ("공제", "불공제")
    ANALYTICS_KEYWORDS = ("왜 늘", "왜 줄", "추이", "비율", "전월", "지난달")
    TRANSACTION_KEYWORDS = ("매출", "매입", "거래", "지출", "비용")

    def reply(self, *, business, message, year, month):
        normalized = message.replace(" ", "")
        if any(keyword in normalized for keyword in self.DEDUCTION_KEYWORDS):
            return self._deduction_reply(business=business, year=year, month=month)
        if any(keyword in normalized for keyword in self.VAT_KEYWORDS):
            return self._vat_reply(business=business, year=year, month=month)
        if any(keyword in normalized for keyword in self.ANALYTICS_KEYWORDS):
            return self._analytics_reply(
                business=business,
                year=year,
                month=month,
            )
        if any(keyword in normalized for keyword in self.TRANSACTION_KEYWORDS):
            return self._transaction_reply(business=business, year=year, month=month)
        return ChatReply(
            content=(
                "거래, 매출·매입, 공제 검토, 예상 부가세에 관해 질문해 주세요. "
                "예: ‘이번 달 예상 부가세 얼마야?’"
            ),
            metadata={"intent": "HELP", "sources": []},
        )

    def _vat_reply(self, *, business, year, month):
        try:
            forecast = VatForecastService.calculate(business=business, year=year, month=month)
        except UnsupportedTaxType:
            return ChatReply(
                content=(
                    f"{business.tax_type} "
                    "사업자의 예상 부가세 계산은 아직 지원하지 않습니다. 현재는 일반과세자만 계산할 수 있습니다."
                ),
                metadata={
                    "intent": "VAT_FORECAST",
                    "year_month": f"{year:04d}-{month:02d}",
                    "sources": ["BUSINESS", "TAX"],
                    "supported": False,
                },
            )

        if forecast["refundable_vat"] > 0:
            result_sentence = f"현재 자료 기준 예상 환급세액은 {_won(forecast['refundable_vat'])}입니다."
        else:
            result_sentence = f"현재 자료 기준 예상 납부세액은 {_won(forecast['payable_vat'])}입니다."
        content = (
            f"{year}년 {month}월 매출세액은 {_won(forecast['output_vat'])}, "
            f"확정된 공제 매입세액은 {_won(forecast['deductible_input_vat'])}입니다. "
            f"{result_sentence}"
        )
        if forecast["unconfirmed_transaction_count"]:
            content += (
                f" 아직 공제 여부를 확인하지 않은 거래가 "
                f"{forecast['unconfirmed_transaction_count']}건 있어 금액이 달라질 수 있습니다."
            )
        return ChatReply(
            content=content,
            metadata={
                "intent": "VAT_FORECAST",
                "year_month": forecast["year_month"],
                "sources": ["BUSINESS", "TRANSACTION", "TAX"],
                "forecast": {
                    "output_vat": format(forecast["output_vat"], "f"),
                    "deductible_input_vat": format(forecast["deductible_input_vat"], "f"),
                    "payable_vat": format(forecast["payable_vat"], "f"),
                    "refundable_vat": format(forecast["refundable_vat"], "f"),
                    "unconfirmed_transaction_count": forecast["unconfirmed_transaction_count"],
                },
            },
        )

    def _deduction_reply(self, *, business, year, month):
        start_date, end_date = month_range(year, month)
        purchases = effective_purchase_transactions(
            business=business,
            start_date=start_date,
            end_date=end_date,
        )
        DeductionReviewService.ensure_for_queryset(purchases)
        counts = {
            item["confirmed_status"]: item["count"]
            for item in DeductionReview.objects.filter(transaction__in=purchases)
            .values("confirmed_status")
            .annotate(count=Count("id"))
        }
        deductible = counts.get(DeductionReview.ConfirmedStatus.DEDUCTIBLE, 0)
        non_deductible = counts.get(DeductionReview.ConfirmedStatus.NON_DEDUCTIBLE, 0)
        unconfirmed = counts.get(DeductionReview.ConfirmedStatus.UNCONFIRMED, 0)
        return ChatReply(
            content=(
                f"{year}년 {month}월 매입 중 공제 확정 {deductible}건, "
                f"불공제 확정 {non_deductible}건, 확인 필요 {unconfirmed}건입니다. "
                "AI 추천이 아닌 원본 공제 표시와 사용자의 최종 확인 결과를 기준으로 집계했습니다."
            ),
            metadata={
                "intent": "DEDUCTION_STATUS",
                "year_month": f"{year:04d}-{month:02d}",
                "sources": ["TRANSACTION", "TAX"],
                "counts": {
                    "deductible": deductible,
                    "non_deductible": non_deductible,
                    "unconfirmed": unconfirmed,
                },
            },
        )

    def _transaction_reply(self, *, business, year, month):
        start_date, end_date = month_range(year, month)
        transactions = effective_transactions(
            business=business,
            start_date=start_date,
            end_date=end_date,
        )
        totals = {
            item["transaction_type"]: item
            for item in transactions.values("transaction_type")
            .annotate(count=Count("id"), amount=Sum("total_amount"))
        }
        sales = totals.get(Transaction.TransactionType.SALE, {"count": 0, "amount": ZERO})
        purchases = totals.get(
            Transaction.TransactionType.PURCHASE,
            {"count": 0, "amount": ZERO},
        )
        return ChatReply(
            content=(
                f"{year}년 {month}월 정리된 거래는 매출 {sales['count']}건 "
                f"({_won(sales['amount'])}), 매입 {purchases['count']}건 "
                f"({_won(purchases['amount'])})입니다. 취소 거래와 중복 확정 거래는 제외했습니다."
            ),
            metadata={
                "intent": "TRANSACTION_SUMMARY",
                "year_month": f"{year:04d}-{month:02d}",
                "sources": ["TRANSACTION"],
                "sales": {"count": sales["count"], "amount": format(sales["amount"] or ZERO, "f")},
                "purchases": {
                    "count": purchases["count"],
                    "amount": format(purchases["amount"] or ZERO, "f"),
                },
            },
        )

    @staticmethod
    def _analytics_reply(*, business, year, month):
        summary = get_monthly_tax_summary(business.id, year, month)
        change_parts = []
        if summary["sales_change_rate"] is not None:
            change_parts.append(f"매출은 전월 대비 {summary['sales_change_rate']:+.1f}%")
        if summary["expense_change_rate"] is not None:
            change_parts.append(f"지출은 전월 대비 {summary['expense_change_rate']:+.1f}%")
        if not change_parts:
            change_sentence = "전월 데이터가 없어 증감률은 아직 계산할 수 없습니다."
        else:
            change_sentence = ", ".join(change_parts) + "입니다."
        if summary["top_increasing_category"]:
            change_sentence += (
                f" 가장 많이 증가한 지출 항목은 {summary['top_increasing_category']}입니다."
            )
        return ChatReply(
            content=(
                f"{year}년 {month}월 총 매출은 {_won(summary['total_sales'])}, "
                f"총 지출은 {_won(summary['total_expense'])}입니다. {change_sentence}"
            ),
            metadata={
                "intent": "ANALYTICS",
                "year_month": f"{year:04d}-{month:02d}",
                "sources": ["ANALYTICS"],
                "analytics_available": True,
                "summary": {
                    "total_sales": summary["total_sales"],
                    "total_expense": summary["total_expense"],
                    "sales_change_rate": summary["sales_change_rate"],
                    "expense_change_rate": summary["expense_change_rate"],
                    "top_increasing_category": summary["top_increasing_category"],
                },
            },
        )
