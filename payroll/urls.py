from django.urls import path

from payroll.views import (
    EmployeeDetailView, EmployeeListCreateView,
    PaymentDetailView, PaymentListCreateView,
)

urlpatterns = [
    path("employees/", EmployeeListCreateView.as_view(), name="employee-list-create"),
    path("employees/<int:employee_id>/", EmployeeDetailView.as_view(), name="employee-detail"),
    path("payments/", PaymentListCreateView.as_view(), name="payment-list-create"),
    path("payments/<int:payment_id>/", PaymentDetailView.as_view(), name="payment-detail"),
]