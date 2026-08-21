"""OpenAI 클라이언트의 생성 설정을 한곳에서 관리한다."""

from django.conf import settings
from openai import OpenAI


def get_client(*, client: OpenAI | None = None) -> OpenAI:
    """주입된 클라이언트를 우선 사용하고, 없으면 설정값으로 생성한다.

    Args:
        client: 테스트나 호출부에서 주입한 OpenAI 클라이언트.

    Returns:
        재사용하거나 새로 생성한 OpenAI 클라이언트.
    """
    if client is not None:
        return client
    return OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=getattr(settings, "OPENAI_TIMEOUT_SECONDS", 20.0),
    )
