from django.db.models import Exists, OuterRef, Q

from transactions.models import TransactionDuplicate


def with_pending_duplicate_flag(queryset):
    pending_duplicates = TransactionDuplicate.objects.filter(
        Q(primary_transaction_id=OuterRef("pk"))
        | Q(suspected_transaction_id=OuterRef("pk")),
        status=TransactionDuplicate.Status.PENDING,
    )
    return queryset.select_related("deduction_review").annotate(
        has_pending_duplicate=Exists(pending_duplicates)
    )
