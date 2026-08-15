"""사업종류별 산재보험료율 매핑.

출처: 고용노동부 고시, 2026년도 사업종류별 산재보험료율.
Business.business_type/business_item은 자유 텍스트라 정확한 사업종류 코드 매칭이
불가능함 — 키워드 포함 여부로 근사 매칭하고, 매칭 안 되면 기본값(도소매·음식·숙박업)을
사용. 실제 산재보험료율은 근로복지공단이 사업의 실질 내용을 보고 별도로 부여하므로,
이 매핑은 참고용 근사치이며 정확한 요율은 사업장이 근로복지공단에 등록한 사업종류
코드를 확인해야 함 (TODO: businesses 앱에 사업종류 코드 필드가 생기면 그걸로 대체).
"""

DEFAULT_RATE = 0.008  # 도소매·음식·숙박업 (매칭 안 될 때 기본값)

# (키워드 목록, 요율) 순서대로 검사 — 위에서부터 먼저 매칭되는 것을 사용
_KEYWORD_RATES = [
    (["제조", "가공", "생산", "공장"], 0.013),
    (["건설", "공사", "인테리어"], 0.034),
    (["운수", "운송", "배달", "택배"], 0.017),
    (["숙박", "음식", "카페", "커피", "제과", "베이커리", "식당", "레스토랑", "판매", "도매", "소매"], 0.008),
    (["금융", "보험", "부동산"], 0.006),
    (["정보", "통신", "IT", "소프트웨어", "서비스업"], 0.007),
]


def get_industrial_accident_rate(business) -> float:
    """Business의 업태/종목 텍스트를 보고 산재보험료율(사업종류별 요율만, 출퇴근재해요율 제외)을 추정."""
    text = f"{business.business_type or ''} {business.business_item or ''}"

    for keywords, rate in _KEYWORD_RATES:
        if any(keyword in text for keyword in keywords):
            return rate

    return DEFAULT_RATE