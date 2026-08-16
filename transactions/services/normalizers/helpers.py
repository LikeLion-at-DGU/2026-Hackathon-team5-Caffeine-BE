import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation


SUCCESS_CODES = {"MOCK-00000", "CF-00000"}


class TransactionNormalizationError(ValueError):
    pass


def ensure_success(payload):
    code = str(payload.get("result", {}).get("code", "")).strip()
    if code not in SUCCESS_CODES:
        message = payload.get("result", {}).get("message", "CODEF 거래 조회에 실패했습니다.")
        display_code = code or "MISSING_RESULT_CODE"
        raise TransactionNormalizationError(f"{display_code}: {message}")


def as_list(value):
    if value in (None, ""):
        return []
    return value if isinstance(value, list) else [value]


def parse_date(value):
    text = str(value or "").strip().replace("-", "")
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError as exc:
        raise TransactionNormalizationError(f"올바르지 않은 거래일자입니다: {value!r}") from exc


def parse_time(value):
    text = str(value or "").strip().replace(":", "")
    if not text:
        return None
    for fmt in ("%H%M%S", "%H%M"):
        try:
            return datetime.strptime(text, fmt).time()
        except ValueError:
            continue
    raise TransactionNormalizationError(f"올바르지 않은 거래시간입니다: {value!r}")


def parse_decimal(value):
    text = str(value or "0").strip().replace(",", "")
    try:
        return Decimal(text or "0")
    except InvalidOperation as exc:
        raise TransactionNormalizationError(f"올바르지 않은 금액입니다: {value!r}") from exc


def parse_integer(value):
    text = str(value or "0").strip().replace(",", "")
    try:
        return int(text or "0")
    except ValueError as exc:
        raise TransactionNormalizationError(f"올바르지 않은 정수입니다: {value!r}") from exc


def parse_year_month(value):
    text = str(value or "").strip().replace("-", "")
    if len(text) != 6 or not text.isdigit():
        raise TransactionNormalizationError(f"올바르지 않은 연월입니다: {value!r}")
    year = int(text[:4])
    month = int(text[4:])
    if not 1 <= month <= 12:
        raise TransactionNormalizationError(f"올바르지 않은 연월입니다: {value!r}")
    return year, month


def normalized_business_number(value):
    return "".join(character for character in str(value or "") if character.isdigit())


def external_id(prefix, record, approval_no=""):
    if approval_no:
        return f"{prefix}:{approval_no}"
    canonical = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]
    return f"{prefix}:HASH:{digest}"


def text_values(*values):
    return tuple(str(value).strip() for value in values if str(value or "").strip())
