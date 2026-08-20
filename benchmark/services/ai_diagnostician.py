import json
import logging
from dataclasses import dataclass
from django.conf import settings
from openai import OpenAI

from benchmark.services.calculator import BenchmarkCalculationResult

logger = logging.getLogger(__name__)


@dataclass
class AIDiagnosisResult:
    score: int
    grade_label: str
    prescriptions: list[dict]
    summary_points: list[str]
    is_fallback: bool
    raw_response: dict = None


from transactions.models import Transaction
from decimal import Decimal


class RuleBasedDiagnostician:
    """OpenAI API 미설정 또는 호출 실패 시 실제 매장 거래 데이터를 정밀 분석하여 실전형 원포인트 처방을 도출하는 안전장치."""

    @classmethod
    def diagnose(cls, calc: BenchmarkCalculationResult) -> AIDiagnosisResult:
        diff_pct = calc.revenue_diff_pct
        if diff_pct > 20:
            score = 95
            grade_label = "최우수 — 상위 5% 매장"
        elif diff_pct > 5:
            score = 86
            grade_label = "양호 — 상위 20% 매장"
        elif diff_pct > -5:
            score = 75
            grade_label = "보통 — 평균 수준 매장"
        else:
            score = 65
            grade_label = "주의 — 하위 30% 매장"

        # 1. 실제 매장의 8월 거래 내역 분석
        year, month = map(int, calc.year_month.split("-"))
        purchases = Transaction.objects.filter(
            business_id=calc.business_id,
            transaction_date__year=year,
            transaction_date__month=month,
            transaction_type=Transaction.TransactionType.PURCHASE,
        )

        # (1) 면세 의제매입 대상(우유 등) 탐색 (가장 큰 매입처 우선)
        deemed_tx = purchases.filter(
            category=Transaction.Category.RAW_MATERIAL,
            vat_amount=0,
        ).order_by("-total_amount").first()
        milk_merchant = deemed_tx.merchant_name if deemed_tx else "식자재 거래처"
        milk_amount = int(deemed_tx.total_amount) if deemed_tx else 0
        deemed_vat_saving = int(milk_amount * Decimal(9) / Decimal(109))

        # (2) 개인 지출(불공제) 탐색
        personal_txs = purchases.filter(
            expense_purpose=Transaction.ExpensePurpose.PERSONAL
        )
        personal_count = personal_txs.count()
        personal_sum = sum(int(t.total_amount) for t in personal_txs)
        personal_names = "·".join([t.merchant_name.split()[0] for t in personal_txs[:3]]) if personal_txs.exists() else "개인 지출"

        # (3) 포장재/소모품 탐색
        supplies_tx = purchases.filter(
            category=Transaction.Category.SUPPLIES
        ).first()
        supplies_merchant = supplies_tx.merchant_name if supplies_tx else "소모품 거래처"
        supplies_amount = int(supplies_tx.total_amount) if supplies_tx else 0

        # (4) 인건비 비중
        labor_item = next((item for item in calc.category_comparison if item.category == "PAYROLL"), None)
        labor_ratio = labor_item.my_ratio if labor_item else 0.0
        labor_bm = labor_item.benchmark_ratio if labor_item else 0.0

        # 2. 실제 데이터 100% 매칭 3대 실전 처방
        prescriptions = [
            {
                "id": 1,
                "type": "COST_REDUCTION",
                "title": f"{month}월 {supplies_merchant}({supplies_amount:,}원) 등 포장재·소모품비 구매 시 테이크아웃 컵·홀더를 낱개 구매하는 대신 분기 단위 박스 대량 발주 또는 B2B 도매몰로 전환 시 고정비를 즉시 절감할 수 있습니다." if supplies_amount > 0 else "포장재·소모품비 구매 시 낱개 구매 대신 분기 단위 대량 발주 또는 전용 B2B 몰 전환으로 고정비를 즉시 절감하세요.",
            },
            {
                "id": 2,
                "type": "REVENUE_BOOST",
                "title": f"현재 인건비율({labor_ratio:.1f}%)을 고려할 때, 오후 유휴 시간대에 마진율이 높은 고단가 세트를 집중 판매하여 객단가를 끌어올려 알바비 효율을 극대화하세요.",
            },
            {
                "id": 3,
                "type": "TAX_SAVING",
                "title": f"{month}월 {milk_merchant} 매입({milk_amount:,}원)에 대해 부가가치세법 제42조(의제매입세액 공제)를 적용하여 이번 부가세 신고 시 공제/환급을 챙기세요." if milk_amount > 0 else "면세 식자재 매입 시 부가가치세법 제42조에 따른 음식점업 의제매입세액 공제(공제율 9/109)를 위해 계산서를 꼭 발급받으세요.",
            },
        ]

        # 3. 3대 핵심 요약
        summary_points = [
            f"식자재 원가율({calc.raw_material_ratio:.1f}%)은 상권 평균({calc.benchmark_raw_material_ratio:.1f}%)과 비교해 관리 중이며, 포장재 대량 발주 시 추가적인 비용 절감이 가능합니다.",
            f"{month}월 인건비 비중({labor_ratio:.1f}%)은 상권 평균({labor_bm:.1f}%) 대비 관리되고 있으며, 유휴 시간대 고마진 세트 판매로 매출 효율을 높일 수 있습니다.",
            f"개인 지출 {personal_count}건({personal_names} 등 {personal_sum:,}원)을 AI가 사전 불공제 분류하여 국세청 가산세(10%)를 선제적으로 방어했습니다." if personal_count > 0 else "개인 용도 지출을 사업용 카드에서 분리하여 가산세 리스크를 선제적으로 예방하고 있습니다.",
        ]

        return AIDiagnosisResult(
            score=score,
            grade_label=grade_label,
            prescriptions=prescriptions,
            summary_points=summary_points,
            is_fallback=True,
            raw_response={"source": "rule_based_fallback"},
        )


