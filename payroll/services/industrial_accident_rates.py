"""사업장 업태·종목으로 산재보험료율을 추정한다.

사업종류 코드가 없는 현재 데이터 구조에서는 2026년 고용노동부 고시의 업종을
키워드로 근사한다. 일치하는 업종이 없으면 도소매·음식·숙박업 요율을 사용한다.
"""

DEFAULT_RATE = 0.008  # 도소매·음식·숙박업 기본 요율

# 구체적인 업종을 먼저 배치해 첫 번째 일치 요율을 사용한다.
_KEYWORD_RATES = [
    (["제조", "가공", "생산", "공장"], 0.013),
    (["건설", "공사", "인테리어"], 0.034),
    (["운수", "운송", "배달", "택배"], 0.017),
    (["숙박", "음식", "카페", "커피", "제과", "베이커리", "식당", "레스토랑", "판매", "도매", "소매"], 0.008),
    (["금융", "보험", "부동산"], 0.006),
    (["정보", "통신", "IT", "소프트웨어", "서비스업"], 0.007),
]


def get_industrial_accident_rate(business) -> float:
    """사업장 업태·종목에서 출퇴근재해 요율을 제외한 산재 요율을 추정한다."""
    text = f"{business.business_type or ''} {business.business_item or ''}"

    for keywords, rate in _KEYWORD_RATES:
        if any(keyword in text for keyword in keywords):
            return rate

    return DEFAULT_RATE
