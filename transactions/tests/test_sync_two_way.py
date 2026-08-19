"""TransactionSyncService의 카카오 2-way(추가인증) 흐름 검증.

CODEF 실호출은 하지 않는다 — provider 자리에 Mock을 넣어 CF-03002/CF-00000
응답을 우리가 원하는 시점에 통제해서 돌려주고, 그에 따라 sync()/retry()가
올바르게 반응하는지(저장/롤백/pending 상태/2차 요청 payload)를 확인한다.
"""

from datetime import date
from unittest.mock import Mock

from django.test import TestCase

from businesses.models import Business, CodefConnection
from transactions.models import Transaction
from transactions.services.sync_service import (
    NoPendingTwoWayAuthError,
    PendingTwoWayAuthError,
    TransactionSyncService,
)


def _success(records):
    return {"result": {"code": "CF-00000", "message": "성공"}, "data": records}


def _two_way_required(job_index=0, thread_index=1, jti="mock-jti", timestamp=123456, method="kakao"):
    return {
        "result": {"code": "CF-03002", "message": "추가인증이 필요합니다."},
        "data": {
            "continue2Way": True,
            "jobIndex": job_index,
            "threadIndex": thread_index,
            "jti": jti,
            "twoWayTimestamp": timestamp,
            "method": method,
        },
    }


def _cash_receipt_record(approval_no="CR-001", used_date="20260802"):
    return {
        "resUsedDate": used_date,
        "resUsedTime": "091523",
        "resTransTypeNm": "승인거래",
        "resApprovalNo": approval_no,
        "resSupplyValue": "5000",
        "resVAT": "500",
        "resTotalAmount": "5500",
        "resCompanyIdentityNo": "1234567890",
    }


def _tax_invoice_record(approval_no, supplier="9998887777", contractor="1234567890"):
    return {
        "resSupplyValue": "1000000",
        "resReportingDate": "20260810",
        "resSupplierRegNumber": supplier,
        "resSupplierCompanyName": "카페비서",
        "resContractorRegNumber": contractor,
        "resContractorCompanyName": "거래처",
        "resTotalAmount": "1100000",
        "resTaxAmt": "100000",
        "resIssueDate": "20260810",
        "resApprovalNo": approval_no,
    }


class TransactionSyncTwoWayTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            business_name="카페비서",
            business_number="1234567890",
        )
        self.provider = Mock()
        self.provider.ensure_business_access.return_value = None
        self.service = TransactionSyncService(provider=self.provider)

    def _connection(self):
        return CodefConnection.objects.filter(
            business=self.business,
            connection_type="HOMETAX",
        ).first()

    # --------------------------------------------------
    # 정상 흐름 (2-way 없음) - 회귀 확인
    # --------------------------------------------------

    def test_sync_succeeds_normally_when_no_two_way_needed(self):
        self.provider.get_cash_receipt_sales.return_value = _success(
            [_cash_receipt_record()]
        )

        result = self.service.sync(
            self.business,
            date(2026, 8, 1),
            date(2026, 8, 31),
            [Transaction.SourceType.CASH_RECEIPT_SALE],
        )

        self.assertEqual(result["outcome"], "SUCCESS")
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(Transaction.objects.count(), 1)
        self.assertIsNone(self._connection())

    # --------------------------------------------------
    # 단일 소스에서 CF-03002
    # --------------------------------------------------

    def test_sync_returns_auth_required_and_saves_pending_on_cf03002(self):
        self.provider.get_cash_receipt_sales.return_value = _two_way_required(
            job_index=3, thread_index=7, jti="jti-xyz", timestamp=999,
        )

        result = self.service.sync(
            self.business,
            date(2026, 8, 1),
            date(2026, 8, 31),
            [Transaction.SourceType.CASH_RECEIPT_SALE],
        )

        self.assertEqual(result["outcome"], "AUTH_REQUIRED")
        self.assertEqual(result["pending_source"], Transaction.SourceType.CASH_RECEIPT_SALE)
        self.assertEqual(result["pending_operation"], "")
        self.assertEqual(Transaction.objects.count(), 0)

        conn = self._connection()
        self.assertIsNotNone(conn)
        self.assertTrue(conn.continue_2way)
        self.assertEqual(conn.status, "AUTH_REQUIRED")
        self.assertEqual(conn.job_index, 3)
        self.assertEqual(conn.thread_index, 7)
        self.assertEqual(conn.jti, "jti-xyz")
        self.assertEqual(conn.two_way_timestamp, 999)
        self.assertEqual(conn.pending_source, Transaction.SourceType.CASH_RECEIPT_SALE)
        self.assertEqual(conn.pending_operation, "")
        self.assertEqual(conn.pending_start_date, date(2026, 8, 1))
        self.assertEqual(conn.pending_end_date, date(2026, 8, 31))

    # --------------------------------------------------
    # atomic 롤백: 앞 소스는 성공했지만 뒤 소스에서 CF-03002
    # --------------------------------------------------

    def test_earlier_successful_source_is_rolled_back_when_later_source_needs_auth(self):
        self.provider.get_cash_receipt_sales.return_value = _success(
            [_cash_receipt_record()]
        )
        self.provider.get_tax_invoice_purchases.return_value = _success(
            [_tax_invoice_record("TI-PUR-001")]
        )
        self.provider.get_tax_invoice_sales.return_value = _two_way_required()

        result = self.service.sync(
            self.business,
            date(2026, 8, 1),
            date(2026, 8, 31),
            [
                Transaction.SourceType.CASH_RECEIPT_SALE,
                Transaction.SourceType.TAX_INVOICE,
            ],
        )

        self.assertEqual(result["outcome"], "AUTH_REQUIRED")
        self.assertEqual(result["pending_source"], Transaction.SourceType.TAX_INVOICE)
        self.assertEqual(result["pending_operation"], "SALE")

        # CASH_RECEIPT_SALE도, TAX_INVOICE 매입도 전부 롤백되어야 한다 —
        # 반쪽짜리 sync 결과가 DB에 남으면 안 된다.
        self.assertEqual(Transaction.objects.count(), 0)

        conn = self._connection()
        self.assertEqual(conn.pending_source, Transaction.SourceType.TAX_INVOICE)
        self.assertEqual(conn.pending_operation, "SALE")

    def test_purchase_needs_auth_before_sales_is_even_called(self):
        self.provider.get_tax_invoice_purchases.return_value = _two_way_required()

        result = self.service.sync(
            self.business,
            date(2026, 8, 1),
            date(2026, 8, 31),
            [Transaction.SourceType.TAX_INVOICE],
        )

        self.assertEqual(result["pending_operation"], "PURCHASE")
        # 매입에서 이미 멈췄으니 매출 endpoint는 아예 호출되지 않아야 한다
        # (카카오 알림이 두 개 뜨는 것을 막기 위함).
        self.provider.get_tax_invoice_sales.assert_not_called()

    # --------------------------------------------------
    # 이미 pending이 있는 상태에서 새 sync 차단
    # --------------------------------------------------

    def test_new_sync_is_blocked_while_two_way_is_pending(self):
        self.provider.get_cash_receipt_sales.return_value = _two_way_required()
        self.service.sync(
            self.business,
            date(2026, 8, 1),
            date(2026, 8, 31),
            [Transaction.SourceType.CASH_RECEIPT_SALE],
        )

        with self.assertRaises(PendingTwoWayAuthError):
            self.service.sync(
                self.business,
                date(2026, 9, 1),
                date(2026, 9, 30),
                [Transaction.SourceType.CASH_RECEIPT_SALE],
            )

    def test_credit_card_sales_summary_alone_is_not_blocked_by_hometax_pending(self):
        # CREDIT_CARD_SALES_SUMMARY는 공동인증서 기반이라 카카오 2-way와
        # 무관하다 — HOMETAX 쪽에 pending이 있어도 막히면 안 된다.
        CodefConnection.objects.create(
            business=self.business,
            connection_type="HOMETAX",
            continue_2way=True,
            pending_source=Transaction.SourceType.CASH_RECEIPT_SALE,
        )
        self.provider.get_credit_card_sales_summary.return_value = {
            "result": {"code": "CF-00000"},
            "data": {"resSalesHistoryList": []},
        }

        result = self.service.sync(
            self.business,
            date(2026, 8, 1),
            date(2026, 8, 31),
            ["CREDIT_CARD_SALES_SUMMARY"],
        )

        self.assertEqual(result["outcome"], "SUCCESS")

    # --------------------------------------------------
    # retry()
    # --------------------------------------------------

    def test_retry_without_pending_raises(self):
        with self.assertRaises(NoPendingTwoWayAuthError):
            self.service.retry(self.business)

    def test_retry_reissues_same_endpoint_with_two_way_info_and_clears_pending(self):
        self.provider.get_cash_receipt_sales.return_value = _two_way_required(
            job_index=1, thread_index=2, jti="jti-1", timestamp=1000,
        )
        self.service.sync(
            self.business,
            date(2026, 8, 1),
            date(2026, 8, 31),
            [Transaction.SourceType.CASH_RECEIPT_SALE],
        )

        # 카카오 인증을 완료했다고 가정 — 이제 2차 요청은 성공한다.
        self.provider.get_cash_receipt_sales.return_value = _success(
            [_cash_receipt_record()]
        )

        result = self.service.retry(self.business)

        self.assertEqual(result["outcome"], "SUCCESS")
        self.assertEqual(Transaction.objects.count(), 1)

        conn = self._connection()
        self.assertFalse(conn.continue_2way)
        self.assertEqual(conn.status, "CONNECTED")
        self.assertEqual(conn.pending_source, "")
        self.assertIsNone(conn.pending_start_date)

        # 2차 요청이 정확히 저장해둔 job_index/thread_index/jti/timestamp +
        # simpleAuth="1"로 다시 호출됐는지 확인.
        _, kwargs = self.provider.get_cash_receipt_sales.call_args
        self.assertEqual(
            kwargs["two_way_info"],
            {"jobIndex": 1, "threadIndex": 2, "jti": "jti-1", "twoWayTimestamp": 1000},
        )
        self.assertEqual(kwargs["simple_auth"], "1")

    def test_retry_for_tax_invoice_sale_refetches_purchases_fresh_and_continues_sales_only(self):
        # 매입은 이미 성공했었고(하지만 atomic 롤백으로 저장은 안 됐고),
        # 매출만 2-way가 걸린 상황을 만든다.
        self.provider.get_tax_invoice_purchases.return_value = _success(
            [_tax_invoice_record("TI-PUR-001")]
        )
        self.provider.get_tax_invoice_sales.return_value = _two_way_required(
            job_index=5, thread_index=9, jti="jti-sale", timestamp=555,
        )

        self.service.sync(
            self.business,
            date(2026, 8, 1),
            date(2026, 8, 31),
            [Transaction.SourceType.TAX_INVOICE],
        )

        self.assertEqual(Transaction.objects.count(), 0)

        # 카카오 인증 완료 후 매출 2차 요청은 성공.
        self.provider.get_tax_invoice_sales.return_value = _success(
            [_tax_invoice_record("TI-SALE-001", supplier="1234567890", contractor="5556667777")]
        )
        self.provider.get_tax_invoice_purchases.reset_mock()
        self.provider.get_tax_invoice_sales.reset_mock(return_value=False, side_effect=False)
        self.provider.get_tax_invoice_sales.return_value = _success(
            [_tax_invoice_record("TI-SALE-001", supplier="1234567890", contractor="5556667777")]
        )

        result = self.service.retry(self.business)

        self.assertEqual(result["outcome"], "SUCCESS")
        # 매입(재조회, fresh) + 매출(2차 요청) 둘 다 저장되어야 한다.
        # (normalize_tax_invoices는 external_id를 "TAX_INVOICE_{PURCHASE|SALE}:
        # {approval_no}" 형식으로 만든다 — helpers.external_id() 참고.)
        self.assertEqual(Transaction.objects.count(), 2)
        self.assertTrue(
            Transaction.objects.filter(
                external_id="TAX_INVOICE_PURCHASE:TI-PUR-001"
            ).exists()
        )
        self.assertTrue(
            Transaction.objects.filter(
                external_id="TAX_INVOICE_SALE:TI-SALE-001"
            ).exists()
        )

        # 매입은 fresh 1차 요청(2-way 정보 없이) 이어야 한다.
        _, purchase_kwargs = self.provider.get_tax_invoice_purchases.call_args
        self.assertIsNone(purchase_kwargs["two_way_info"])
        self.assertIsNone(purchase_kwargs["simple_auth"])

        # 매출은 2-way 정보를 실어 보내야 한다.
        _, sales_kwargs = self.provider.get_tax_invoice_sales.call_args
        self.assertEqual(
            sales_kwargs["two_way_info"],
            {"jobIndex": 5, "threadIndex": 9, "jti": "jti-sale", "twoWayTimestamp": 555},
        )
        self.assertEqual(sales_kwargs["simple_auth"], "1")

    def test_retry_still_requiring_auth_updates_pending_again(self):
        self.provider.get_cash_receipt_sales.return_value = _two_way_required(
            job_index=1, thread_index=1, jti="jti-first", timestamp=100,
        )
        self.service.sync(
            self.business,
            date(2026, 8, 1),
            date(2026, 8, 31),
            [Transaction.SourceType.CASH_RECEIPT_SALE],
        )

        # N차 인증: 재시도해도 또 추가인증이 필요한 경우.
        self.provider.get_cash_receipt_sales.return_value = _two_way_required(
            job_index=2, thread_index=2, jti="jti-second", timestamp=200,
        )

        result = self.service.retry(self.business)

        self.assertEqual(result["outcome"], "AUTH_REQUIRED")
        conn = self._connection()
        self.assertTrue(conn.continue_2way)
        self.assertEqual(conn.jti, "jti-second")
        self.assertEqual(conn.job_index, 2)