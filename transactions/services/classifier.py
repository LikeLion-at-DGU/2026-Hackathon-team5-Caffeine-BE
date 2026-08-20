from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
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


class LLMTransactionClassifier:
    """OpenAI GPT-5 계열을 활용한 지출 품목 맥락 추론 분류기."""

    SYSTEM_PROMPT = """당신은 대한민국 소상공인(카페/음식점업)을 위한 전문 세무 회계 AI입니다.
주어진 거래처 상호명, 거래 금액, 수집 출처 정보를 바탕으로 카페 운영 지출 카테고리를 정확하게 분류하세요.

[분류 카테고리 목록]
- RAW_MATERIAL: 원두, 우유, 식자재, 시럽, 베이커리 생지 등 음료/디저트 제조에 직접 들어가는 원재료 (예: 매일유업, 일리카페, 스위트시럽, 베이커리팩토리 등)
- SUPPLIES: 종이컵, 빨대, 냅킨, 테이크아웃 포장재, 주방/매장 위생용품, 사무/매장 비품 등 (예: 코스트코, 삼원위생상사, 팩플러스 등)
- UTILITIES: 전기요금, 가스요금, 수도요금, 통신요금 등 공과금 (예: 한국전력공사 등)
- FEES: 카드 단말기(VAN/POS) 이용료, 결제 수수료 등 (예: 나이스정보통신 등)
- RENT: 매장 임대료, 관리비
- EQUIPMENT: 커피머신, 그라인더, 제빙기 등 설비/기물
- ADVERTISING: SNS 광고, 마케팅, 홍보비
- DELIVERY: 배달 대행, 퀵서비스, 택배비
- UNCLASSIFIED: 위 어디에도 명확히 속하지 않거나 개인 지출(유튜브, 무신사, 편의점 간식, 타 카페 음료 등)인 경우

반드시 아래 JSON 포맷으로만 응답하세요:
{
  "classifications": [
    {
      "index": 0,
      "category": "SUPPLIES",
      "confidence": 0.92,
      "reason": "카페 운영용 대용량 비품/소모품 구매로 추론"
    }
  ]
}
"""

    @classmethod
    def classify_batch(cls, items: list[dict], business_type: str = "카페/음식점업") -> list[dict]:
        """미분류 거래 목록을 GPT-5 모델로 일괄 분류하여 결과를 반환합니다."""
        if not items:
            return []

        if not getattr(settings, "OPENAI_API_KEY", ""):
            return [{"index": i, "category": Transaction.Category.UNCLASSIFIED, "confidence": None} for i in range(len(items))]

        import json
        import logging
        from openai import OpenAI

        logger = logging.getLogger(__name__)

        user_content = {
            "business_type": business_type,
            "items": [
                {
                    "index": idx,
                    "merchant_name": item.get("merchant_name", ""),
                    "amount": int(item.get("total_amount", 0)),
                    "source": item.get("source", ""),
                }
                for idx, item in enumerate(items)
            ],
        }

        try:
            client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=getattr(settings, "OPENAI_TIMEOUT_SECONDS", 20.0),
            )
            model_name = getattr(settings, "OPENAI_MODEL", "gpt-5.6-luna")
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": cls.SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
            )
            raw_text = response.choices[0].message.content
            parsed = json.loads(raw_text)
            results = parsed.get("classifications", [])
            return results
        except Exception as exc:
            logger.warning("OpenAI batch transaction classification failed: %s", exc)
            return [{"index": i, "category": Transaction.Category.UNCLASSIFIED, "confidence": None} for i in range(len(items))]

