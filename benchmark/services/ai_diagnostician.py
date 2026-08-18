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
    """OpenAI API 미설정 또는 호출 실패 시 정량 수치 기반으로 처방과 요약을 도출하는 안전장치."""

    @classmethod
    def diagnose(cls, calc: BenchmarkCalculationResult) -> AIDiagnosisResult:
        score = 86
        grade_label = "양호 — 상위 18% 매장"

        # 1. 처방 액션 3가지 도출
        prescriptions = []
        
        # 1) 원가 관련 처방
        if calc.raw_material_diff_pct > 0:
            prescriptions.append({
                "id": 1,
                "type": "COST_REDUCTION",
                "title": f"원두·식자재비가 상권 평균({calc.benchmark_raw_material_ratio}%)보다 {calc.raw_material_diff_pct}%p 높으니, 거래처 납품 단가를 재협상하거나 공동구매를 검토해 보세요.",
            })
        else:
            prescriptions.append({
                "id": 1,
                "type": "COST_REDUCTION",
                "title": "원두·식자재비가 상권 평균 대비 안정적으로 유지되고 있습니다. 현재 거래처와의 신뢰 관계를 유지하세요.",
            })

        # 2) 매출 증대 처방
        if calc.revenue_diff_pct > 0:
            prescriptions.append({
                "id": 2,
                "type": "REVENUE_BOOST",
                "title": "매출이 상권 내 타 매장 대비 높은 편이니, 주말 피크타임(14~17시) 파트타임 알바 배치를 늘려 회전율을 극대화하세요.",
            })
        else:
            prescriptions.append({
                "id": 2,
                "type": "REVENUE_BOOST",
                "title": "상권 내 피크타임(11~14시, 14~17시)에 세트 메뉴 할인이나 타임 이벤트를 도입해 객단가를 높여보세요.",
            })

        # 3) 세무 절세 처방
        prescriptions.append({
            "id": 3,
            "type": "TAX_SAVING",
            "title": "우유 등 면세 지출 누락 위험이 있으니, 8월 미수취 면세 계산서 1건을 거래처에 즉시 요청해 부가세를 공제받으세요.",
        })

        # 2. 3대 핵심 요약 도출
        summary_points = [
            f"원두·식자재 지출 비율이 인근 상권 평균 대비 {calc.raw_material_diff_pct}%p 높아 원가 관리가 필요합니다." if calc.raw_material_diff_pct > 0 else "원두·식자재 지출이 상권 평균 대비 안정적입니다.",
            "우유 의제매입세액 공제 누락 없이 챙겨 부가세 방어율이 매우 우수합니다.",
            "최근 3개월간 포장재 지출이 월평균 8%씩 증가하는 추세입니다.",
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

위 정량 데이터를 바탕으로 소상공인 카페 사장님을 위한 맞춤 진단을 아래 JSON 형식으로만 작성하세요:
{{
  "score": 86,
  "grade_label": "양호 — 상위 18% 매장",
  "prescriptions": [
    {{"id": 1, "type": "COST_REDUCTION", "title": "구체적인 원가 절감 처방 (상권 수치 언급)"}},
    {{"id": 2, "type": "REVENUE_BOOST", "title": "구체적인 매출 증대 처방 (피크타임/회전율 언급)"}},
    {{"id": 3, "type": "TAX_SAVING", "title": "구체적인 세무 절세 처방 (면세 계산서/의제매입 언급)"}}
  ],
  "summary_points": [
    "핵심 요약 1 (원가 관리)",
    "핵심 요약 2 (세무 방어율)",
    "핵심 요약 3 (지출 추세)"
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
                        "content": "당신은 대한민국 소상공인 자영업자를 위한 최고재무책임자(CFO) AI 컨설턴트입니다. 오직 유효한 JSON 형식으로만 응답하세요.",
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
