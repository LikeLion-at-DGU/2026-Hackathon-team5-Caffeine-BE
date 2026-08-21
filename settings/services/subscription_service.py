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

    # 결제수단 교체 즉시 이용을 재개하되, 만료된 구독은 재구독 정책 없이 복구하지 않는다.
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
    # 이미 결제한 이용 기간은 취소 후에도 보장한다.
    subscription.access_until = subscription.next_billing_date
    subscription.save()
    return subscription


def _add_one_month(d: date) -> date:
    """결제일을 한 달 뒤로 옮기고, 없는 날짜는 해당 월 말일로 맞춘다."""
    year = d.year + (d.month // 12)
    month = d.month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return d.replace(year=year, month=month, day=day)


def run_due_billing(today: date | None = None) -> dict:
    """결제일이 지난 구독의 정기 결제를 처리한다.

    - 성공: 다음 결제일 갱신 및 정상 상태 복구
    - 실패: 실패 사유 기록 후 다음 배치에서 재시도

    Args:
        today: 배치 기준일. 생략하면 서버의 현재 날짜를 사용한다.

    Returns:
        성공·실패·전체 처리 건수.
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
    """이용 기간이 끝난 취소 구독을 만료 상태로 전환한다."""
    today = today or timezone.now().date()
    return Subscription.objects.filter(status="CANCELLED", access_until__lt=today).update(status="EXPIRED")
