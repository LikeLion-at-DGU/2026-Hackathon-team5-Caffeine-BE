from django.utils import timezone
from rest_framework import serializers

from settings.models import Subscription


class SubscriptionSerializer(serializers.ModelSerializer):
    plan_display_name = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()
    days_until_billing = serializers.SerializerMethodField()

    class Meta:
        model = Subscription
        fields = [
            "plan_name", "plan_display_name", "price", "status", "status_display",
            "next_billing_date", "days_until_billing",
            "card_company", "card_last4",
            "cancelled_at", "access_until", "last_payment_error",
        ]

    def get_plan_display_name(self, obj):
        return obj.get_plan_name_display()

    def get_status_display(self, obj):
        return obj.get_status_display()

    def get_days_until_billing(self, obj):
        delta = obj.next_billing_date - timezone.now().date()
        return max(delta.days, 0)


class PaymentMethodUpdateSerializer(serializers.Serializer):
    payment_token = serializers.CharField()


class BusinessInfoSerializer(serializers.Serializer):
    business_name = serializers.CharField()
    representative_name = serializers.CharField(allow_blank=True)
    birth_date = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    business_number = serializers.CharField(allow_null=True, allow_blank=True)
    tax_type = serializers.CharField(required=False)
    industry_code = serializers.CharField(allow_blank=True)
    # 업태와 종목은 화면에서 필요한 방식으로 조합할 수 있도록 분리한다.
    business_type = serializers.CharField(required=False, allow_blank=True)
    business_item = serializers.CharField(required=False, allow_blank=True)


class BusinessInfoUpdateSerializer(serializers.Serializer):
    business_name = serializers.CharField(required=False)
    representative_name = serializers.CharField(required=False, allow_blank=True)
    birth_date = serializers.CharField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    business_number = serializers.CharField(required=False, allow_blank=True)
    industry_code = serializers.CharField(required=False, allow_blank=True)
    # 과세유형은 변경 이력을 남기는 동기화 API에서만 수정한다.
