from django.db import models
from django.db.models import Q


class DeductionReview(models.Model):
    class SuggestedStatus(models.TextChoices):
        DEDUCTIBLE_CANDIDATE = "DEDUCTIBLE_CANDIDATE", "공제 후보"
        NON_DEDUCTIBLE_CANDIDATE = "NON_DEDUCTIBLE_CANDIDATE", "불공제 후보"
        REVIEW_REQUIRED = "REVIEW_REQUIRED", "검토 필요"

    class SuggestionSource(models.TextChoices):
        CODEF = "CODEF", "CODEF"
        RULE = "RULE", "규칙"
        AI = "AI", "AI"

    class ConfirmedStatus(models.TextChoices):
        UNCONFIRMED = "UNCONFIRMED", "미확정"
        DEDUCTIBLE = "DEDUCTIBLE", "공제"
        NON_DEDUCTIBLE = "NON_DEDUCTIBLE", "불공제"

    transaction = models.OneToOneField(
        "transactions.Transaction",
        on_delete=models.CASCADE,
        related_name="deduction_review",
    )
    suggested_status = models.CharField(
        max_length=40,
        choices=SuggestedStatus.choices,
        default=SuggestedStatus.REVIEW_REQUIRED,
    )
    suggestion_source = models.CharField(
        max_length=20,
        choices=SuggestionSource.choices,
        default=SuggestionSource.RULE,
    )
    suggestion_reason = models.TextField(blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=4, null=True, blank=True)
    confirmed_status = models.CharField(
        max_length=20,
        choices=ConfirmedStatus.choices,
        default=ConfirmedStatus.UNCONFIRMED,
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-transaction__transaction_date", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(confidence__isnull=True) | Q(confidence__gte=0, confidence__lte=1),
                name="deduction_confidence_range",
            ),
        ]
        indexes = [
            models.Index(fields=["confirmed_status"], name="deduction_confirmed_idx"),
            models.Index(fields=["suggested_status"], name="deduction_suggested_idx"),
        ]

    def __str__(self):
        return f"{self.transaction_id}: {self.suggested_status}/{self.confirmed_status}"


class MonthlyClose(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "진행 중"
        CLOSED = "CLOSED", "마감"

    business = models.ForeignKey(
        "businesses.Business",
        on_delete=models.CASCADE,
        related_name="monthly_closes",
    )
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    sales_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    purchase_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    output_vat = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    deductible_input_vat = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    estimated_vat = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    snapshot = models.JSONField(default=dict, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "-month"]
        constraints = [
            models.UniqueConstraint(
                fields=["business", "year", "month"],
                name="uniq_business_monthly_close",
            ),
            models.CheckConstraint(
                condition=Q(month__gte=1, month__lte=12),
                name="monthly_close_month_range",
            ),
        ]
        indexes = [
            models.Index(
                fields=["business", "status", "year", "month"],
                name="close_biz_status_period_idx",
            ),
        ]

    @property
    def year_month(self):
        return f"{self.year:04d}-{self.month:02d}"

    def __str__(self):
        return f"{self.business_id}/{self.year_month}: {self.status}"
