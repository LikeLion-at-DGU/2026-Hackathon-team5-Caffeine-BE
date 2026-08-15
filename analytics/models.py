from django.db import models

from businesses.models import Business


class MonthlyClose(models.Model):
    """월별 장부 마감 승인 기록."""
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="monthly_closes")
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    closed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["business", "year", "month"], name="uniq_business_monthly_close")
        ]

    def __str__(self) -> str:
        return f"{self.business.business_name} {self.year}-{self.month:02d} 마감"