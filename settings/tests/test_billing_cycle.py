import base64
import json
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from businesses.models import Business
from settings.models import Subscription
from settings.services import subscription_service
from settings.services.subscription_service import _add_one_month


def _encode_token(payload: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")


NORMAL_TOKEN = _encode_token({"card_company": "국민카드(가상)", "card_last4": "5678", "scenario": None})
CHARGE_FAIL_TOKEN = _encode_token({"card_company": "국민카드(가상)", "card_last4": "0341", "scenario": "CHARGE_FAIL"})


class RunDueBillingTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(business_name="카페비서 1호점")
        self.today = timezone.now().date()

    def test_charges_active_subscription_and_advances_next_billing_date(self):
        subscription_service.update_payment_method(self.business.id, NORMAL_TOKEN)
        subscription = Subscription.objects.get(business=self.business)
        subscription.next_billing_date = self.today
        subscription.save()

        result = subscription_service.run_due_billing(self.today)

        subscription.refresh_from_db()
        self.assertEqual(result, {"charged": 1, "failed": 0, "total": 1})
        self.assertEqual(subscription.status, "ACTIVE")
        self.assertEqual(subscription.last_payment_error, "")
        self.assertEqual(subscription.next_billing_date, _add_one_month(self.today))

    def test_marks_past_due_on_charge_failure_and_keeps_next_billing_date_for_retry(self):
        subscription_service.update_payment_method(self.business.id, CHARGE_FAIL_TOKEN)
        subscription = Subscription.objects.get(business=self.business)
        subscription.next_billing_date = self.today
        subscription.save()

        result = subscription_service.run_due_billing(self.today)

        subscription.refresh_from_db()
        self.assertEqual(result, {"charged": 0, "failed": 1, "total": 1})
        self.assertEqual(subscription.status, "PAST_DUE")
        self.assertTrue(subscription.last_payment_error)
        # 실패한 건은 다음 cron에서 재시도할 수 있도록 next_billing_date를 그대로 둔다.
        self.assertEqual(subscription.next_billing_date, self.today)

    def test_marks_past_due_when_no_payment_method_registered(self):
        subscription = subscription_service.get_subscription(self.business.id)
        subscription.next_billing_date = self.today
        subscription.save()

        result = subscription_service.run_due_billing(self.today)

        subscription.refresh_from_db()
        self.assertEqual(result, {"charged": 0, "failed": 1, "total": 1})
        self.assertEqual(subscription.status, "PAST_DUE")
        self.assertEqual(subscription.last_payment_error, "등록된 결제 수단이 없습니다.")

    def test_ignores_subscriptions_not_yet_due(self):
        subscription = subscription_service.get_subscription(self.business.id)
        subscription.next_billing_date = self.today + timedelta(days=5)
        subscription.save()

        result = subscription_service.run_due_billing(self.today)

        self.assertEqual(result, {"charged": 0, "failed": 0, "total": 0})

    def test_update_payment_method_reactivates_past_due_subscription(self):
        subscription_service.update_payment_method(self.business.id, CHARGE_FAIL_TOKEN)
        subscription = Subscription.objects.get(business=self.business)
        subscription.next_billing_date = self.today
        subscription.save()
        subscription_service.run_due_billing(self.today)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, "PAST_DUE")

        subscription_service.update_payment_method(self.business.id, NORMAL_TOKEN)

        subscription.refresh_from_db()
        self.assertEqual(subscription.status, "ACTIVE")
        self.assertEqual(subscription.last_payment_error, "")


class ExpireLapsedCancellationsTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(business_name="카페비서 1호점")
        self.today = timezone.now().date()

    def test_expires_cancelled_subscription_past_access_until(self):
        subscription = subscription_service.get_subscription(self.business.id)
        subscription.status = "CANCELLED"
        subscription.access_until = self.today - timedelta(days=1)
        subscription.save()

        count = subscription_service.expire_lapsed_cancellations(self.today)

        subscription.refresh_from_db()
        self.assertEqual(count, 1)
        self.assertEqual(subscription.status, "EXPIRED")

    def test_does_not_expire_cancelled_subscription_still_within_access_period(self):
        subscription = subscription_service.get_subscription(self.business.id)
        subscription.status = "CANCELLED"
        subscription.access_until = self.today
        subscription.save()

        count = subscription_service.expire_lapsed_cancellations(self.today)

        subscription.refresh_from_db()
        self.assertEqual(count, 0)
        self.assertEqual(subscription.status, "CANCELLED")
