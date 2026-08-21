"""`manage.py check`에서 데모 관련 배포 설정을 점검한다."""

from django.conf import settings
from django.core.checks import Warning as CheckWarning, register


@register()
def demo_mode_warning(app_configs, **kwargs):
    """데모 모드가 활성화된 환경에 경고를 표시한다."""
    if not getattr(settings, "DEMO_MODE", False):
        return []
    return [
        CheckWarning(
            "DEMO_MODE가 활성화되어 있습니다. Authorization 헤더 없는 요청이 "
            "데모 계정으로 인증되며 is_demo=True 사업장에 접근할 수 있습니다.",
            hint="실서비스로 전환할 때 .env에 DEMO_MODE=0 을 설정하세요.",
            id="caffeine.W001",
        )
    ]


@register()
def unowned_business_access_warning(app_configs, **kwargs):
    """소유자 없는 사업장 접근이 테스트 밖에서 허용되지 않게 경고한다."""
    if not getattr(settings, "ALLOW_UNOWNED_BUSINESS_ACCESS", False):
        return []
    return [
        CheckWarning(
            "ALLOW_UNOWNED_BUSINESS_ACCESS가 활성화되어 있습니다. owner가 지정되지 "
            "않은 사업장에 인증된 아무 사용자나 접근할 수 있습니다.",
            hint="이 값은 테스트 런타임에서만 True여야 합니다.",
            id="caffeine.W002",
        )
    ]
