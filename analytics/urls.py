from django.urls import path

from analytics.views import ExportView, MonthlyCloseView, MonthlySummaryView

urlpatterns = [
    path("monthly-summary/", MonthlySummaryView.as_view(), name="monthly-summary"),
    path("monthly-summary/close/", MonthlyCloseView.as_view(), name="monthly-summary-close"),
    path("export/", ExportView.as_view(), name="analytics-export"),
]