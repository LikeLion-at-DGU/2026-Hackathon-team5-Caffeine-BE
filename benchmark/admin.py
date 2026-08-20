from django.contrib import admin

from .models import AIDiagnosisHistory, IndustryBenchmark


@admin.register(IndustryBenchmark)
class IndustryBenchmarkAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "region",
        "business_type",
        "year_month",
        "benchmark_monthly_revenue",
    ]
    list_filter = ["business_type", "year_month"]
    search_fields = ["region"]


@admin.register(AIDiagnosisHistory)
class AIDiagnosisHistoryAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "business",
        "year_month",
        "score",
        "is_fallback",
        "created_at",
    ]
    list_filter = ["is_fallback", "year_month"]
