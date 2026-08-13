from django.urls import path

from payroll.views import EmployeeDetailView, EmployeeListCreateView

urlpatterns = [
    path("employees/", EmployeeListCreateView.as_view(), name="employee-list-create"),
    path("employees/<int:employee_id>/", EmployeeDetailView.as_view(), name="employee-detail"),
]