from django.urls import path
from . import views

urlpatterns = [
    path("<str:year_month>/", views.ReportDetailView.as_view(), name="report-detail"),
    path("<str:year_month>/generate/", views.ReportGenerateView.as_view(), name="report-generate"),
    path("<str:year_month>/download/", views.ReportDownloadView.as_view(), name="report-download"),
    path("<str:year_month>/approve/", views.ReportApproveView.as_view(), name="report-approve"),
    path("<str:year_month>/send-email/", views.ReportSendEmailView.as_view(), name="report-send-email"),
]