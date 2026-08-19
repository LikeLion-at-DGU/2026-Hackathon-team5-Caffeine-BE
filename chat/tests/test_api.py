from datetime import date
from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from businesses.models import Business
from transactions.models import Transaction

from chat.models import ChatMessage


class ChatApiTests(APITestCase):
    def setUp(self):
        self.business = Business.objects.create(
            business_name="카페비서 데모카페",
            tax_type="GENERAL",
        )
        self.other_business = Business.objects.create(
            business_name="다른 카페",
            tax_type="GENERAL",
        )
        Transaction.objects.create(
            business=self.business,
            source_type=Transaction.SourceType.CASH_RECEIPT_SALE,
            external_id="sale-001",
            transaction_type=Transaction.TransactionType.SALE,
            transaction_date=date(2026, 8, 3),
            total_amount=Decimal("55000.00"),
            supply_amount=Decimal("50000.00"),
            vat_amount=Decimal("5000.00"),
        )

    def test_post_creates_question_and_answer(self):
        response = self.client.post(
            reverse("chat-message-list-create"),
            {
                "business_id": self.business.id,
                "message": "8월 매출 거래 알려줘",
                "year_month": "2026-08",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["data"]["answer"],
            response.data["data"]["assistant_message"]["content"],
        )
        self.assertEqual(response.data["code"], "CHAT_MESSAGE_CREATED")
        data = response.data["data"]
        self.assertEqual(data["user_message"]["role"], ChatMessage.Role.USER)
        self.assertEqual(data["assistant_message"]["role"], ChatMessage.Role.ASSISTANT)
        self.assertIn("매출 1건", data["assistant_message"]["content"])
        self.assertEqual(ChatMessage.objects.count(), 2)

    def test_get_returns_only_requested_business_history(self):
        ChatMessage.objects.create(
            business=self.business,
            role=ChatMessage.Role.USER,
            content="내 질문",
        )
        ChatMessage.objects.create(
            business=self.other_business,
            role=ChatMessage.Role.USER,
            content="다른 질문",
        )

        response = self.client.get(
            reverse("chat-message-list-create"),
            {"business_id": self.business.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["pagination"]["total_count"], 1)
        self.assertEqual(response.data["data"]["items"][0]["content"], "내 질문")

    def test_post_rejects_invalid_period(self):
        response = self.client.post(
            reverse("chat-message-list-create"),
            {
                "business_id": self.business.id,
                "message": "질문",
                "year_month": "2026-13",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "INVALID_CHAT_MESSAGE")

    def test_post_requires_business(self):
        response = self.client.post(
            reverse("chat-message-list-create"),
            {"message": "질문", "year_month": "2026-08"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "INVALID_CHAT_MESSAGE")

    def test_get_filters_by_keyword_and_q(self):
        ChatMessage.objects.create(
            business=self.business,
            role=ChatMessage.Role.USER,
            content="부가세 절세 방법 알려줘",
        )
        ChatMessage.objects.create(
            business=self.business,
            role=ChatMessage.Role.USER,
            content="원천세 신고 기한이 언제야?",
        )

        # 1. keyword로 검색
        res1 = self.client.get(
            reverse("chat-message-list-create"),
            {"business_id": self.business.id, "keyword": "부가세"},
        )
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.data["data"]["pagination"]["total_count"], 1)
        self.assertIn("부가세", res1.data["data"]["items"][0]["content"])

        # 2. q로 검색
        res2 = self.client.get(
            reverse("chat-message-list-create"),
            {"business_id": self.business.id, "q": "원천세"},
        )
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.data["data"]["pagination"]["total_count"], 1)
        self.assertIn("원천세", res2.data["data"]["items"][0]["content"])
