from django.core.management.base import BaseCommand
from django.utils import timezone

from settings.services.subscription_service import expire_lapsed_cancellations, run_due_billing


class Command(BaseCommand):
    """정기 결제와 취소 구독 만료를 실행하는 일일 배치.

    실제 운영에서는 서버 crontab에 다음과 같이 등록해 매일 새벽 한 번 실행한다.

        0 0 * * * cd /home/ubuntu/2026-Hackathon-team5-Caffeine-BE && \\
            venv/bin/python manage.py run_billing_cycle >> /home/ubuntu/logs/billing_cycle.log 2>&1

    별도 작업 큐 없이 Django 관리 명령과 운영체제의 Cron으로 실행한다.
    """

    help = "구독 정기 결제(자동 갱신)를 실행하고, 취소된 구독 중 이용 기간이 끝난 건을 만료 처리합니다."

    def handle(self, *args, **options):
        today = timezone.now().date()

        billing_result = run_due_billing(today)
        self.stdout.write(
            "[정기 결제] 대상 {total}건 중 성공 {charged}건, 실패 {failed}건".format(**billing_result)
        )

        expired_count = expire_lapsed_cancellations(today)
        self.stdout.write(f"[구독 만료] {expired_count}건을 EXPIRED로 전환했습니다.")

        self.stdout.write(self.style.SUCCESS("run_billing_cycle 완료"))
