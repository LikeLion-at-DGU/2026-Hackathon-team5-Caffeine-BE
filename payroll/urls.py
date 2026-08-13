from django.urls import path

from payroll.views import (
    EmployeeDetailView, EmployeeListCreateView,
    PaymentDetailView, PaymentExportView, PaymentListCreateView,
    PayrollSummaryView,
)

urlpatterns = [
    path("employees/", EmployeeListCreateView.as_view(), name="employee-list-create"),
    path("employees/<int:employee_id>/", EmployeeDetailView.as_view(), name="employee-detail"),
    path("payments/", PaymentListCreateView.as_view(), name="payment-list-create"),
    path("payments/<int:payment_id>/", PaymentDetailView.as_view(), name="payment-detail"),
    path("payments/export/", PaymentExportView.as_view(), name="payment-export"),
    path("summary/", PayrollSummaryView.as_view(), name="payroll-summary"),
]