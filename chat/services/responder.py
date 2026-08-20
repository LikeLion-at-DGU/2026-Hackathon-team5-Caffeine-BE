from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Sum

from analytics.services.monthly_summary_service import get_monthly_tax_summary
from payroll.services.payment_service import get_monthly_summary as get_payroll_summary
from tax.models import DeductionReview
from tax.services.deduction_service import DeductionReviewService
from tax.services.periods import month_range
from tax.services.vat_service import UnsupportedTaxType, VatForecastService
from transactions.models import Transaction
from transactions.services.querysets import effective_purchase_transactions, effective_transactions

ZERO = Decimal("0.00")


@dataclass
class ChatReply:
    content: str
    metadata: dict


def _won(value):
    return f"{int(value or ZERO):,}원"


class RuleBasedChatResponder:
    """실제 DB 숫자와 세무 법령 지식을 기반으로 명확하고 세분화된 답변을 제공하는 Responder."""

    name = "RULE_BASED"

    WITHHOLDING_TAX_KEYWORDS = ("원천세", "인건비납부", "원천징수", "급여세금", "납부일", "원천세납부")
    TAX_SAVING_KEYWORDS = ("절세", "절세방법", "세금줄이", "줄이는법", "공제받는법", "세금아끼", "절세팁")
    LAW_KEYWORDS = ("법령", "법적근거", "조항", "부가가치세법", "소득세법", "세법근거")
    DEDUCTION_KEYWORDS = ("공제", "불공제", "의제매입")
    VAT_KEYWORDS = ("부가세", "예상부가세", "환급", "세금얼마", "부가세계산")
    ANALYTICS_KEYWORDS = ("왜늘", "왜줄", "추이", "비율", "전월", "지난달")
    TRANSACTION_KEYWORDS = ("매출", "매입", "거래", "지출", "비용")

    def reply(self, *, business, message, year, month):
        normalized = message.replace(" ", "")

        # 1. 원천세 및 급여 납부일 질문
        if any(keyword in normalized for keyword in self.WITHHOLDING_TAX_KEYWORDS):
            return self._withholding_tax_reply(business=business, year=year, month=month)

        # 2. 절세 방법 및 팁 질문
        if any(keyword in normalized for keyword in self.TAX_SAVING_KEYWORDS):
            return self._tax_saving_reply(business=business, year=year, month=month)

        # 3. 법령 해석 및 근거 질문
        if any(keyword in normalized for keyword in self.LAW_KEYWORDS):
            return self._law_reply(business=business, year=year, month=month)

        # 4. 공제/불공제 검토 질문
        if any(keyword in normalized for keyword in self.DEDUCTION_KEYWORDS):
            return self._deduction_reply(business=business, year=year, month=month)

        # 5. 부가세 예상액 및 세금 계산 질문
        if any(keyword in normalized for keyword in self.VAT_KEYWORDS):
            return self._vat_reply(business=business, year=year, month=month)

        # 6. 증감 추이 분석 질문
        if any(keyword in normalized for keyword in self.ANALYTICS_KEYWORDS):
            return self._analytics_reply(business=business, year=year, month=month)

        # 7. 거래/매출/매입 요약 질문
        if any(keyword in normalized for keyword in self.TRANSACTION_KEYWORDS):
            return self._transaction_reply(business=business, year=year, month=month)

        return ChatReply(
            content=(
                f"안녕하세요, {business.business_name} 사장님! 카페비서 세무 AI 비서입니다. "
                "원천세 납부일, 부가세 절세 방법, 예상 부가세, 지출 공제 여부 등 궁금한 점을 질문해 주세요.\n"
                "예: '원천세 납부일이 언제야?', '부가세 절세 방법 알려줘', '이번 달 예상 부가세 얼마야?'"
            ),
            metadata={"intent": "HELP", "sources": []},
        )

    def _withholding_tax_reply(self, *, business, year, month):
        """원천세 납부 기한 및 인건비 원천징수 현황 안내."""
        payroll = get_payroll_summary(business.id, year, month)
        withholding_tax = payroll.get("withholding_tax", 0)
        total_labor = payroll.get("total_labor_cost", 0)
        employee_count = payroll.get("employee_count", 0)

        # 다음 달 10일 계산
        next_month = 1 if month == 12 else month + 1
        next_year = year + 1 if month == 12 else year
        due_date_str = f"{next_year}년 {next_month}월 10일"

        content = (
            f"📅 **원천세 납부일 및 인건비 현황 안내**\n\n"
            f"• **법정 납부 기한**: 원천징수한 세금은 급여 지급일이 속하는 달의 **다음 달 10일({due_date_str})**까지 관할 세무서에 신고·납부해야 합니다.\n"
            f"  *(반기별 납부 승인 사업장은 상반기분 7월 10일, 하반기분 익년 1월 10일까지)*\n\n"
            f"• **{business.business_name} {year}년 {month}월 인건비 현황**:\n"
            f"  - 등록 근로자: 총 {employee_count}명 (정직원, 단시간, 3.3% 프리랜서)\n"
            f"  - 지급 총액: {_won(total_labor)}\n"
            f"  - **납부할 원천징수 세액 합계: {_won(withholding_tax)}**\n\n"
            f"💡 **근거 법령**: 소득세법 제127조(원천징수의무) 및 제128조(원천징수세액의 납부기한)"
        )
        return ChatReply(
            content=content,
            metadata={
                "intent": "WITHHOLDING_TAX",
                "year_month": f"{year:04d}-{month:02d}",
                "due_date": due_date_str,
                "employee_count": employee_count,
                "total_labor_cost": total_labor,
                "withholding_tax": withholding_tax,
                "sources": ["PAYROLL", "TAX_LAW"],
            },
        )

    def _tax_saving_reply(self, *, business, year, month):
        """카페 사장님을 위한 4대 실질 절세 가이드."""
        content = (
            f"💡 **{business.business_name} 사장님을 위한 4대 카페 부가세 절세 전략**\n\n"
            f"1. **🥛 우유·생과일 의제매입세액 공제 챙기기**\n"
            f"   - 면세 농·축·수·임산물을 과세 음식용역의 원재료로 사용하면 의제매입세액 공제 대상이 될 수 있습니다. **9/109 특례율은 2026년 말까지 과세표준 2억원 이하 개인 음식점업자에게 적용**되며, 사업자 유형·증빙·공제한도 확인이 필요합니다.\n\n"
            f"2. **💳 국세청 홈택스에 '사업용 신용카드' 등록하기**\n"
            f"   - 매장에서 쓰는 카드를 홈택스에 미리 등록해 두면 소모품, 비품, 포장재 구입 시 10% 부가세 매입세액 공제가 누락 없이 자동 반영됩니다.\n\n"
            f"3. **👥 알바생·직원 인건비 원천세 적기 신고**\n"
            f"   - 매월 10일까지 인건비 원천징수 이행상황신고서를 제출해야 종합소득세 신고 시 인건비 전액을 합법적인 필요경비로 인정받아 소득세를 대폭 줄일 수 있습니다.\n\n"
            f"4. **🧾 3만 원 초과 지출 적격증빙 필수 수취**\n"
            f"   - 간이영수증 대신 세금계산서, 현금영수증(지출증빙용), 신용카드 매출전표를 받아 증빙불비 가산세(2%)를 예방하세요."
        )
        return ChatReply(
            content=content,
            metadata={
                "intent": "TAX_SAVING_GUIDE",
                "year_month": f"{year:04d}-{month:02d}",
                "sources": ["TAX_LAW", "BEST_PRACTICE"],
            },
        )

    def _law_reply(self, *, business, year, month):
        """공식 세법 조항 및 법령 근거 안내."""
        content = (
            f"📜 **카페 운영 관련 주요 세법 및 법령 근거**\n\n"
            f"• **부가가치세법 제42조 (면세농산물등 의제매입세액 공제특례)**\n"
            f"  부가가치세를 면제받아 공급받은 농산물·축산물·수산물 또는 임산물을 원재료로 하여 제조·가공한 과세 재화·용역에 대해 일정 비율을 매입세액으로 공제합니다. 2026년 말까지 과세표준 2억원 이하 개인 음식점업자는 9/109 특례율이 적용되며, 그 밖의 사업자는 법정 구분에 따라 공제율이 달라집니다.\n\n"
            f"• **소득세법 제128조 (원천징수세액의 납부기한)**\n"
            f"  원천징수의무자는 매월 징수한 세액을 그 징수일이 속하는 달의 다음 달 10일까지 관할 세무서에 납부하여야 합니다.\n\n"
            f"• **부가가치세법 제32조 (세금계산서 발급)**\n"
            f"  사업자가 재화 또는 용역을 공급하는 경우에는 전자세금계산서를 발급하여야 하며, 국세청 전송 기한은 발급일의 다음 날까지입니다."
        )
        return ChatReply(
            content=content,
            metadata={
                "intent": "LAW_INTERPRETATION",
                "sources": ["LAW_GO_KR", "NTS_GO_KR"],
            },
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
            f"확정된 일반 매입세액은 {_won(forecast['deductible_input_vat'])}입니다. "
            f"{result_sentence}"
        )
        if forecast["deemed_purchase_deduction"] > 0:
            content += (
                f" 예상 납부세액에는 면세 원재료 후보액 "
                f"{_won(forecast['deemed_purchase_candidate_amount'])}에 대한 "
                f"의제매입세액 추정 {_won(forecast['deemed_purchase_deduction'])}이 포함되었습니다. "
                "이 금액은 개인 음식점업자 특례율을 가정한 추정치로 신고 전 적격성과 한도를 확인해야 합니다."
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
                "sources": ["BUSINESS", "TAX"],
                "payable_vat": format(forecast["payable_vat"] or ZERO, "f"),
                "refundable_vat": format(forecast["refundable_vat"] or ZERO, "f"),
                "deemed_purchase_deduction": format(
                    forecast["deemed_purchase_deduction"] or ZERO, "f"
                ),
                "deemed_purchase_calculation_status": forecast[
                    "deemed_purchase_calculation_status"
                ],
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

    @staticmethod
    def _transaction_reply(*, business, year, month):
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
        if summary.get("sales_change_rate") is not None:
            change_parts.append(f"매출은 전월 대비 {summary['sales_change_rate']:+.1f}%")
        if summary.get("expense_change_rate") is not None:
            change_parts.append(f"지출은 전월 대비 {summary['expense_change_rate']:+.1f}%")
        if not change_parts:
            change_sentence = "전월 데이터가 없어 증감률은 아직 계산할 수 없습니다."
        else:
            change_sentence = ", ".join(change_parts) + "입니다."
        if summary.get("top_increasing_category"):
            change_sentence += (
                f" 가장 많이 증가한 지출 항목은 {summary['top_increasing_category']}입니다."
            )
        if summary.get("profit_margin") is None:
            profit_sentence = "매출이 없어 이익률은 계산할 수 없습니다."
        else:
            profit_sentence = (
                f"추정 순이익은 {_won(summary['net_profit'])}, "
                f"이익률은 {summary['profit_margin']:.1f}%입니다."
            )
        return ChatReply(
            content=(
                f"{year}년 {month}월 총 매출은 {_won(summary['total_sales'])}, "
                f"총 지출은 {_won(summary['total_expense'])}입니다. "
                f"{profit_sentence} {change_sentence}"
            ),
            metadata={
                "intent": "ANALYTICS",
                "year_month": f"{year:04d}-{month:02d}",
                "sources": ["ANALYTICS"],
                "analytics_available": True,
                "summary": {
                    "total_sales": summary["total_sales"],
                    "total_expense": summary["total_expense"],
                    "net_profit": summary["net_profit"],
                    "profit_margin": summary.get("profit_margin"),
                    "sales_change_rate": summary.get("sales_change_rate"),
                    "expense_change_rate": summary.get("expense_change_rate"),
                    "top_increasing_category": summary.get("top_increasing_category"),
                    "expense_breakdown": summary.get("expense_breakdown", []),
                    "payroll_withholding_tax": summary.get("payroll_withholding_tax", 0),
                    "payroll_employee_count": summary.get("payroll_employee_count", 0),
                },
            },
        )
