from django.contrib import admin

from .models import DeductionReview, MonthlyClose


@admin.register(DeductionReview)
class DeductionReviewAdmin(admin.ModelAdmin):
    list_display = (
        "transaction",
        "suggested_status",
        "suggestion_source",
        "confirmed_status",
        "confirmed_at",
    )
    list_filter = ("suggested_status", "suggestion_source", "confirmed_status")
    search_fields = ("transaction__merchant_name", "transaction__external_id")


@admin.register(MonthlyClose)
class MonthlyCloseAdmin(admin.ModelAdmin):
    list_display = ("business", "year", "month", "status", "estimated_vat", "approved_at")
    list_filter = ("status", "year", "month")
