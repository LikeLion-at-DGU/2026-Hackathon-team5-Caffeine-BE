from django.conf import settings
from django.db import transaction as db_transaction
from django.utils.module_loading import import_string

from ..models import ChatMessage


class ChatService:
    @staticmethod
    def get_responder():
        responder_class = import_string(settings.CHAT_RESPONDER_CLASS)
        return responder_class()

    @classmethod
    def send_message(cls, *, business, content, year, month):
        user_message = ChatMessage.objects.create(
            business=business,
            role=ChatMessage.Role.USER,
            content=content,
            metadata={"year_month": f"{year:04d}-{month:02d}"},
        )
        responder = cls.get_responder()
        reply = responder.reply(
            business=business,
            message=content,
            year=year,
            month=month,
        )
        # 외부 API를 기다리는 동안 DB write transaction을 잡고 있지 않는다.
        with db_transaction.atomic():
            assistant_message = ChatMessage.objects.create(
                business=business,
                role=ChatMessage.Role.ASSISTANT,
                content=reply.content,
                reply_to=user_message,
                metadata={
                    "responder": getattr(responder, "name", responder.__class__.__name__),
                    **reply.metadata,
                },
            )
        return user_message, assistant_message
