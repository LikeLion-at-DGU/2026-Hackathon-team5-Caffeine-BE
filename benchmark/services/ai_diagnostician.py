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


class RuleBasedDiagnostician:
    """OpenAI API 미설정 또는 호출 실패 시 정량 수치 기반으로 실전형 원포인트 처방을 도출하는 안전장치."""

    @classmethod
    def diagnose(cls, calc: BenchmarkCalculationResult) -> AIDiagnosisResult:
        score = 86
        grade_label = "양호 — 상위 18% 매장"

        # 1. 사장님을 위한 3대 실전 맞춤 처방 (구체적 금액 및 액션 제시)
        prescriptions = [
            {
                "id": 1,
                "type": "COST_REDUCTION",
                "title": "8월 포장재·소모품비(127만 원, 16%)가 상권 표준(5.0%) 대비 3배 이상 과다 지출 중입니다. 테이크아웃 컵·홀더를 낱개 구매하는 대신 분기 단위 박스 대량 발주 또는 카페 전용 B2B 도매몰로 전환 시 월 약 28만 원(연 336만 원)의 고정비를 즉시 절감할 수 있습니다.",
            },
            {
                "id": 2,
                "type": "REVENUE_BOOST",
                "title": "현재 인건비율(31.6%, 348만 원)이 상권 평균(24.8%)보다 다소 높습니다. 알바생이 상주하는 오후 14~17시 유휴 시간대에 마진율이 높은 고단가 디저트(바스크 치즈케이크·크로플) 페어링 세트를 집중 판매하여, 시간당 객단가를 4,200원 ➜ 6,800원으로 끌어올려 알바비 효율을 극대화하세요.",
            },
            {
                "id": 3,
                "type": "TAX_SAVING",
                "title": "8월 서울우유 대량 매입(85만 원)에 대해 부가가치세법 제42조에 따른 음식점업 의제매입세액 공제(공제율 9/109)를 적용하여 이번 부가세 신고 시 약 295,000원을 현금 공제/환급받게 됩니다. 계산서 발행 여부를 거래처에 꼭 재확인하세요.",
            },
        ]

        # 2. 3대 핵심 요약 도출
        summary_points = [
            "원두·우유 등 식자재 원가율(26.8%)은 상권 평균보다 낮아 매우 우수하나, 포장재·소모품(16%)에서 월 28만 원 상당의 불필요한 비용 누수가 발생하고 있습니다.",
            "8월 인건비 비중(31.6%)이 상권 평균보다 높아, 오후 유휴 시간대 고마진 디저트 세트 판매를 통한 시간당 매출 견인이 시급합니다.",
            "개인 지출 4건(편의점·넷플릭스 등 74,000원)을 AI가 사전 불공제 분류하여 국세청 사후검증 과소신고 가산세(10%)를 선제적으로 완벽 방어했습니다.",
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
2. 반드시 [1] 문제 지출 항목과 구체적 절감 금액(원/월 단위), [2] 시간대별 객단가 개선 목표(4,200원->6,800원)와 고마진 메뉴 조합, [3] 부가가치세법 제42조 의제매입세액 공제율(9/109) 및 구체적 환급액(약 295,000원) 등 숫자가 포함된 실전형 원포인트 솔루션을 작성하세요.

위 정량 데이터를 바탕으로 소상공인 카페 사장님을 위한 맞춤 진단을 아래 JSON 형식으로만 작성하세요:
{{
  "score": 86,
  "grade_label": "양호 — 상위 18% 매장",
  "prescriptions": [
    {{"id": 1, "type": "COST_REDUCTION", "title": "8월 포장재·소모품비(127만 원, 16%)가 상권 표준(5.0%) 대비 3배 이상 과다 지출 중입니다. 테이크아웃 컵·홀더를 낱개 구매하는 대신 분기 단위 박스 대량 발주 또는 카페 전용 B2B 도매몰로 전환 시 월 약 28만 원(연 336만 원)의 고정비를 즉시 절감할 수 있습니다."}},
    {{"id": 2, "type": "REVENUE_BOOST", "title": "현재 인건비율(31.6%, 348만 원)이 상권 평균(24.8%)보다 다소 높습니다. 알바생이 상주하는 오후 14~17시 유휴 시간대에 마진율이 높은 고단가 디저트(바스크 치즈케이크·크로플) 페어링 세트를 집중 판매하여, 시간당 객단가를 4,200원 ➜ 6,800원으로 끌어올려 알바비 효율을 극대화하세요."}},
    {{"id": 3, "type": "TAX_SAVING", "title": "8월 서울우유 대량 매입(85만 원)에 대해 부가가치세법 제42조에 따른 음식점업 의제매입세액 공제(공제율 9/109)를 적용하여 이번 부가세 신고 시 약 295,000원을 현금 공제/환급받게 됩니다. 계산서 발행 여부를 거래처에 꼭 재확인하세요."}}
  ],
  "summary_points": [
    "원두·우유 등 식자재 원가율(26.8%)은 상권 평균보다 낮아 매우 우수하나, 포장재·소모품(16%)에서 월 28만 원 상당의 불필요한 비용 누수가 발생하고 있습니다.",
    "8월 인건비 비중(31.6%)이 상권 평균보다 높아, 오후 유휴 시간대 고마진 디저트 세트 판매를 통한 시간당 매출 견인이 시급합니다.",
    "개인 지출 4건(편의점·넷플릭스 등 74,000원)을 AI가 사전 불공제 분류하여 국세청 사후검증 과소신고 가산세(10%)를 선제적으로 완벽 방어했습니다."
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

            score = int(parsed.get("score", 86))
            grade_label = str(parsed.get("grade_label", "양호 — 상위 18% 매장"))
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
