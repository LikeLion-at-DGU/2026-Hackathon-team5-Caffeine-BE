from collections import Counter

from django.db import transaction as db_transaction

from businesses.models import CodefConnection
from integrations.codef.base import CodefBusinessAccessError
from integrations.codef.client import (
    extract_two_way_info,
    is_two_way_required,
)
from integrations.codef.factory import get_codef_provider
from transactions.models import (
    MonthlySalesSummary,
    Transaction,
    TransactionDuplicate,
)

from .classifier import RuleBasedTransactionClassifier
from .duplicate_detector import DuplicateDetector
from .ingestion_service import (
    MonthlySalesSummaryIngestionService,
    TransactionIngestionService,
)
from .normalizers import (
    normalize_business_card_purchases,
    normalize_cash_receipt_sales,
    normalize_credit_card_sales_summaries,
    normalize_tax_invoices,
)
from .normalizers.helpers import normalized_business_number


class TransactionSourceMismatchError(ValueError):
    """요청 사업장과 거래 원본의 사업자번호가 일치하지 않을 때 발생한다."""


class PendingTwoWayAuthError(ValueError):
    """이미 진행 중인 카카오 2-way 인증이 있을 때 발생한다."""


class NoPendingTwoWayAuthError(ValueError):
    """재시도할 2-way 인증 정보가 없을 때 발생한다."""


class CodefTwoWayRequired(Exception):
    """거래 조회 중 CODEF 2-way 추가인증이 필요한 경우 사용한다.

    atomic 블록 밖으로 예외를 전달해 기존 저장 내용을 롤백한 뒤,
    인증 재개에 필요한 정보만 CodefConnection에 별도로 저장한다.
    """

    def __init__(
        self,
        *,
        source,
        operation,
        start_date,
        end_date,
        two_way_info,
        method,
        raw,
    ):
        self.source = source
        self.operation = operation
        self.start_date = start_date
        self.end_date = end_date
        self.two_way_info = two_way_info
        self.method = method
        self.raw = raw

        label = (
            f"{source}/{operation}"
            if operation
            else source
        )

        super().__init__(
            f"카카오 추가인증이 필요합니다: {label}"
        )


# Transaction Sync의 카카오 2-way 인증은 HOMETAX 연결을 사용한다.
_HOMETAX_CONNECTION_TYPE = "HOMETAX"

# CODEF simpleAuth 승인 완료 값
_SIMPLE_AUTH_OK = "1"

# 카카오 2-way 인증이 발생할 수 있는 거래 소스.
# 신용카드 매출자료는 공동인증서 기반이므로 제외한다.
_HOMETAX_DEPENDENT_SOURCES = {
    Transaction.SourceType.CARD_PURCHASE,
    Transaction.SourceType.CASH_RECEIPT_SALE,
    Transaction.SourceType.TAX_INVOICE,
}


