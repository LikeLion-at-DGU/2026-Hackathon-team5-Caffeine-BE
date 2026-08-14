from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q


class Transaction(models.Model):
    class SourceType(models.TextChoices):
        CARD_PURCHASE = "CARD_PURCHASE", "카드 매입"
        CASH_RECEIPT_PURCHASE = "CASH_RECEIPT_PURCHASE", "현금영수증 매입"
        CASH_RECEIPT_SALE = "CASH_RECEIPT_SALE", "현금영수증 매출"
        TAX_INVOICE = "TAX_INVOICE", "전자세금계산서"

    class TransactionType(models.TextChoices):
        PURCHASE = "PURCHASE", "매입"
        SALE = "SALE", "매출"

    class CancelStatus(models.TextChoices):
        NORMAL = "NORMAL", "정상"
        CANCELLED = "CANCELLED", "취소"

    class Category(models.TextChoices):
        UNCLASSIFIED = "UNCLASSIFIED", "미분류"
        RAW_MATERIAL = "RAW_MATERIAL", "원재료"
        RENT = "RENT", "임차료"
        UTILITIES = "UTILITIES", "공과금"
        SUPPLIES = "SUPPLIES", "소모품"
        ADVERTISING = "ADVERTISING", "광고비"
        DELIVERY = "DELIVERY", "운송·배달비"
        FEES = "FEES", "수수료"
        EQUIPMENT = "EQUIPMENT", "시설·장비"
        OTHER = "OTHER", "기타"

    class ClassificationSource(models.TextChoices):
        UNCLASSIFIED = "UNCLASSIFIED", "미분류"
        AI = "AI", "AI"
        USER = "USER", "사용자"
        RULE = "RULE", "규칙"

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    source_type = models.CharField(max_length=30, choices=SourceType.choices)
    external_id = models.CharField(max_length=255)
    transaction_type = models.CharField(max_length=10, choices=TransactionType.choices)
    transaction_date = models.DateField()
    transaction_time = models.TimeField(null=True, blank=True)
    merchant_name = models.CharField(max_length=255, blank=True)
    merchant_business_number = models.CharField(max_length=20, blank=True)
    supply_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    vat_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    approval_no = models.CharField(max_length=100, blank=True)
    cancel_status = models.CharField(
        max_length=10,
        choices=CancelStatus.choices,
        default=CancelStatus.NORMAL,
    )
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.UNCLASSIFIED,
    )
    classification_source = models.CharField(
        max_length=20,
        choices=ClassificationSource.choices,
        default=ClassificationSource.UNCLASSIFIED,
    )
    classification_confidence = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        null=True,
        blank=True,
    )
    raw_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-transaction_date", "-transaction_time", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "source_type", "external_id"],
                name="uniq_transaction_external_id",
            ),
            models.CheckConstraint(
                condition=(
                    Q(classification_confidence__isnull=True)
                    | Q(classification_confidence__gte=0, classification_confidence__lte=1)
                ),
                name="transaction_confidence_range",
            ),
        ]
        indexes = [
            models.Index(fields=["business", "transaction_date"], name="txn_biz_date_idx"),
            models.Index(
                fields=["business", "transaction_type", "transaction_date"],
                name="txn_biz_type_date_idx",
            ),
            models.Index(fields=["business", "category"], name="txn_biz_category_idx"),
        ]

    def __str__(self):
        return f"{self.business_id}/{self.transaction_date}/{self.merchant_name or self.external_id}"


class TransactionDuplicate(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "확인 대기"
        CONFIRMED = "CONFIRMED", "중복 확정"
        DISMISSED = "DISMISSED", "중복 아님"

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="transaction_duplicates",
    )
    primary_transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name="duplicate_candidates_as_primary",
    )
    suspected_transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name="duplicate_candidates_as_suspected",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    detection_reason = models.JSONField(default=dict, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["primary_transaction", "suspected_transaction"],
                name="uniq_transaction_duplicate_pair",
            ),
            models.CheckConstraint(
                condition=~Q(primary_transaction=F("suspected_transaction")),
                name="duplicate_transactions_differ",
            ),
            models.CheckConstraint(
                condition=Q(confidence__isnull=True) | Q(confidence__gte=0, confidence__lte=1),
                name="duplicate_confidence_range",
            ),
        ]
        indexes = [
            models.Index(fields=["business", "status"], name="txn_dup_biz_status_idx"),
        ]

    def clean(self):
        super().clean()
        if (
            self.primary_transaction_id
            and self.primary_transaction_id == self.suspected_transaction_id
        ):
            raise ValidationError("하나의 거래를 자기 자신의 중복 거래로 등록할 수 없습니다.")

        business_ids = [
            self.business_id,
            getattr(self.primary_transaction, "business_id", None) if self.primary_transaction_id else None,
            getattr(self.suspected_transaction, "business_id", None) if self.suspected_transaction_id else None,
        ]
        if all(business_ids) and len(set(business_ids)) != 1:
            raise ValidationError("중복 거래 쌍과 business는 모두 같은 사업장에 속해야 합니다.")

    def __str__(self):
        return f"{self.primary_transaction_id}<->{self.suspected_transaction_id}: {self.status}"
