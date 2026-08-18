"""CODEF API 통신을 담당하는 공통 클라이언트.

- Access Token 발급
- CODEF 상품 API 요청
- CODEF 응답 디코딩 및 JSON 변환

요청/응답 인코딩 방식은 CODEF 공식 Python SDK(easycodefpy)를 따른다.
"""

import json
from urllib.parse import quote, unquote_plus

import requests
from django.conf import settings
from requests.auth import HTTPBasicAuth


class CodefClientError(Exception):
    """CODEF 설정 또는 응답 처리 중 발생하는 예외."""


class CodefClient:
    TOKEN_URL = "https://oauth.codef.io/oauth/token"

    def get_access_token(self) -> str:
        """Client ID/Secret으로 CODEF Access Token을 발급한다."""

        if not settings.CODEF_CLIENT_ID:
            raise CodefClientError(
                "CODEF_CLIENT_ID가 설정되지 않았습니다. .env를 확인하세요."
            )

        if not settings.CODEF_CLIENT_SECRET:
            raise CodefClientError(
                "CODEF_CLIENT_SECRET이 설정되지 않았습니다. .env를 확인하세요."
            )

        response = requests.post(
            self.TOKEN_URL,
            auth=HTTPBasicAuth(
                settings.CODEF_CLIENT_ID,
                settings.CODEF_CLIENT_SECRET,
            ),
            data={
                "grant_type": "client_credentials",
                "scope": "read",
            },
            headers={
                "Accept": "application/json",
            },
            timeout=settings.CODEF_TIMEOUT_SECONDS,
        )

        response.raise_for_status()
        data = response.json()

        access_token = data.get("access_token")

        if not access_token:
            raise CodefClientError(
                "CODEF Access Token 응답에 access_token이 없습니다."
            )

        return access_token

    def post(self, path: str, payload: dict) -> dict:
        """CODEF 상품 API를 호출하고 JSON 응답을 반환한다."""

        if not settings.CODEF_API_BASE_URL:
            raise CodefClientError(
                "CODEF_API_BASE_URL이 설정되지 않았습니다. .env를 확인하세요."
            )

        token = self.get_access_token()

        # CODEF 공식 SDK 방식에 맞춰 요청 본문을 URL 인코딩한다.
        body_str = quote(
            json.dumps(payload, ensure_ascii=False)
        )

        response = requests.post(
            f"{settings.CODEF_API_BASE_URL}{path}",
            data=body_str,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
            timeout=settings.CODEF_TIMEOUT_SECONDS,
        )

        response.raise_for_status()

        try:
            # CODEF 응답을 URL 디코딩한 뒤 JSON으로 변환한다.
            return json.loads(
                unquote_plus(response.text)
            )
        except json.JSONDecodeError as exc:
            raise CodefClientError(
                f"CODEF 응답을 JSON으로 해석할 수 없습니다: {exc}"
            ) from exc
            
TWO_WAY_REQUIRED_CODE = "CF-03002"


def is_two_way_required(raw: dict) -> bool:
    """CODEF 응답이 추가인증(2-way)을 요구하는 상태인지 확인한다."""
    result = raw.get("result") or {}
    data = raw.get("data") or {}
    return (
        result.get("code") == TWO_WAY_REQUIRED_CODE
        and bool(data.get("continue2Way"))
    )


def extract_two_way_info(raw: dict) -> dict:
    """추가인증 재요청에 필요한 값을 CODEF 응답에서 꺼낸다."""
    data = raw.get("data") or {}
    return {
        "jobIndex": data.get("jobIndex"),
        "threadIndex": data.get("threadIndex"),
        "jti": data.get("jti"),
        "twoWayTimestamp": data.get("twoWayTimestamp"),
    }


def build_two_way_payload(base_payload: dict, two_way_info: dict, simple_auth: str,) -> dict:
    """1차 요청 payload에 추가인증 정보를 덧붙인 2차 요청 payload를 만든다."""
    return {
        **base_payload,
        "simpleAuth": simple_auth,
        "is2Way": True,
        "twoWayInfo": two_way_info,
    }