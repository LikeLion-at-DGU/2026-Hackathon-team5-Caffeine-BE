import json
from types import SimpleNamespace
from unittest.mock import Mock

from django.test import TestCase, override_settings

from businesses.models import Business
from chat.models import ChatMessage
from chat.services.openai_responder import OFFICIAL_TAX_DOMAINS, OpenAIChatResponder
from payroll.models import Employee, Payment
from payroll.services import payment_service


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
        employee = Employee.objects.create(
            business=self.business,
            name="장예은",
            employment_type="FULL_TIME",
            hourly_wage=12000,
        )
        Payment.objects.create(
            employee=employee,
            year=2026,
            month=8,
            work_hours=100,
            gross_pay=1_200_000,
            withholding_tax=12_000,
        )
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
        self.assertIn("payroll", context["SERVICE_CONTEXT"])
        payroll_facts = context["SERVICE_CONTEXT"]["payroll"]["facts"]
        self.assertEqual(payroll_facts["employee_count"], 1)
        self.assertGreater(payroll_facts["total_labor_cost"], 1_200_000)
        self.assertEqual(payroll_facts["withholding_tax"], 12_000)
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

    def test_payroll_context_reads_latest_database_values_on_every_reply(self):
        employee = Employee.objects.create(
            business=self.business,
            name="박서연",
            employment_type="PART_TIME",
            hourly_wage=10_000,
            is_long_term_contract=True,
        )
        payment = payment_service.create_payment(
            self.business.id,
            employee.id,
            2026,
            8,
            80,
        )
        client = Mock()
        client.responses.create.return_value = SimpleNamespace(
            output_text="인건비를 확인했어요.",
            output=[],
            usage=None,
        )
        responder = OpenAIChatResponder(client=client)

        responder.reply(
            business=self.business,
            message="이번 달 인건비 얼마야?",
            year=2026,
            month=8,
        )
        first_context = json.loads(client.responses.create.call_args.kwargs["input"])
        first_payroll = first_context["SERVICE_CONTEXT"]["payroll"]["facts"]

        employee.hourly_wage = 12_000
        employee.save(update_fields=["hourly_wage"])
        payment_service.update_payment(self.business.id, payment.id, 80)

        responder.reply(
            business=self.business,
            message="수정된 인건비 다시 알려줘",
            year=2026,
            month=8,
        )
        second_context = json.loads(client.responses.create.call_args.kwargs["input"])
        second_payroll = second_context["SERVICE_CONTEXT"]["payroll"]["facts"]

        new_employee = Employee.objects.create(
            business=self.business,
            name="신규직원",
            employment_type="FULL_TIME",
            hourly_wage=11_000,
        )
        payment_service.create_payment(
            self.business.id,
            new_employee.id,
            2026,
            8,
            40,
        )
        responder.reply(
            business=self.business,
            message="새 직원까지 포함한 인건비 알려줘",
            year=2026,
            month=8,
        )
        third_context = json.loads(client.responses.create.call_args.kwargs["input"])
        third_payroll = third_context["SERVICE_CONTEXT"]["payroll"]["facts"]

        self.assertEqual(first_payroll["employee_count"], 1)
        self.assertEqual(second_payroll["employee_count"], 1)
        self.assertGreater(
            second_payroll["total_labor_cost"],
            first_payroll["total_labor_cost"],
        )
        self.assertEqual(third_payroll["employee_count"], 2)
        self.assertGreater(
            third_payroll["total_labor_cost"],
            second_payroll["total_labor_cost"],
        )

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
