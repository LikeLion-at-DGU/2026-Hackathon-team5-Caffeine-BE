from django.test import TestCase

from businesses.models import Business

from chat.models import ChatMessage


class ChatMessageModelTests(TestCase):
    def test_assistant_message_can_reference_user_message(self):
        business = Business.objects.create(business_name="카페비서 데모카페")
        user_message = ChatMessage.objects.create(
            business=business,
            role=ChatMessage.Role.USER,
            content="이번 달 부가세 얼마야?",
        )
        assistant_message = ChatMessage.objects.create(
            business=business,
            role=ChatMessage.Role.ASSISTANT,
            content="확인해 볼게요.",
            reply_to=user_message,
        )

        self.assertEqual(assistant_message.reply_to, user_message)
        self.assertEqual(user_message.replies.get(), assistant_message)
