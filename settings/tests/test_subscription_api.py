from django.test import TestCase
from rest_framework.test import APIClient

from businesses.models import Business
from settings.models import Subscription


class SubscriptionAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.business = Business.objects.create(business_name="카페비서")

    def test_get_subscription_auto_creates_on_first_access(self):
        response = self.client.get(f"/api/businesses/{self.business.id}/settings/subscription/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["plan_name"], "PRO")
        self.assertEqual(response.data["data"]["status"], "ACTIVE")
        self.assertTrue(Subscription.objects.filter(business=self.business).exists())

    def test_subscription_does_not_expose_billing_key(self):
        response = self.client.get(f"/api/businesses/{self.business.id}/settings/subscription/")
        self.assertNotIn("billing_key", response.data["data"])
        self.assertNotIn("billing_key_encrypted", response.data["data"])

    def test_update_payment_method_success(self):
        response = self.client.patch(
            f"/api/businesses/{self.business.id}/settings/subscription/payment-method/",
            {"payment_token": "tok_abc123"}, format="json",
        )

        self.assertEqual(response.status_code, 200)
        subscription = Subscription.objects.get(business=self.business)
        self.assertTrue(subscription.billing_key_encrypted)
        self.assertNotEqual(subscription.billing_key_encrypted, "")

    def test_update_payment_method_missing_token_returns_400(self):
        response = self.client.patch(
            f"/api/businesses/{self.business.id}/settings/subscription/payment-method/",
            {}, format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_cancel_subscription_sets_access_until_next_billing_date(self):
        # 먼저 구독 생성
        self.client.get(f"/api/businesses/{self.business.id}/settings/subscription/")
        subscription = Subscription.objects.get(business=self.business)
        original_next_billing = subscription.next_billing_date

        response = self.client.post(f"/api/businesses/{self.business.id}/settings/subscription/cancel/")

        self.assertEqual(response.status_code, 200)
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, "CANCELLED")
        self.assertEqual(subscription.access_until, original_next_billing)

    def test_cancel_already_cancelled_subscription_returns_409(self):
        self.client.get(f"/api/businesses/{self.business.id}/settings/subscription/")
        self.client.post(f"/api/businesses/{self.business.id}/settings/subscription/cancel/")

        response = self.client.post(f"/api/businesses/{self.business.id}/settings/subscription/cancel/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "ALREADY_CANCELLED")