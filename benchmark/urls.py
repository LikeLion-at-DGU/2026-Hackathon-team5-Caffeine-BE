from django.urls import path
from benchmark.views import (
    BenchmarkDashboardView,
    BenchmarkCategoriesView,
    BenchmarkTrendView,
    BenchmarkAiDiagnosisRefreshView,
    BenchmarkDeepDiagnosisView,
)

urlpatterns = [
    path("", BenchmarkDashboardView.as_view(), name="benchmark-dashboard"),
    path("categories/", BenchmarkCategoriesView.as_view(), name="benchmark-categories"),
    path("trend/", BenchmarkTrendView.as_view(), name="benchmark-trend"),
    path("ai-diagnosis/", BenchmarkAiDiagnosisRefreshView.as_view(), name="benchmark-ai-diagnosis-refresh"),
    path("deep-diagnosis/", BenchmarkDeepDiagnosisView.as_view(), name="benchmark-deep-diagnosis"),
]
