from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class NormalizedTransaction:
    """CODEF source별 normalizer가 공통으로 반환할 내부 거래 형식."""

    source_type: str
    external_id: str
    transaction_type: str
    transaction_date: date
    total_amount: Decimal
    transaction_time: time | None = None
    merchant_name: str = ""
    merchant_business_number: str = ""
    supply_amount: Decimal = Decimal("0")
    vat_amount: Decimal = Decimal("0")
    approval_no: str = ""
    cancel_status: str = "NORMAL"
    owner_business_number: str = ""
    classification_hints: tuple[str, ...] = ()
    raw_data: dict[str, Any] = field(default_factory=dict)
