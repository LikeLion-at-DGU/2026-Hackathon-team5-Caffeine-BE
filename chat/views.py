import math

from django.utils import timezone
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.responses import error_response, success_response
from core.permissions import check_business_owner
from tax.services.periods import parse_year_month

from .models import ChatMessage
from .serializers import (
    ChatMessageCreateSerializer,
    ChatMessageListQuerySerializer,
    ChatMessageSerializer,
)
from .services.chat_service import ChatService


def _check_business_owner(request, business):
    """core.permissions.check_business_owner 위임 — IDOR 검증 로직 단일화."""
    return check_business_owner(request, business)


class ChatMessageView(APIView):
    # 유료 LLM 호출 남용 방어
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "llm"

    def post(self, request):
        serializer = ChatMessageCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                code="INVALID_CHAT_MESSAGE",
                message="질문 내용이 올바르지 않습니다.",
                errors=serializer.errors,
            )
        params = serializer.validated_data
        owner_err = _check_business_owner(request, params["business"])
        if owner_err:
            return owner_err

        if params.get("year_month"):
            year, month = parse_year_month(params["year_month"])
        else:
            today = timezone.localdate()
            year, month = today.year, today.month

        user_message, assistant_message = ChatService.send_message(
            business=params["business"],
            content=params["message"],
            year=year,
            month=month,
        )
        return success_response(
            code="CHAT_MESSAGE_CREATED",
            message="카페비서가 질문에 답변했습니다.",
            data={
                "answer": assistant_message.content,
                "user_message": ChatMessageSerializer(user_message).data,
                "assistant_message": ChatMessageSerializer(assistant_message).data,
            },
            status=201,
        )

    def get(self, request):
        query = ChatMessageListQuerySerializer(data=request.query_params)
        if not query.is_valid():
            return error_response(
                code="INVALID_CHAT_QUERY",
                message="대화 이력 조회 조건이 올바르지 않습니다.",
                errors=query.errors,
            )
        params = query.validated_data
        owner_err = _check_business_owner(request, params["business"])
        if owner_err:
            return owner_err

        messages = ChatMessage.objects.filter(business=params["business"])
        search_query = params.get("keyword") or params.get("q")
        if search_query:
            messages = messages.filter(content__icontains=search_query)
        total_count = messages.count()
        offset = (params["page"] - 1) * params["page_size"]
        items = messages[offset : offset + params["page_size"]]
        return success_response(
            code="CHAT_MESSAGE_LIST_SUCCESS",
            message="대화 이력을 조회했습니다.",
            data={
                "items": ChatMessageSerializer(items, many=True).data,
                "pagination": {
                    "page": params["page"],
                    "page_size": params["page_size"],
                    "total_count": total_count,
                    "total_pages": math.ceil(total_count / params["page_size"]),
                },
            },
        )
