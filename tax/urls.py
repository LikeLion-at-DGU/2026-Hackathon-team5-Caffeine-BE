from django.urls import path

from .views import (
    DeductionAiSuggestView,
    DeductionConfirmView,
    DeductionListView,
    MonthlyCloseApproveView,
    MonthlyCloseDetailView,
    VatForecastView,
)


urlpatterns = [
    path("deductions/", DeductionListView.as_view(), name="tax-deduction-list"),
    path(
        "deductions/<int:transaction_id>/ai-suggest/",
        DeductionAiSuggestView.as_view(),
        name="tax-deduction-ai-suggest",
    ),
    path(
        "deductions/<int:transaction_id>/",
        DeductionConfirmView.as_view(),
        name="tax-deduction-confirm",
    ),
    path("vat-forecast/", VatForecastView.as_view(), name="tax-vat-forecast"),
    path(
        "closing/<str:year_month>/",
        MonthlyCloseDetailView.as_view(),
        name="tax-monthly-close-detail",
    ),
    path(
        "closing/<str:year_month>/approve/",
        MonthlyCloseApproveView.as_view(),
        name="tax-monthly-close-approve",
    ),
]
