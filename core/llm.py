"""OpenAI 클라이언트 생성의 단일 진실 공급원.

chat, benchmark(진단/심층진단), transactions(자동분류) 4곳에서 각자
`OpenAI(api_key=..., timeout=...)`를 반복 생성하던 것을 여기 하나로 모은다.
타임아웃 정책이나 클라이언트 생성 방식을 바꿀 때 이 파일만 고치면 된다.
"""

from django.conf import settings
from openai import OpenAI


def get_client(*, client: OpenAI | None = None) -> OpenAI:
    """이미 주입된 client(테스트에서 mock을 넣는 경우 등)가 있으면 그대로 반환하고,
    없으면 settings의 OPENAI_API_KEY/OPENAI_TIMEOUT_SECONDS로 새로 만든다."""
    if client is not None:
        return client
    return OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=getattr(settings, "OPENAI_TIMEOUT_SECONDS", 20.0),
    )
