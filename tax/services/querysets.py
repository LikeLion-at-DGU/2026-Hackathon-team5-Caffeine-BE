from transactions.models import Transaction, TransactionDuplicate


def effective_transactions(*, business, start_date=None, end_date=None):
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
