from django.urls import path

from analytics.views import (
    AnalyticsExportView,
    AnalyticsSummaryView,
    CategoryTrendView,
    CostRatioView,
    DeductionBreakdownView,
    MonthlyCloseView,
    MonthlySummaryView,
)

urlpatterns = [
    path("cost-ratio/", CostRatioView.as_view(), name="cost-ratio"),
    path("trend/", CategoryTrendView.as_view(), name="category-trend"),
    path("summary/", AnalyticsSummaryView.as_view(), name="analytics-summary"),
    path("monthly-summary/", MonthlySummaryView.as_view(), name="monthly-summary"),
    path("deduction-breakdown/", DeductionBreakdownView.as_view(), name="deduction-breakdown"),
    path("monthly-summary/close/", MonthlyCloseView.as_view(), name="monthly-summary-close"),
    path("export/", AnalyticsExportView.as_view(), name="analytics-export"),
]
