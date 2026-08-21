from django.db import models

from businesses.models import Business


class Subscription(models.Model):
    PLAN_CHOICES = [
        ("PRO", "카페비서 Pro"),
    ]

    STATUS_CHOICES = [
        ("ACTIVE", "구독 이용 중"),
        ("PAST_DUE", "결제 실패"),
        ("CANCELLED", "구독 취소됨"),
        ("EXPIRED", "이용 종료"),
    ]

    business = models.OneToOneField(Business, on_delete=models.CASCADE, related_name="subscription")
    plan_name = models.CharField(max_length=20, choices=PLAN_CHOICES, default="PRO")
    price = models.PositiveIntegerField(default=19900)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    next_billing_date = models.DateField()
    cancelled_at = models.DateField(null=True, blank=True)
    access_until = models.DateField(null=True, blank=True)

    # 카드 원문 대신 PG사가 발급한 빌링키와 표시 정보만 저장한다.
    billing_key_encrypted = models.CharField(max_length=255, blank=True)
    card_company = models.CharField(max_length=50, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)

    # 다음 결제 재시도와 사용자 안내에 필요한 최근 실패 사유.
    last_payment_error = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.business.business_name} - {self.plan_name} ({self.status})"