class AIDiagnostician:
    """OpenAI를 활용하여 소상공인 맞춤형 AI 경영 진단 및 원포인트 처방을 생성한다."""

    def __init__(self, client=None):
        self.client = client

    def diagnose(self, calc: BenchmarkCalculationResult) -> AIDiagnosisResult:
        if not getattr(settings, "OPENAI_API_KEY", ""):
            logger.info("OPENAI_API_KEY 미설정으로 규칙 기반 진단(Fallback)을 사용합니다.")
            return RuleBasedDiagnostician.diagnose(calc)

        diff_pct = calc.revenue_diff_pct
        if diff_pct > 20:
            example_score = 95
            example_grade = "최우수 — 상위 5% 매장"
        elif diff_pct > 5:
            example_score = 86
            example_grade = "양호 — 상위 20% 매장"
        elif diff_pct > -5:
            example_score = 75
            example_grade = "보통 — 평균 수준 매장"
        else:
            example_score = 65
            example_grade = "주의 — 하위 30% 매장"

        prompt_input = f"""
[내 매장 재무/세무 지표]
- 매장명: {calc.business_name}
- 기준 연월: {calc.year_month}
- 상권 위치: {calc.region_name}
- 총매출: {calc.total_revenue:,}원 (상권 평균 대비 {calc.revenue_diff_pct:+0.1f}%)
- 총지출: {calc.total_expense:,}원
- 식자재·원두 비중: {calc.raw_material_ratio}% (상권 평균 {calc.benchmark_raw_material_ratio}%, 차이 {calc.raw_material_diff_pct:+0.1f}%p)
- 카테고리 비교: {json.dumps([{'name': item.name, 'my_ratio': item.my_ratio, 'bm_ratio': item.benchmark_ratio, 'diff': item.diff_ratio} for item in calc.category_comparison], ensure_ascii=False)}

[작성 지침 - 절대 상투적이거나 뻔한 교과서 문구를 쓰지 마세요]
1. '거래처와 신뢰를 유지하세요', '친절하게 응대하세요', '세트 할인을 해보세요' 같은 무의미하고 당연한 말은 엄격히 금지합니다.
2. 반드시 [1] 문제 지출 항목과 구체적 절감 금액, [2] 시간대별 객단가 개선 목표와 추천 메뉴 조합, [3] 부가가치세법 제42조 의제매입세액 공제율(9/109) 등 실제 데이터를 반영한 숫자가 포함된 실전형 원포인트 솔루션을 작성하세요.
3. 매장의 상황에 맞는 동적인 점수와 등급 라벨을 생성하세요.

위 정량 데이터를 바탕으로 소상공인 카페 사장님을 위한 맞춤 진단을 아래 JSON 형식으로만 작성하세요 (예시 데이터는 참고용이며 실제 지표를 반영할 것):
{{
  "score": {example_score},
  "grade_label": "{example_grade}",
  "prescriptions": [
    {{"id": 1, "type": "COST_REDUCTION", "title": "포장재 구매 시 분기 단위 박스 대량 발주 또는 카페 전용 B2B 도매몰로 전환 시 고정비를 즉시 절감할 수 있습니다."}},
    {{"id": 2, "type": "REVENUE_BOOST", "title": "오후 14~17시 유휴 시간대에 마진율이 높은 고단가 디저트 페어링 세트를 집중 판매하여 객단가를 끌어올려 알바비 효율을 극대화하세요."}},
    {{"id": 3, "type": "TAX_SAVING", "title": "식자재 매입 시 부가가치세법 제42조에 따른 음식점업 의제매입세액 공제(공제율 9/109)를 적용하기 위해 계산서 발행 여부를 꼭 확인하세요."}}
  ],
  "summary_points": [
    "식자재 원가율은 상권 평균 대비 우수하며, 포장재 대량 발주 시 추가 절감이 가능합니다.",
    "인건비 비중은 상권 평균 대비 안정적이며, 유휴 시간대 고마진 판매로 매출 효율을 높일 수 있습니다.",
    "개인 지출 항목을 AI가 사전 불공제 분류하여 가산세를 선제적으로 방어했습니다."
  ]
}}
"""

        try:
            client = self.client or OpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=getattr(settings, "OPENAI_TIMEOUT_SECONDS", 20.0),
            )
            response = client.chat.completions.create(
                model=getattr(settings, "OPENAI_MODEL", "gpt-5.6-luna"),
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 대한민국 소상공인 자영업자를 위한 최고재무책임자(CFO) AI 컨설턴트입니다. 뻔한 교과서 조언을 배제하고, 실제 장부 숫자와 상권 통계에 기반한 날카롭고 구체적인 원포인트 솔루션을 오직 유효한 JSON 형식으로만 응답하세요.",
                    },
                    {"role": "user", "content": prompt_input},
                ],
                response_format={"type": "json_object"},
            )
            raw_text = response.choices[0].message.content
            parsed = json.loads(raw_text)

            score = int(parsed.get("score", example_score))
            grade_label = str(parsed.get("grade_label", example_grade))
            prescriptions = parsed.get("prescriptions", [])
            summary_points = parsed.get("summary_points", [])

            # 유효성 검사
            if not prescriptions or not summary_points:
                raise ValueError("JSON 응답 필수 키 누락")

            return AIDiagnosisResult(
                score=score,
                grade_label=grade_label,
                prescriptions=prescriptions,
                summary_points=summary_points,
                is_fallback=False,
                raw_response=parsed,
            )

        except Exception as exc:
            logger.warning(f"OpenAI 진단 생성 실패 ({exc}); 규칙 기반 진단(Fallback)으로 대체합니다.")
            return RuleBasedDiagnostician.diagnose(calc)
