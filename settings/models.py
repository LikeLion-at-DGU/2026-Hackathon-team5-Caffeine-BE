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

    # 결제수단 — 카드번호 원본은 절대 저장하지 않음, PG사 발급 토큰만 저장
    billing_key_encrypted = models.CharField(max_length=255, blank=True)
    card_company = models.CharField(max_length=50, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)

    # 정기 결제(자동 갱신) 실패 시 사유 — 성공하면 빈 문자열로 초기화됨
    last_payment_error = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.business.business_name} - {self.plan_name} ({self.status})"

