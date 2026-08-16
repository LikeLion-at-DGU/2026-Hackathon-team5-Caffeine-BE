from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from transactions.models import Transaction
from transactions.services.types import NormalizedTransaction


@dataclass(frozen=True, slots=True)
class ClassificationResult:
    category: str
    source: str
    confidence: Decimal | None
    matched_keywords: tuple[str, ...] = ()


class RuleBasedTransactionClassifier:
    """거래처 업종·종목과 세금계산서 품목에만 근거한 보수적 분류기."""

    KEYWORDS = {
        Transaction.Category.RAW_MATERIAL: (
            "원두",
            "유제품",
            "식료품",
            "식자재",
            "베이커리",
            "빵류",
            "과자류",
            "시럽",
            "소스",
            "냉동과일",
            "생크림",
        ),
        Transaction.Category.RENT: ("임대료", "임차료", "월세"),
        Transaction.Category.UTILITIES: (
            "한국전력",
            "서울전력",
            "전기요금",
            "수도요금",
            "도시가스",
            "통신요금",
        ),
        Transaction.Category.SUPPLIES: (
            "포장용기",
            "일회용품",
            "종이컵",
            "컵홀더",
            "빨대",
            "냅킨",
            "위생용품",
            "청소용품",
            "세정제",
            "사무용품",
            "문구",
            "영수증 용지",
        ),
        Transaction.Category.ADVERTISING: ("광고", "마케팅", "홍보"),
        Transaction.Category.DELIVERY: ("택배", "배송", "운송", "퀵서비스", "배달대행"),
        Transaction.Category.FEES: ("수수료", "플랫폼 이용료", "카드 단말기 이용료"),
        Transaction.Category.EQUIPMENT: (
            "주방용품",
            "카페용품",
            "커피머신",
            "그라인더",
            "냉장고",
            "제빙기",
            "계량도구",
        ),
    }

    def classify(self, normalized: NormalizedTransaction) -> ClassificationResult:
        if normalized.transaction_type != Transaction.TransactionType.PURCHASE:
            return self._unclassified()

        haystack = " ".join(normalized.classification_hints).casefold()
        if not haystack:
            return self._unclassified()

        matches = {}
        scores = Counter()
        for category, keywords in self.KEYWORDS.items():
            matched = tuple(keyword for keyword in keywords if keyword.casefold() in haystack)
            if matched:
                matches[category] = matched
                scores[category] = len(matched)

        if not scores:
            return self._unclassified()

        ranking = scores.most_common()
        best_category, best_score = ranking[0]
        if len(ranking) > 1 and ranking[1][1] == best_score:
            return self._unclassified()

        confidence = Decimal("0.9500") if best_score >= 2 else Decimal("0.8500")
        return ClassificationResult(
            category=best_category,
            source=Transaction.ClassificationSource.RULE,
            confidence=confidence,
            matched_keywords=matches[best_category],
        )

    @staticmethod
    def _unclassified():
        return ClassificationResult(
            category=Transaction.Category.UNCLASSIFIED,
            source=Transaction.ClassificationSource.UNCLASSIFIED,
            confidence=None,
        )
