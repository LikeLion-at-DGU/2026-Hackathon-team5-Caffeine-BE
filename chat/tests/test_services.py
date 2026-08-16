from datetime import date
from decimal import Decimal

from django.test import TestCase

from businesses.models import Business
from transactions.models import Transaction

from tax.models import DeductionReview

from chat.models import ChatMessage
from chat.services.chat_service import ChatService
from chat.services.responder import RuleBasedChatResponder


class ChatServiceTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            business_name="카페비서 데모카페",
            tax_type="GENERAL",
        )
        self.purchase = self.create_transaction(
            "purchase-001",
            Transaction.TransactionType.PURCHASE,
        )
        self.sale = self.create_transaction("sale-001", Transaction.TransactionType.SALE)

    def create_transaction(self, external_id, transaction_type):
        return Transaction.objects.create(
            business=self.business,
            source_type=Transaction.SourceType.CARD_PURCHASE,
            external_id=external_id,
            transaction_type=transaction_type,
            transaction_date=date(2026, 8, 3),
            total_amount=Decimal("110000.00"),
            supply_amount=Decimal("100000.00"),
            vat_amount=Decimal("10000.00"),
        )

    def test_vat_reply_uses_tax_forecast(self):
        DeductionReview.objects.create(
            transaction=self.purchase,
            confirmed_status=DeductionReview.ConfirmedStatus.DEDUCTIBLE,
        )

        reply = RuleBasedChatResponder().reply(
            business=self.business,
            message="이번 달 부가세 얼마야?",
            year=2026,
            month=8,
        )

        self.assertEqual(reply.metadata["intent"], "VAT_FORECAST")
        self.assertIn("매출세액은 10,000원", reply.content)
        self.assertIn("예상 납부세액은 0원", reply.content)

    def test_deduction_reply_reports_unconfirmed_count(self):
        reply = RuleBasedChatResponder().reply(
            business=self.business,
            message="공제 확인할 거 있어?",
            year=2026,
            month=8,
        )

        self.assertEqual(reply.metadata["intent"], "DEDUCTION_STATUS")
        self.assertEqual(reply.metadata["counts"]["unconfirmed"], 1)

    def test_analytics_question_uses_analytics_service_result(self):
        reply = RuleBasedChatResponder().reply(
            business=self.business,
            message="비용이 지난달보다 왜 늘었어?",
            year=2026,
            month=8,
        )

        self.assertEqual(reply.metadata["intent"], "ANALYTICS")
        self.assertTrue(reply.metadata["analytics_available"])
        self.assertIn("총 지출", reply.content)

    def test_send_message_persists_user_and_assistant_pair(self):
        user_message, assistant_message = ChatService.send_message(
            business=self.business,
            content="8월 거래 알려줘",
            year=2026,
            month=8,
        )

        self.assertEqual(ChatMessage.objects.count(), 2)
        self.assertEqual(assistant_message.reply_to, user_message)
        self.assertEqual(assistant_message.metadata["responder"], "RULE_BASED")
        self.assertEqual(assistant_message.metadata["intent"], "TRANSACTION_SUMMARY")
