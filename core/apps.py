from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        # 배포 설정 자기 점검 등록 (manage.py check에서 실행)
        from core import checks  # noqa: F401
