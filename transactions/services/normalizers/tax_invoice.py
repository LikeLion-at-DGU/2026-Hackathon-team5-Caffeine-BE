from transactions.models import Transaction
from transactions.services.types import NormalizedTransaction

from .helpers import (
    as_list,
    ensure_success,
    external_id,
    normalized_business_number,
    parse_date,
    parse_decimal,
    text_values,
)


def normalize_tax_invoices(payload, transaction_type):
    ensure_success(payload)
    results = []

    for record in as_list(payload.get("data")):
        is_purchase = transaction_type == Transaction.TransactionType.PURCHASE
        if is_purchase:
            merchant_name = record.get("resSupplierCompanyName")
            merchant_number = record.get("resSupplierRegNumber")
            merchant_type = record.get("resSupplierBusinessTypes")
            merchant_items = record.get("resSupplierBusinessItems")
            owner_number = record.get("resContractorRegNumber")
        else:
            merchant_name = record.get("resContractorCompanyName")
            merchant_number = record.get("resContractorRegNumber")
            merchant_type = record.get("resContractorBusinessTypes")
            merchant_items = record.get("resContractorBusinessItems")
            owner_number = record.get("resSupplierRegNumber")

        approval_no = str(record.get("resApprovalNo") or "").strip()
        trade_item_names = [
            item.get("resTaxItemName")
            for item in as_list(record.get("resTradeItemList"))
        ]
        hints = ()
        if is_purchase:
            hints = text_values(
                merchant_name,
                merchant_type,
                merchant_items,
                record.get("resRepItems"),
                *trade_item_names,
            )

        results.append(
            NormalizedTransaction(
                source_type=Transaction.SourceType.TAX_INVOICE,
                external_id=external_id(
                    f"TAX_INVOICE_{transaction_type}",
                    record,
                    approval_no,
                ),
                transaction_type=transaction_type,
                transaction_date=parse_date(
                    record.get("resIssueDate") or record.get("resReportingDate")
                ),
                merchant_name=str(merchant_name or "").strip(),
                merchant_business_number=normalized_business_number(merchant_number),
                supply_amount=parse_decimal(
                    record.get("resSupplyValue") or record.get("resSupplyAmount")
                ),
                vat_amount=parse_decimal(
                    record.get("resTaxAmt") or record.get("resTax")
                ),
                total_amount=parse_decimal(record.get("resTotalAmount")),
                approval_no=approval_no,
                owner_business_number=normalized_business_number(owner_number),
                classification_hints=hints,
                raw_data=record,
            )
        )

    return results
