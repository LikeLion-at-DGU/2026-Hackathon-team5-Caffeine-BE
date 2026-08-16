from django.contrib import admin

from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("business", "role", "short_content", "created_at")
    list_filter = ("role", "created_at")
    search_fields = ("content", "business__business_name")
    readonly_fields = ("created_at",)

    @admin.display(description="내용")
    def short_content(self, obj):
        return obj.content[:60]
