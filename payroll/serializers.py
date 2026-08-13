from rest_framework import serializers

from payroll.models import Employee


class EmployeeCreateSerializer(serializers.ModelSerializer):
    rrn_front = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Employee
        fields = ["name", "employment_type", "hourly_wage", "monthly_contracted_hours", "rrn_front"]

    def create(self, validated_data):
        rrn_front = validated_data.pop("rrn_front", "")
        employee = Employee(**validated_data)
        employee.set_rrn_front(rrn_front)
        employee.save()
        return employee


class EmployeeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ["name", "employment_type", "hourly_wage", "monthly_contracted_hours"]
        extra_kwargs = {field: {"required": False} for field in fields}


class EmployeeListItemSerializer(serializers.ModelSerializer):
    employee_id = serializers.IntegerField(source="id")
    # TODO: 재직/퇴사 상태 관리가 필요해지면 모델에 status 필드 추가 필요.
    # 현재는 삭제(DELETE)로만 관리하므로 목록에는 항상 ACTIVE로 응답.
    status = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ["employee_id", "name", "employment_type", "hourly_wage", "monthly_contracted_hours", "status"]
        # rrn_front는 절대 포함하지 않음 — 민감정보 노출 방지 (2026-08-13 결정)

    def get_status(self, obj):
        return "ACTIVE"