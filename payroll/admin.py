from django.contrib import admin

from .models import Employee, Payment


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "business",
        "name",
        "employment_type",
        "status",
        "hourly_wage",
        "created_at",
    ]
    list_filter = ["employment_type", "status"]
    search_fields = ["name"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "employee",
        "year",
        "month",
        "gross_pay",
        "withholding_tax",
        "created_at",
    ]
    list_filter = ["year", "month"]
