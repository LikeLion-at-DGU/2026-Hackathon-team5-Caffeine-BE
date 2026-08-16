from django.contrib import admin
from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("business", "year_month", "status", "generated_at", "approved_at", "sent_at")
    list_filter = ("status",)