from rest_framework import serializers
from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ["year_month", "status", "generated_at", "approved_at", "sent_at"]