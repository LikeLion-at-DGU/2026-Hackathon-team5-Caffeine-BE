from datetime import date
from rest_framework import serializers


class BenchmarkQuerySerializer(serializers.Serializer):
    year = serializers.IntegerField(required=False, default=lambda: date.today().year)
    month = serializers.IntegerField(required=False, default=lambda: date.today().month, min_value=1, max_value=12)
    region = serializers.CharField(required=False, default="성수동 상권")


class BenchmarkRefreshSerializer(serializers.Serializer):
    year = serializers.IntegerField(required=False, default=lambda: date.today().year)
    month = serializers.IntegerField(required=False, default=lambda: date.today().month, min_value=1, max_value=12)
