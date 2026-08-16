from django.db import models


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = "USER", "사용자"
        ASSISTANT = "ASSISTANT", "카페비서"

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )
    role = models.CharField(max_length=20, choices=Role.choices)
    content = models.TextField()
    reply_to = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replies",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["business", "created_at"], name="chat_biz_created_idx"),
        ]

    def __str__(self):
        return f"{self.business_id}/{self.role}: {self.content[:40]}"
