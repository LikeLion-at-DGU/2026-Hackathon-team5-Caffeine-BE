from rest_framework import serializers

from transactions.models import Transaction


class AnalyticsPeriodQuerySerializer(serializers.Serializer):
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    month = serializers.IntegerField(min_value=1, max_value=12)


class CostRatioQuerySerializer(AnalyticsPeriodQuerySerializer):
    pass


class TrendQuerySerializer(serializers.Serializer):
    category = serializers.ChoiceField(
        choices=[*Transaction.Category.choices, ("LABOR", "인건비")]
    )
    end_year = serializers.IntegerField(min_value=2000, max_value=2100, required=False)
    end_month = serializers.IntegerField(min_value=1, max_value=12, required=False)
    months = serializers.IntegerField(min_value=2, max_value=24, default=6)

    def validate(self, attrs):
        if ("end_year" in attrs) != ("end_month" in attrs):
            raise serializers.ValidationError("end_year와 end_month는 함께 입력해야 합니다.")
        return attrs


class AnalyticsExportQuerySerializer(AnalyticsPeriodQuerySerializer):
    # DRF가 GET 쿼리의 `format`을 렌더러 선택 예약어로 사용하므로 별도 이름을 쓴다.
    file_type = serializers.ChoiceField(choices=["csv", "pdf"], default="csv")
