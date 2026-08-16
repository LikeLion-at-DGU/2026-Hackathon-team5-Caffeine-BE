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
    text_values,
)


def normalize_business_card_purchases(payload):
    ensure_success(payload)
    data = payload.get("data") or {}
    owner_business_number = normalized_business_number(data.get("resCompanyIdentityNo"))
    results = []

    for record in as_list(data.get("resDetailList")):
        approval_no = str(record.get("resApprovalNo") or "").strip()
        identity = {
            key: record.get(key)
            for key in (
                "resUsedDate",
                "resUsedTime",
                "resMemberStoreCorpNo",
                "resMemberStoreName",
                "resTotalAmount",
                "resCardNo",
            )
        }
        transaction_name = str(record.get("resTransTypeNm") or "")
        cancel_value = str(record.get("resCancelYN") or "")
        is_cancelled = "취소" in transaction_name or cancel_value.upper() in {"Y", "1", "TRUE"}

        results.append(
            NormalizedTransaction(
                source_type=Transaction.SourceType.CARD_PURCHASE,
                external_id=external_id("CARD_PURCHASE", identity, approval_no),
                transaction_type=Transaction.TransactionType.PURCHASE,
                transaction_date=parse_date(record.get("resUsedDate")),
                transaction_time=parse_time(record.get("resUsedTime")),
                merchant_name=str(record.get("resMemberStoreName") or "").strip(),
                merchant_business_number=normalized_business_number(
                    record.get("resMemberStoreCorpNo")
                ),
                supply_amount=parse_decimal(record.get("resSupplyValue")),
                vat_amount=parse_decimal(record.get("resTaxAmt")),
                total_amount=parse_decimal(
                    record.get("resTotalAmount") or record.get("resUsedAmount")
                ),
                approval_no=approval_no,
                cancel_status=(
                    Transaction.CancelStatus.CANCELLED
                    if is_cancelled
                    else Transaction.CancelStatus.NORMAL
                ),
                source_deduction_status=_deduction_status(
                    record.get("resDeductDescription")
                ),
                owner_business_number=owner_business_number,
                classification_hints=text_values(
                    record.get("resMemberStoreName"),
                    record.get("resBusinessTypes"),
                    record.get("resBusinessItems"),
                ),
                raw_data=record,
            )
        )

    return results


def _deduction_status(value):
    text = str(value or "").strip()
    if text == "공제":
        return Transaction.SourceDeductionStatus.DEDUCTIBLE
    if text == "불공제":
        return Transaction.SourceDeductionStatus.NON_DEDUCTIBLE
    return Transaction.SourceDeductionStatus.UNKNOWN
