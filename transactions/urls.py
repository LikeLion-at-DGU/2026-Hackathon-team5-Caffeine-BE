from django.urls import path

from .views import (
    TransactionCategoryView,
    TransactionDetailView,
    TransactionDuplicateListView,
    TransactionDuplicateResolutionView,
    TransactionExportView,
    TransactionListView,
    TransactionPurposeView,
    TransactionSyncRetryView,
    TransactionSyncView,
)


urlpatterns = [
    path("export/", TransactionExportView.as_view(), name="transaction-export"),
    path("sync/", TransactionSyncView.as_view(), name="transaction-sync"),
    path("sync/retry/", TransactionSyncRetryView.as_view(), name="transaction-sync-retry"),
    path("", TransactionListView.as_view(), name="transaction-list"),
    path("duplicates/", TransactionDuplicateListView.as_view(), name="transaction-duplicate-list"),
    path(
        "duplicates/<int:duplicate_id>/",
        TransactionDuplicateResolutionView.as_view(),
        name="transaction-duplicate-resolution",
    ),
    path("<int:transaction_id>/", TransactionDetailView.as_view(), name="transaction-detail"),
    path(
        "<int:transaction_id>/category/",
        TransactionCategoryView.as_view(),
        name="transaction-category",
    ),
    path(
        "<int:transaction_id>/purpose/",
        TransactionPurposeView.as_view(),
        name="transaction-purpose",
    ),
]