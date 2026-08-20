from django.contrib import admin

from .models import Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "business",
        "plan_name",
        "status",
        "next_billing_date",
        "card_company",
        "card_last4",
    ]
    list_filter = ["plan_name", "status"]
