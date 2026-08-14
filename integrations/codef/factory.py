from django.conf import settings


def get_codef_provider():
    """설정된 CODEF_MODE에 따라 사용할 Provider를 반환한다."""
    from .mock import MockCodefProvider
    from .real import RealCodefProvider

    mode = getattr(settings, "CODEF_MODE", "mock")

    if mode == "mock":
        return MockCodefProvider()

    if mode == "real":
        return RealCodefProvider()

    raise ValueError(f"지원하지 않는 CODEF_MODE입니다: {mode!r}")