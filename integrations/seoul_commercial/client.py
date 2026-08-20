import json
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class SeoulCommercialClientError(Exception):
    """서울시 상권분석 OpenAPI 호출 오류."""
    pass


class SeoulCommercialClient:
    """서울 열린데이터광장 상권분석 OpenAPI 클라이언트.

    엔드포인트:
    http://openapi.seoul.go.kr:8088/{KEY}/json/VwsmTrdarSelngQq/{START_INDEX}/{END_INDEX}/
    """

    SERVICE_ESTIMATED_SALES = "VwsmTrdarSelngQq"  # 상권-추정매출
    COFFEE_INDUTY_CODE = "CS100010"               # 커피-음료 업종 코드

    def __init__(self, api_key: str = None, base_url: str = None, timeout: float = None):
        self.api_key = api_key if api_key is not None else getattr(settings, "SEOUL_DATA_API_KEY", "")
        self.base_url = (base_url or getattr(settings, "SEOUL_DATA_API_BASE_URL", "http://openapi.seoul.go.kr:8088")).rstrip("/")
        self.timeout = timeout or getattr(settings, "SEOUL_DATA_TIMEOUT_SECONDS", 10.0)

    def fetch_estimated_sales(self, start_index: int = 1, end_index: int = 50, induty_code: str = COFFEE_INDUTY_CODE) -> list[dict]:
        """서울시 상권분석 추정매출 데이터를 조회하고 커피-음료 업종만 필터링하여 반환한다."""
        if not self.api_key:
            raise SeoulCommercialClientError("SEOUL_DATA_API_KEY가 설정되지 않았습니다.")

        url = f"{self.base_url}/{self.api_key}/json/{self.SERVICE_ESTIMATED_SALES}/{start_index}/{end_index}/"
        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            # requests 예외 문자열에는 인증키가 포함된 전체 URL이 들어갈 수 있다.
            # 로그·관리 명령 출력·디버그 예외 체인 어디에도 원본 URL을 남기지 않는다.
            logger.warning("서울시 OpenAPI 요청 실패 (%s)", type(exc).__name__)
            raise SeoulCommercialClientError(
                "서울시 상권분석 API 연결에 실패했습니다. 네트워크 상태와 API 키를 확인해 주세요."
            ) from None
        except json.JSONDecodeError as exc:
            raise SeoulCommercialClientError(f"서울시 응답 JSON 파싱 실패: {exc}") from exc

        root = data.get(self.SERVICE_ESTIMATED_SALES) or {}
        result = root.get("RESULT") or {}
        if result.get("CODE") != "INFO-000":
            msg = result.get("MESSAGE", "알 수 없는 오류")
            raise SeoulCommercialClientError(f"서울시 API 오류 ({result.get('CODE')}): {msg}")

        rows = root.get("row") or []
        if induty_code:
            rows = [row for row in rows if row.get("SVC_INDUTY_CD") == induty_code]
        return rows
