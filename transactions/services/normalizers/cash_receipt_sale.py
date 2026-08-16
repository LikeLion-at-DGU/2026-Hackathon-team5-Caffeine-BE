from transactions.models import Transaction
from transactions.services.types import NormalizedTransaction

from .helpers import (
    as_list,
    ensure_success,
    external_id,
    normalized_business_number,
    parse_date,
    parse_decimal,
    parse_time,
)


def normalize_cash_receipt_sales(payload):
    ensure_success(payload)
    results = []

    for record in as_list(payload.get("data")):
        approval_no = str(record.get("resApprovalNo") or "").strip()
        transaction_name = str(record.get("resTransTypeNm") or "")
        is_cancelled = "취소" in transaction_name

        results.append(
            NormalizedTransaction(
                source_type=Transaction.SourceType.CASH_RECEIPT_SALE,
                external_id=external_id("CASH_RECEIPT_SALE", record, approval_no),
                transaction_type=Transaction.TransactionType.SALE,
                transaction_date=parse_date(record.get("resUsedDate")),
                transaction_time=parse_time(record.get("resUsedTime")),
                supply_amount=parse_decimal(record.get("resSupplyValue")),
                vat_amount=parse_decimal(record.get("resVAT") or record.get("resTaxAmt")),
                total_amount=parse_decimal(record.get("resTotalAmount")),
                approval_no=approval_no,
                cancel_status=(
                    Transaction.CancelStatus.CANCELLED
                    if is_cancelled
                    else Transaction.CancelStatus.NORMAL
                ),
                owner_business_number=normalized_business_number(
                    record.get("resCompanyIdentityNo")
                ),
                raw_data=record,
            )
        )

    return results
