from datetime import timedelta

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
    subscription.save()
    return subscription


def cancel_subscription(business_id: int) -> Subscription:
    subscription = get_subscription(business_id)

    if subscription.status == "CANCELLED":
        raise AlreadyCancelled()

    today = timezone.now().date()
    subscription.status = "CANCELLED"
    subscription.cancelled_at = today
    subscription.access_until = subscription.next_billing_date  # 남은 기간까지 이용 가능 (환불 없음)
    subscription.save()
    return subscription