from django.db import models
from businesses.models import Business


class Report(models.Model):
    STATUS_CHOICES = [
        ("generated", "생성됨"),
        ("approved", "승인됨"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="reports")
    year_month = models.CharField(max_length=7)  # "2026-08"
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="generated")

    generated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    csv_file = models.FileField(upload_to="reports/csv/", null=True, blank=True)
    pdf_file = models.FileField(upload_to="reports/pdf/", null=True, blank=True)

    class Meta:
        unique_together = ("business", "year_month")

    def __str__(self):
        return f"{self.business_id} / {self.year_month} ({self.status})"