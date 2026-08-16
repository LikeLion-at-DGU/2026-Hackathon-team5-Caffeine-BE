from django.contrib import admin

from .models import MonthlySalesSummary, Transaction, TransactionDuplicate


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "business",
        "transaction_date",
        "transaction_type",
        "source_type",
        "merchant_name",
        "total_amount",
        "category",
        "expense_purpose",
    ]
    list_filter = [
        "transaction_type",
        "source_type",
        "category",
        "expense_purpose",
        "cancel_status",
    ]
    search_fields = ["merchant_name", "merchant_business_number", "approval_no", "external_id"]


@admin.register(TransactionDuplicate)
class TransactionDuplicateAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "business",
        "primary_transaction",
        "suspected_transaction",
        "status",
        "confidence",
    ]
    list_filter = ["status"]


@admin.register(MonthlySalesSummary)
class MonthlySalesSummaryAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "business",
        "year",
        "month",
        "source_type",
        "transaction_count",
        "total_amount",
    ]
    list_filter = ["source_type", "year", "month"]
