from rest_framework import serializers

from settings.models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_display_name = serializers.SerializerMethodField()
    days_until_billing = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "plan_name", "plan_display_name", "price", "status",
            "next_billing_date", "days_until_billing",
            "card_company", "card_last4",
        ]

    def get_plan_display_name(self, obj):
        return obj.get_plan_name_display()

    def get_days_until_billing(self, obj):
        from django.utils import timezone
        delta = obj.next_billing_date - timezone.now().date()
        return max(delta.days, 0)


class PaymentMethodUpdateSerializer(serializers.Serializer):
    payment_token = serializers.CharField()