from rest_framework import serializers

from businesses.models import Business
from tax.serializers import YearMonthField

from .models import ChatMessage


class ChatMessageCreateSerializer(serializers.Serializer):
    business_id = serializers.PrimaryKeyRelatedField(
        source="business",
        queryset=Business.objects.all(),
    )
    message = serializers.CharField(max_length=2000, trim_whitespace=True)
    year_month = YearMonthField(required=False)


class ChatMessageListQuerySerializer(serializers.Serializer):
    business_id = serializers.PrimaryKeyRelatedField(
        source="business",
        queryset=Business.objects.all(),
    )
    keyword = serializers.CharField(required=False, allow_blank=True, default="")
    q = serializers.CharField(required=False, allow_blank=True, default="")
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=50)


class ChatMessageSerializer(serializers.ModelSerializer):
    message_id = serializers.IntegerField(source="id", read_only=True)
    business_id = serializers.IntegerField(read_only=True)
    reply_to_message_id = serializers.IntegerField(source="reply_to_id", read_only=True)

    class Meta:
        model = ChatMessage
        fields = [
            "message_id",
            "business_id",
            "role",
            "content",
            "reply_to_message_id",
            "metadata",
            "created_at",
        ]
