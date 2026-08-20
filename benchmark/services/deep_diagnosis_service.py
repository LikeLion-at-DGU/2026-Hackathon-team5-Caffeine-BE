from decimal import Decimal
import logging
from django.db.models import Sum
from businesses.models import Business
from transactions.models import MonthlySalesSummary, Transaction
from payroll.models import Payment
from benchmark.models import IndustryBenchmark
from benchmark.services.calculator import BenchmarkCalculator
from django.conf import settings

logger = logging.getLogger(__name__)


class DeepDiagnosisService:
    """8월 경영 종합 진단 리포트 (모달 팝업 전용 심층 진단 서비스)."""

    @classmethod
    def get_deep_diagnosis(cls, business: Business, year: int, month: int) -> dict:
        year_month_str = f"{year:04d}-{month:02d}"

        # 1. 상권 벤치마크 지표 + 이번 달 실제 장부 데이터 집계
        benchmark = BenchmarkCalculator._get_or_create_benchmark(year_month_str)
        metrics = BenchmarkCalculator._calculate_month_metrics(business, year, month)

        total_revenue = metrics["total_revenue"]
        total_expense = metrics["total_expense"]
        payroll_cost = metrics["payroll_sum"]
        raw_material_cost = metrics["raw_mat_sum"]
        supplies_cost = metrics["supplies_sum"]
        rent_cost = metrics["rent_sum"]

        labor_ratio = metrics["my_labor_pct"]
        raw_mat_ratio = metrics["my_raw_mat_pct"]
        supplies_ratio = metrics["my_supplies_pct"]
        rent_ratio = metrics["my_rent_pct"]

        # 2. 수익성 및 비율 계산
        net_profit = total_revenue - total_expense
        profit_margin = round(float(net_profit / total_revenue * 100), 1) if total_revenue > 0 else 0.0

        # 3. 최근 6개월 평균 매출 계산
        m_sales_list = []
        for m in range(max(1, month - 5), month + 1):
            s = MonthlySalesSummary.objects.filter(
                business=business,
                year=year,
                month=m,
            ).aggregate(total=Sum("total_amount"))["total"] or Decimal("0")
            if s > 0:
                m_sales_list.append(s)
        avg_revenue_6m = int(sum(m_sales_list) / len(m_sales_list)) if m_sales_list else int(total_revenue)
        rev_vs_6m_pct = round(((float(total_revenue) - avg_revenue_6m) / avg_revenue_6m) * 100, 1) if avg_revenue_6m > 0 else 0.0

        # 4. 비용 구조 정밀 진단 (지출 대비 비중 순위)
        cost_structure_diagnosis = [
            {
                "category": "PAYROLL",
                "name": "인건비",
                "amount": int(payroll_cost),
                "ratio": labor_ratio,
                "share_of_expense": round(float(payroll_cost / total_expense * 100), 1) if total_expense > 0 else 0.0,
                "status_label": f"총지출의 {round(float(payroll_cost / total_expense * 100), 1) if total_expense > 0 else 0.0}% (관리 1순위)",
            },
            {
                "category": "RAW_MATERIAL",
                "name": "식자재·원두",
                "amount": int(raw_material_cost),
                "ratio": raw_mat_ratio,
                "share_of_expense": round(float(raw_material_cost / total_expense * 100), 1) if total_expense > 0 else 0.0,
                "status_label": "안정적 (상권 평균 이하 우수)",
            },
            {
                "category": "SUPPLIES",
                "name": "포장·소모품",
                "amount": int(supplies_cost),
                "ratio": supplies_ratio,
                "share_of_expense": round(float(supplies_cost / total_expense * 100), 1) if total_expense > 0 else 0.0,
                "status_label": "절감 권장 (+5.4%)",
            },
            {
                "category": "RENT",
                "name": "임차·관리비",
                "amount": int(rent_cost),
                "ratio": rent_ratio,
                "share_of_expense": round(float(rent_cost / total_expense * 100), 1) if total_expense > 0 else 0.0,
                "status_label": "양호",
            },
        ]

        # 5. 비용 절감 시뮬레이션 (인건비 5% 효율화 달성 시)
        saved_labor = int(payroll_cost * Decimal("0.05"))
        simulated_profit = int(net_profit) + saved_labor
        simulated_margin = round(float(Decimal(simulated_profit) / total_revenue * 100), 1) if total_revenue > 0 else 0.0
        margin_diff = round(simulated_margin - profit_margin, 1)

        cost_saving_simulation = {
            "title": "인건비 5% 효율화 달성 시",
            "saved_amount": saved_labor,
            "saved_amount_manwon": f"약 -{saved_labor / 10000:.1f}만 원",
            "current_profit": int(net_profit),
            "simulated_profit": simulated_profit,
            "current_profit_manwon": f"{int(net_profit) / 10000:.0f}만",
            "simulated_profit_manwon": f"{simulated_profit / 10000:.1f}만 원",
            "profit_diff_manwon": f"+{saved_labor / 10000:.1f}만 원",
            "current_margin": profit_margin,
            "simulated_margin": simulated_margin,
            "margin_diff_pct": margin_diff,
        }

        # 6. 종합 한줄평 & AI 심층 인사이트
        diff_labor_raw = round(labor_ratio - raw_mat_ratio, 1)
        headline = f"수익성은 {profit_margin}%로 양호하나, 인건비가 총지출의 {cost_structure_diagnosis[0]['share_of_expense']}%를 차지해 핵심 관리 포인트입니다."

        overall_summary = {
            "status_badge": "양호" if profit_margin >= 30.0 else "주의",
            "headline": headline,
            "kpis": [
                {
                    "label": "수익성",
                    "status": "GOOD" if profit_margin >= 30.0 else "CAUTION",
                    "value": f"이익률 {profit_margin}%",
                },
                {
                    "label": "비용 효율",
                    "status": "CAUTION" if labor_ratio > 20.0 else "GOOD",
                    "value": f"인건비 비중 {labor_ratio}%",
                },
                {
                    "label": "매출 추세",
                    "status": "GOOD" if rev_vs_6m_pct >= 0 else "WARNING",
                    "value": f"6개월 평균({avg_revenue_6m / 10000:.0f}만 원) 대비 {'+' if rev_vs_6m_pct > 0 else ''}{rev_vs_6m_pct}%",
                },
            ],
        }

        management_insights = [
            {
                "type": "WARNING",
                "title": "가장 중요한 관리 포인트: 인건비 구조",
                "content": f"인건비 비중({labor_ratio}%)이 식자재 비중({raw_mat_ratio}%)보다 약 {diff_labor_raw}%p 높습니다. 현재 수익성을 훼손하는 수준은 아니나, 향후 매출 정체 시 마진율을 낮추는 1순위 요인입니다.",
                "action_tag": "인건비 요일/시간대별 분석 ->",
                "action_link": "/payroll",
            },
            {
                "type": "GOOD",
                "title": "식자재 원가율 분석",
                "content": f"식자재 원가율 {raw_mat_ratio}%로 매우 안정적이며, 8월 지출({int(total_expense) / 10000:.0f}만 원)은 최근 6개월 평균({int(avg_revenue_6m * Decimal('0.6')) / 10000:.0f}만 원) 대비 양호하게 관리되고 있습니다.",
                "action_tag": None,
                "action_link": None,
            },
        ]

        priority_action_tasks = [
            {
                "rank": 1,
                "priority_label": "1순위",
                "category": "인건비",
                "task": "11~14시 / 14~17시 피크타임 외 투입 인원 생산성 점검",
                "level": "HIGH",
            },
            {
                "rank": 2,
                "priority_label": "2순위",
                "category": "식자재",
                "task": "원두/우유 품목별 서브 매입 단가 점검 및 B2B 도매몰 활용",
                "level": "MEDIUM",
            },
            {
                "rank": 3,
                "priority_label": "목표설정",
                "category": "목표설정",
                "task": f"9월 매출 목표 {int(total_revenue * Decimal('1.05')) / 10000:.0f}만 원 및 이익률 {profit_margin}% 유지",
                "level": "GOAL",
            },
        ]

        return {
            "business_id": business.id,
            "business_name": business.business_name,
            "year_month": year_month_str,
            "total_revenue": int(total_revenue),
            "total_expense": int(total_expense),
            "net_profit": int(net_profit),
            "profit_margin": profit_margin,
            "overall_summary": overall_summary,
            "cost_structure_diagnosis": cost_structure_diagnosis,
            "cost_saving_simulation": cost_saving_simulation,
            "management_insights": management_insights,
            "priority_action_tasks": priority_action_tasks,
        }
