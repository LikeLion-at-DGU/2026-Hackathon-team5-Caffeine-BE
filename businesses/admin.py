from django.contrib import admin

from .models import Business


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "business_name",
        "business_number",
        "business_status",
        "tax_type",
        "is_demo",
    ]