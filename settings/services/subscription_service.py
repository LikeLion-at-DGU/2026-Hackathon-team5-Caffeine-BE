import calendar
from datetime import date, timedelta

from django.utils import timezone

from businesses.models import Business
from settings.exceptions import AlreadyCancelled, PaymentMethodUpdateFailed, SubscriptionNotFound
from settings.models import Subscription
from settings.payment_gateway.factory import get_payment_gateway
from settings.services.billing_key_encryption import decrypt_billing_key, encrypt_billing_key


def get_subscription(business_id: int) -> Subscription:
    subscription, _created = Subscription.objects.get_or_create(
        business_id=business_id,
        defaults={"next_billing_date": timezone.now().date() + timedelta(days=30)},
    )
    return subscription


def update_payment_method(business_id: int, payment_token: str) -> Subscription:
    subscription = get_subscription(business_id)

    gateway = get_payment_gateway()
    result = gateway.issue_billing_key(payment_token)

    if not result.get("billing_key"):
        raise PaymentMethodUpdateFailed()

    subscription.billing_key_encrypted = encrypt_billing_key(result["billing_key"])
    subscription.card_company = result["card_company"]
    subscription.card_last4 = result["card_last4"]

    # 결제 실패(PAST_DUE) 상태였다면, 카드를 새로 등록한 시점에 바로 정상화한다.
    # (다음 cron 실행까지 기다리지 않고 결제 수단 갱신 즉시 이용 재개)
    # TODO: EXPIRED(구독 취소 후 만료됨) 상태에서의 "재구독" 흐름은 범위 밖 — 지금은 카드를
    # 새로 등록해도 EXPIRED 상태가 그대로 유지된다. 재구독 정책(플랜 재선택 등)이 정해지면
    # 여기에 EXPIRED -> ACTIVE 전환 + next_billing_date 재설정 로직을 추가해야 한다.
    if subscription.status == "PAST_DUE":
        subscription.status = "ACTIVE"
        subscription.last_payment_error = ""

    subscription.save()
    return subscription


def cancel_subscription(business_id: int) -> Subscription:
    subscription = get_subscription(business_id)

    if subscription.status in ("CANCELLED", "EXPIRED"):
        raise AlreadyCancelled()

    today = timezone.now().date()
    subscription.status = "CANCELLED"
    subscription.cancelled_at = today
    subscription.access_until = subscription.next_billing_date  # 남은 기간까지 이용 가능 (환불 없음)
    subscription.save()
    return subscription


def _add_one_month(d: date) -> date:
    """d 기준 정확히 한 달 뒤 날짜. 말일 케이스(1/31 -> 2/28 등)는 그 달의 마지막 날로 clamp."""
    year = d.year + (d.month // 12)
    month = d.month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return d.replace(year=year, month=month, day=day)


def run_due_billing(today: date | None = None) -> dict:
    """정기 결제(자동 갱신) 배치. cron(run_billing_cycle 커맨드)에서 매일 호출된다.

    ACTIVE 또는 PAST_DUE 상태이면서 next_billing_date가 도래한 구독을 대상으로,
    등록된 결제 수단으로 mock 결제를 시도한다.
    - 성공: next_billing_date를 한 달 뒤로 갱신하고 ACTIVE로 복구, 실패 사유 초기화
    - 실패(또는 결제 수단 없음): PAST_DUE로 전환하고 사유를 기록 (next_billing_date는 그대로 두어
      다음 cron 실행 때 재시도됨)
    """
    today = today or timezone.now().date()
    gateway = get_payment_gateway()

    due_subscriptions = list(
        Subscription.objects.filter(
            status__in=["ACTIVE", "PAST_DUE"],
            next_billing_date__lte=today,
        )
    )

    charged = 0
    failed = 0

    for subscription in due_subscriptions:
        if not subscription.billing_key_encrypted:
            subscription.status = "PAST_DUE"
            subscription.last_payment_error = "등록된 결제 수단이 없습니다."
            subscription.save()
            failed += 1
            continue

        billing_key = decrypt_billing_key(subscription.billing_key_encrypted)
        result = gateway.charge(billing_key, subscription.price)

        if result.get("success"):
            subscription.status = "ACTIVE"
            subscription.last_payment_error = ""
            subscription.next_billing_date = _add_one_month(subscription.next_billing_date)
            subscription.save()
            charged += 1
        else:
            subscription.status = "PAST_DUE"
            subscription.last_payment_error = result.get("error") or "결제에 실패했습니다."
            subscription.save()
            failed += 1

    return {"charged": charged, "failed": failed, "total": len(due_subscriptions)}


def expire_lapsed_cancellations(today: date | None = None) -> int:
    """CANCELLED 상태이면서 access_until이 지난 구독을 EXPIRED로 전환한다."""
    today = today or timezone.now().date()
    return Subscription.objects.filter(status="CANCELLED", access_until__lt=today).update(status="EXPIRED")
