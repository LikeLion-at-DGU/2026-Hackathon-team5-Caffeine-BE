from django.db.models import Exists, OuterRef, Q

from transactions.models import Transaction, TransactionDuplicate


def effective_transactions(*, business, start_date=None, end_date=None):
    """Return non-cancelled transactions after confirmed duplicate removal."""
    confirmed_duplicate_ids = TransactionDuplicate.objects.filter(
        business=business,
        status=TransactionDuplicate.Status.CONFIRMED,
    ).values_list("suspected_transaction_id", flat=True)

    queryset = Transaction.objects.filter(
        business=business,
        cancel_status=Transaction.CancelStatus.NORMAL,
    ).exclude(id__in=confirmed_duplicate_ids)
    if start_date:
        queryset = queryset.filter(transaction_date__gte=start_date)
    if end_date:
        queryset = queryset.filter(transaction_date__lte=end_date)
    return queryset


def effective_purchase_transactions(*, business, start_date=None, end_date=None):
    return effective_transactions(
        business=business,
        start_date=start_date,
        end_date=end_date,
    ).filter(transaction_type=Transaction.TransactionType.PURCHASE)


def with_pending_duplicate_flag(queryset):
    pending_duplicates = TransactionDuplicate.objects.filter(
        Q(primary_transaction_id=OuterRef("pk"))
        | Q(suspected_transaction_id=OuterRef("pk")),
        status=TransactionDuplicate.Status.PENDING,
    )
    return queryset.select_related("deduction_review").annotate(
        has_pending_duplicate=Exists(pending_duplicates)
    )
