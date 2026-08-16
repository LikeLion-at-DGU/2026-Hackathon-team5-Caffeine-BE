import json
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import TestCase, override_settings

from businesses.models import Business
from chat.models import ChatMessage
from chat.services.openai_responder import OFFICIAL_TAX_DOMAINS, OpenAIChatResponder


@override_settings(
    OPENAI_API_KEY="test-key",
    OPENAI_MODEL="gpt-5.6-luna",
    OPENAI_TIMEOUT_SECONDS=20,
    OPENAI_MAX_OUTPUT_TOKENS=1200,
    OPENAI_REASONING_EFFORT="none",
)
class OpenAIChatResponderTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            business_name="카페비서 데모카페",
            business_number="123-45-67890",
            tax_type="GENERAL",
        )

    def test_reply_supplies_service_context_history_and_official_search(self):
        ChatMessage.objects.create(
            business=self.business,
            role=ChatMessage.Role.USER,
            content="안녕",
        )
        ChatMessage.objects.create(
            business=self.business,
            role=ChatMessage.Role.ASSISTANT,
            content="안녕하세요! 카페비서예요 ☕",
        )
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            output_text="이번 달 거래 내역을 확인했어요.",
            output=[],
            usage=SimpleNamespace(input_tokens=100, output_tokens=20, total_tokens=120),
        )

        reply = OpenAIChatResponder(client=client).reply(
            business=self.business,
            message="이번 달 거래 알려줘",
            year=2026,
            month=8,
        )

        self.assertEqual(reply.content, "이번 달 거래 내역을 확인했어요.")
        self.assertEqual(reply.metadata["provider"], "OPENAI")
        self.assertFalse(reply.metadata["fallback"])
        kwargs = client.responses.create.call_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-5.6-luna")
        self.assertFalse(kwargs["store"])
        self.assertEqual(
            kwargs["tools"][0]["filters"]["allowed_domains"],
            OFFICIAL_TAX_DOMAINS,
        )
        self.assertIn("인사를 매번 반복하지 마세요", kwargs["instructions"])
        context = json.loads(kwargs["input"])
        self.assertEqual(context["BUSINESS"]["id"], self.business.id)
        self.assertNotIn("business_number", context["BUSINESS"])
        self.assertIn("transactions", context["SERVICE_CONTEXT"])
        self.assertEqual(len(context["CHAT_HISTORY"]), 2)

    def test_first_turn_requests_friendly_cafe_assistant_greeting(self):
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            output_text="안녕하세요! 카페비서예요 ☕ 무엇을 도와드릴까요?",
            output=[],
            usage=None,
        )

        OpenAIChatResponder(client=client).reply(
            business=self.business,
            message="안녕",
            year=2026,
            month=8,
        )

        instructions = client.responses.create.call_args.kwargs["instructions"]
        self.assertIn("안녕하세요! 카페비서예요 ☕", instructions)

    def test_official_citations_are_exposed_and_appended_as_links(self):
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            output_text="공제 여부는 거래 요건을 함께 확인해야 해요.",
            output=[
                SimpleNamespace(type="web_search_call"),
                SimpleNamespace(
                    type="message",
                    content=[
                        SimpleNamespace(
                            annotations=[
                                SimpleNamespace(
                                    type="url_citation",
                                    url="https://www.law.go.kr/example",
                                    title="국가법령정보센터",
                                ),
                                SimpleNamespace(
                                    type="url_citation",
                                    url="https://example.com/not-allowed",
                                    title="비공식 블로그",
                                ),
                            ]
                        )
                    ],
                ),
            ],
            usage=None,
        )

        reply = OpenAIChatResponder(client=client).reply(
            business=self.business,
            message="의제매입세액 공제 요건 알려줘",
            year=2026,
            month=8,
        )

        self.assertTrue(reply.metadata["web_searched"])
        self.assertEqual(len(reply.metadata["citations"]), 1)
        self.assertIn("https://www.law.go.kr/example", reply.content)
        self.assertNotIn("example.com/not-allowed", reply.content)

    def test_api_error_uses_rule_based_fallback(self):
        client = Mock()
        client.responses.create.side_effect = TimeoutError("timeout")

        reply = OpenAIChatResponder(client=client).reply(
            business=self.business,
            message="이번 달 거래 알려줘",
            year=2026,
            month=8,
        )

        self.assertEqual(reply.metadata["provider"], "RULE_BASED")
        self.assertTrue(reply.metadata["fallback"])
        self.assertEqual(reply.metadata["fallback_reason"], "TIMEOUTERROR")
        self.assertIn("매출 0건", reply.content)

    @override_settings(OPENAI_API_KEY="")
    def test_missing_key_uses_rule_based_fallback_without_api_call(self):
        client = Mock()

        reply = OpenAIChatResponder(client=client).reply(
            business=self.business,
            message="이번 달 거래 알려줘",
            year=2026,
            month=8,
        )

        client.responses.create.assert_not_called()
        self.assertEqual(reply.metadata["fallback_reason"], "MISSING_API_KEY")
