"""CODEF 인증과 상품 API 요청을 공통 처리한다.

- Access Token 발급
- CODEF 상품 API 요청
- CODEF 응답 디코딩 및 JSON 변환

요청·응답 인코딩은 CODEF 공식 Python SDK와 같은 방식을 사용한다.
"""

import base64
import json
from urllib.parse import quote, unquote_plus

import requests
from Crypto.Cipher import PKCS1_v1_5
from Crypto.PublicKey import RSA
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

        # 공식 SDK와 동일한 전송 형식을 유지하도록 본문을 URL 인코딩한다.
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
            # URL 인코딩된 CODEF 응답을 복원한 뒤 JSON으로 변환한다.
            return json.loads(
                unquote_plus(response.text)
            )
        except json.JSONDecodeError as exc:
            raise CodefClientError(
                f"CODEF 응답을 JSON으로 해석할 수 없습니다: {exc}"
            ) from exc
            


def encrypt_with_public_key(text: str) -> str:
    """CODEF 공개키로 민감한 요청값을 RSA 암호화한다.

    공식 SDK와 호환되도록 PKCS1 v1.5 패딩과 Base64 DER 공개키 형식을 사용한다.
    """

    if not settings.CODEF_PUBLIC_KEY:
        raise CodefClientError(
            "CODEF_PUBLIC_KEY가 설정되지 않았습니다. .env를 확인하세요."
        )

    try:
        key_der = base64.b64decode(settings.CODEF_PUBLIC_KEY)
        public_key = RSA.importKey(key_der)
        cipher = PKCS1_v1_5.new(public_key)
        cipher_text = cipher.encrypt(text.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise CodefClientError(
            f"CODEF_PUBLIC_KEY로 RSA 암호화에 실패했습니다: {exc}"
        ) from exc

    return base64.b64encode(cipher_text).decode("utf-8")


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
    """최초 요청값을 보존하면서 추가인증 재요청값을 구성한다."""
    return {
        **base_payload,
        "simpleAuth": simple_auth,
        "is2Way": True,
        "twoWayInfo": two_way_info,
    }