class TransactionSyncService:
    SUPPORTED_SOURCES = (
        Transaction.SourceType.CARD_PURCHASE,
        Transaction.SourceType.CASH_RECEIPT_SALE,
        Transaction.SourceType.TAX_INVOICE,
        MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
    )

    def __init__(self, provider=None):
        self.provider = provider or get_codef_provider()
        self.ingestion = TransactionIngestionService()
        self.sales_summary_ingestion = (
            MonthlySalesSummaryIngestionService()
        )
        self.classifier = RuleBasedTransactionClassifier()
        self.duplicate_detector = DuplicateDetector()

    # ==================================================
    # 최초 동기화
    # ==================================================

    def sync(
        self,
        business,
        start_date,
        end_date,
        sources,
    ):
        """거래 소스를 조회하고 정상 응답만 DB에 저장한다.

        2-way 인증이 필요한 경우 현재 atomic 작업을 롤백하고,
        인증 재개에 필요한 pending 정보만 별도로 저장한다.
        """

        self._ensure_no_pending_two_way(
            business,
            sources,
        )

        try:
            with db_transaction.atomic():
                return self._sync_atomic(
                    business,
                    start_date,
                    end_date,
                    sources,
                )

        except CodefTwoWayRequired as exc:
            # atomic 롤백 완료 후 pending 정보만 새로 저장
            self._save_pending_two_way(
                business,
                exc,
            )

            return self._auth_required_result(
                business,
                exc,
            )

    def _sync_atomic(
        self,
        business,
        start_date,
        end_date,
        sources,
    ):
        """전체 Transaction Sync 저장 작업을 하나의 transaction으로 처리한다."""

        total_created = 0
        total_updated = 0
        skipped_outside_period = 0
        source_results = []
        category_counts = Counter()

        transaction_created_count = 0
        transaction_updated_count = 0
        sales_summary_created_count = 0
        sales_summary_updated_count = 0
        new_duplicate_candidate_count = 0

        for source in sources:
            try:
                self.provider.ensure_business_access(
                    business,
                    source,
                )
            except CodefBusinessAccessError as exc:
                raise TransactionSourceMismatchError(
                    str(exc)
                ) from exc

            # 신용카드 매출자료는 Transaction이 아닌
            # MonthlySalesSummary로 별도 저장한다.
            if (
                source
                == MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY
            ):
                result = self._sync_credit_card_sales_summaries(
                    business,
                    start_date,
                    end_date,
                )

                total_created += result["created_count"]
                total_updated += result["updated_count"]

                sales_summary_created_count += (
                    result["created_count"]
                )
                sales_summary_updated_count += (
                    result["updated_count"]
                )

                skipped_outside_period += (
                    result["skipped_count"]
                )

                source_results.append(
                    result["source_result"]
                )
                continue

            normalized_items = self._fetch_and_normalize(
                source,
                business,
                start_date,
                end_date,
            )

            self._validate_business_ownership(
                business,
                normalized_items,
            )

            in_period = [
                item
                for item in normalized_items
                if (
                    start_date
                    <= item.transaction_date
                    <= end_date
                )
            ]

            skipped_outside_period += (
                len(normalized_items)
                - len(in_period)
            )

            source_created = 0
            source_updated = 0

            for normalized in in_period:
                saved, created = self.ingestion.save(
                    business,
                    normalized,
                )

                self._apply_classification(
                    saved,
                    normalized,
                )

                _, created_duplicates = (
                    self.duplicate_detector.detect_with_count(
                        saved
                    )
                )

                new_duplicate_candidate_count += (
                    created_duplicates
                )

                category_counts[
                    saved.category
                ] += 1

                if created:
                    source_created += 1
                else:
                    source_updated += 1

            total_created += source_created
            total_updated += source_updated

            transaction_created_count += source_created
            transaction_updated_count += source_updated

            source_results.append(
                {
                    "source_type": source,
                    "record_type": "TRANSACTION",
                    "fetched_count": len(
                        normalized_items
                    ),
                    "in_period_count": len(
                        in_period
                    ),
                    "created_count": source_created,
                    "updated_count": source_updated,
                }
            )

        duplicates_after = (
            TransactionDuplicate.objects.filter(
                business=business
            ).count()
        )

        return {
            "outcome": "SUCCESS",
            "business_id": business.id,
            "period": {
                "start_date":
                    start_date.isoformat(),
                "end_date":
                    end_date.isoformat(),
            },
            "source_results":
                source_results,
            "created_count":
                total_created,
            "updated_count":
                total_updated,
            "transaction_created_count":
                transaction_created_count,
            "transaction_updated_count":
                transaction_updated_count,
            "sales_summary_created_count":
                sales_summary_created_count,
            "sales_summary_updated_count":
                sales_summary_updated_count,
            "skipped_outside_period_count":
                skipped_outside_period,
            "new_duplicate_candidate_count":
                new_duplicate_candidate_count,
            "duplicate_candidate_total_count":
                duplicates_after,
            "category_counts":
                dict(category_counts),
        }

    # ==================================================
    # 카카오 2-way 인증 완료 후 재시도
    # ==================================================

    def retry(self, business):
        """저장된 pending 정보를 사용해 2-way 거래 조회를 재개한다."""

        conn = CodefConnection.objects.filter(
            business=business,
            connection_type=_HOMETAX_CONNECTION_TYPE,
        ).first()

        if (
            not conn
            or not conn.continue_2way
            or not conn.pending_source
        ):
            raise NoPendingTwoWayAuthError(
                "재시도할 카카오 추가인증 요청이 없습니다."
            )

        source = conn.pending_source
        operation = conn.pending_operation
        start_date = conn.pending_start_date
        end_date = conn.pending_end_date

        two_way_info = {
            "jobIndex":
                conn.job_index,
            "threadIndex":
                conn.thread_index,
            "jti":
                conn.jti,
            "twoWayTimestamp":
                conn.two_way_timestamp,
        }

        try:
            with db_transaction.atomic():
                result = self._retry_atomic(
                    business,
                    source,
                    operation,
                    start_date,
                    end_date,
                    two_way_info,
                )

        except CodefTwoWayRequired as exc:
            # 재요청 후 다시 추가인증이 필요한 경우
            # 새로운 2-way 정보로 pending 상태를 갱신한다.
            self._save_pending_two_way(
                business,
                exc,
            )

            return self._auth_required_result(
                business,
                exc,
            )

        self._clear_pending_two_way(
            business
        )

        return result

    def _retry_atomic(
        self,
        business,
        source,
        operation,
        start_date,
        end_date,
        two_way_info,
    ):
        """pending 거래를 2-way 정보와 함께 재조회하고 저장한다."""

        normalized_items = self._fetch_and_normalize(
            source,
            business,
            start_date,
            end_date,
            resume_operation=operation,
            two_way_info=two_way_info,
            simple_auth=_SIMPLE_AUTH_OK,
        )

        self._validate_business_ownership(
            business,
            normalized_items,
        )

        in_period = [
            item
            for item in normalized_items
            if (
                start_date
                <= item.transaction_date
                <= end_date
            )
        ]

        created_count = 0
        updated_count = 0
        category_counts = Counter()
        new_duplicate_candidate_count = 0

        for normalized in in_period:
            saved, created = self.ingestion.save(
                business,
                normalized,
            )

            self._apply_classification(
                saved,
                normalized,
            )

            _, created_duplicates = (
                self.duplicate_detector.detect_with_count(
                    saved
                )
            )

            new_duplicate_candidate_count += (
                created_duplicates
            )

            category_counts[
                saved.category
            ] += 1

            if created:
                created_count += 1
            else:
                updated_count += 1

        duplicates_after = (
            TransactionDuplicate.objects.filter(
                business=business
            ).count()
        )

        return {
            "outcome": "SUCCESS",
            "business_id": business.id,
            "period": {
                "start_date":
                    start_date.isoformat(),
                "end_date":
                    end_date.isoformat(),
            },
            "source_results": [
                {
                    "source_type": source,
                    "record_type":
                        "TRANSACTION",
                    "fetched_count":
                        len(normalized_items),
                    "in_period_count":
                        len(in_period),
                    "created_count":
                        created_count,
                    "updated_count":
                        updated_count,
                }
            ],
            "created_count":
                created_count,
            "updated_count":
                updated_count,
            "transaction_created_count":
                created_count,
            "transaction_updated_count":
                updated_count,
            "sales_summary_created_count":
                0,
            "sales_summary_updated_count":
                0,
            "skipped_outside_period_count":
                len(normalized_items)
                - len(in_period),
            "new_duplicate_candidate_count":
                new_duplicate_candidate_count,
            "duplicate_candidate_total_count":
                duplicates_after,
            "category_counts":
                dict(category_counts),
        }

    # ==================================================
    # 신용카드 매출자료
    # ==================================================

    def _sync_credit_card_sales_summaries(
        self,
        business,
        start_date,
        end_date,
    ):
        """공동인증서 기반 신용카드 월별 매출자료를 저장한다.

        이 상품은 카카오 2-way 인증 대상이 아니다.
        """

        payload = (
            self.provider
            .get_credit_card_sales_summary(
                business,
                start_date,
                end_date,
            )
        )

        normalized_items = (
            normalize_credit_card_sales_summaries(
                payload
            )
        )

        start_period = (
            start_date.year,
            start_date.month,
        )
        end_period = (
            end_date.year,
            end_date.month,
        )

        in_period = [
            item
            for item in normalized_items
            if (
                start_period
                <= (item.year, item.month)
                <= end_period
            )
        ]

        created_count = 0
        updated_count = 0

        for normalized in in_period:
            _, created = (
                self.sales_summary_ingestion.save(
                    business,
                    normalized,
                )
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        return {
            "created_count":
                created_count,
            "updated_count":
                updated_count,
            "skipped_count":
                len(normalized_items)
                - len(in_period),
            "source_result": {
                "source_type":
                    (
                        MonthlySalesSummary
                        .SourceType
                        .CREDIT_CARD_SALES_SUMMARY
                    ),
                "record_type":
                    "MONTHLY_SALES_SUMMARY",
                "fetched_count":
                    len(normalized_items),
                "in_period_count":
                    len(in_period),
                "created_count":
                    created_count,
                "updated_count":
                    updated_count,
            },
        }

    # ==================================================
    # Provider 조회 및 2-way 감지
    # ==================================================

    def _fetch_and_normalize(
        self,
        source,
        business,
        start_date,
        end_date,
        *,
        resume_operation=None,
        two_way_info=None,
        simple_auth=None,
    ):
        """거래 원본을 조회하고 source별 normalizer를 적용한다.

        resume_operation이 지정된 경우 해당 거래 요청에만
        2-way 재요청 정보를 전달한다.
        """

        def _resume_kwargs(operation):
            if (
                resume_operation is not None
                and operation
                == resume_operation
            ):
                return {
                    "two_way_info":
                        two_way_info,
                    "simple_auth":
                        simple_auth,
                }

            return {
                "two_way_info": None,
                "simple_auth": None,
            }

        # --------------------------------------------------
        # 사업용 신용카드 매입
        # --------------------------------------------------

        if source == Transaction.SourceType.CARD_PURCHASE:
            payload = (
                self.provider
                .get_business_card_purchases(
                    business,
                    start_date,
                    end_date,
                    **_resume_kwargs(""),
                )
            )

            self._raise_if_two_way_required(
                payload,
                source=source,
                operation="",
                start_date=start_date,
                end_date=end_date,
            )

            return normalize_business_card_purchases(
                payload
            )

        # --------------------------------------------------
        # 현금영수증 매출
        # --------------------------------------------------

        if (
            source
            == Transaction.SourceType.CASH_RECEIPT_SALE
        ):
            payload = (
                self.provider
                .get_cash_receipt_sales(
                    business,
                    start_date,
                    end_date,
                    **_resume_kwargs(""),
                )
            )

            self._raise_if_two_way_required(
                payload,
                source=source,
                operation="",
                start_date=start_date,
                end_date=end_date,
            )

            return normalize_cash_receipt_sales(
                payload
            )

        # --------------------------------------------------
        # 전자세금계산서
        # --------------------------------------------------

        if source == Transaction.SourceType.TAX_INVOICE:
            # 매입부터 조회한다.
            # 매입에서 추가인증이 발생하면 매출은 호출하지 않는다.
            purchases = (
                self.provider
                .get_tax_invoice_purchases(
                    business,
                    start_date,
                    end_date,
                    **_resume_kwargs(
                        Transaction
                        .TransactionType
                        .PURCHASE
                    ),
                )
            )

            self._raise_if_two_way_required(
                purchases,
                source=source,
                operation=(
                    Transaction
                    .TransactionType
                    .PURCHASE
                ),
                start_date=start_date,
                end_date=end_date,
            )

            # 매입 조회가 완료된 경우에만 매출을 조회한다.
            sales = (
                self.provider
                .get_tax_invoice_sales(
                    business,
                    start_date,
                    end_date,
                    **_resume_kwargs(
                        Transaction
                        .TransactionType
                        .SALE
                    ),
                )
            )

            self._raise_if_two_way_required(
                sales,
                source=source,
                operation=(
                    Transaction
                    .TransactionType
                    .SALE
                ),
                start_date=start_date,
                end_date=end_date,
            )

            return [
                *normalize_tax_invoices(
                    purchases,
                    Transaction
                    .TransactionType
                    .PURCHASE,
                ),
                *normalize_tax_invoices(
                    sales,
                    Transaction
                    .TransactionType
                    .SALE,
                ),
            ]

        raise ValueError(
            "지원하지 않는 거래 동기화 소스입니다: "
            f"{source}"
        )

    @staticmethod
    def _raise_if_two_way_required(
        raw,
        *,
        source,
        operation,
        start_date,
        end_date,
    ):
        """CODEF 응답이 추가인증 상태이면 내부 제어 예외를 발생시킨다."""

        if not is_two_way_required(raw):
            return

        raise CodefTwoWayRequired(
            source=source,
            operation=operation,
            start_date=start_date,
            end_date=end_date,
            two_way_info=extract_two_way_info(
                raw
            ),
            method=(
                (raw.get("data") or {})
                .get("method", "")
            ),
            raw=raw,
        )

    # ==================================================
    # 2-way pending 상태 관리
    # ==================================================

    @staticmethod
    def _ensure_no_pending_two_way(
        business,
        sources,
    ):
        """진행 중인 HOMETAX 2-way가 있으면 새 거래 조회를 막는다."""

        # 공동인증서 상품만 요청한 경우에는
        # HOMETAX pending 상태와 무관하게 실행할 수 있다.
        if not any(
            source in _HOMETAX_DEPENDENT_SOURCES
            for source in sources
        ):
            return

        conn = (
            CodefConnection.objects.filter(
                business=business,
                connection_type=(
                    _HOMETAX_CONNECTION_TYPE
                ),
            )
            .first()
        )

        if (
            conn
            and conn.continue_2way
        ):
            raise PendingTwoWayAuthError(
                "이미 완료되지 않은 카카오 인증 요청이 있습니다. "
                "먼저 인증을 완료하거나 재시도해주세요."
            )

    @staticmethod
    def _save_pending_two_way(
        business,
        exc,
    ):
        """CODEF 2-way 정보와 재개할 거래 요청 정보를 저장한다."""

        conn, _ = (
            CodefConnection.objects.get_or_create(
                business=business,
                connection_type=(
                    _HOMETAX_CONNECTION_TYPE
                ),
            )
        )

        conn.status = "AUTH_REQUIRED"
        conn.continue_2way = True

        conn.method = exc.method
        conn.job_index = (
            exc.two_way_info.get(
                "jobIndex"
            )
        )
        conn.thread_index = (
            exc.two_way_info.get(
                "threadIndex"
            )
        )
        conn.jti = (
            exc.two_way_info.get("jti")
            or ""
        )
        conn.two_way_timestamp = (
            exc.two_way_info.get(
                "twoWayTimestamp"
            )
        )

        conn.pending_source = exc.source
        conn.pending_operation = (
            exc.operation
            or ""
        )
        conn.pending_start_date = (
            exc.start_date
        )
        conn.pending_end_date = (
            exc.end_date
        )

        conn.last_error_code = ""
        conn.last_error_message = ""
        conn.last_raw_response = exc.raw

        conn.save()

    @staticmethod
    def _clear_pending_two_way(
        business,
    ):
        """2-way 인증 완료 후 pending 상태를 초기화한다."""

        conn = (
            CodefConnection.objects.filter(
                business=business,
                connection_type=(
                    _HOMETAX_CONNECTION_TYPE
                ),
            )
            .first()
        )

        if not conn:
            return

        conn.status = "CONNECTED"
        conn.continue_2way = False

        conn.method = ""
        conn.job_index = None
        conn.thread_index = None
        conn.jti = ""
        conn.two_way_timestamp = None

        conn.pending_source = ""
        conn.pending_operation = ""
        conn.pending_start_date = None
        conn.pending_end_date = None

        conn.last_error_code = ""
        conn.last_error_message = ""

        conn.save()

    @staticmethod
    def _auth_required_result(
        business,
        exc,
    ):
        """프론트에 반환할 추가인증 대기 응답을 생성한다."""

        return {
            "outcome": "AUTH_REQUIRED",
            "business_id": business.id,
            "pending_source":
                exc.source,
            "pending_operation":
                exc.operation,
            "period": {
                "start_date":
                    exc.start_date.isoformat(),
                "end_date":
                    exc.end_date.isoformat(),
            },
            "message": (
                "카카오 추가인증이 필요합니다. "
                "인증 완료 후 "
                "/transactions/sync/retry/ 로 "
                "재시도하세요."
            ),
        }

    # ==================================================
    # 공통 검증 및 후처리
    # ==================================================

    @staticmethod
    def _validate_business_ownership(
        business,
        normalized_items,
    ):
        """조회된 거래가 요청 사업자의 데이터인지 검증한다."""

        expected = normalized_business_number(
            business.business_number
        )

        if not expected:
            return

        mismatched = {
            item.owner_business_number
            for item in normalized_items
            if (
                item.owner_business_number
                and item.owner_business_number
                != expected
            )
        }

        if mismatched:
            raise TransactionSourceMismatchError(
                "요청한 사업자번호와 CODEF 거래 원본의 "
                "사업자번호가 일치하지 않습니다."
            )

    def _apply_classification(
        self,
        transaction,
        normalized,
    ):
        """사용자 분류가 없는 거래에 규칙 기반 분류 결과를 적용한다."""

        if (
            transaction.classification_source
            == Transaction.ClassificationSource.USER
        ):
            return

        result = self.classifier.classify(
            normalized
        )

        transaction.category = (
            result.category
        )
        transaction.classification_source = (
            result.source
        )
        transaction.classification_confidence = (
            result.confidence
        )

        transaction.save(
            update_fields=[
                "category",
                "classification_source",
                "classification_confidence",
                "updated_at",
            ]
        )