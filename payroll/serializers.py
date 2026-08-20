from rest_framework import serializers

from payroll.models import Employee, Payment
from payroll.services.payment_service import get_payslip_data

class EmployeeCreateSerializer(serializers.ModelSerializer):
    rrn_front = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Employee
        fields = [
            "name",
            "employment_type",
            "hourly_wage",
            "monthly_contracted_hours",
            "work_started_at",
            "is_long_term_contract",
            "rrn_front",
        ]

    def create(self, validated_data):
        rrn_front = validated_data.pop("rrn_front", "")
        employee = Employee(**validated_data)
        employee.set_rrn_front(rrn_front)
        employee.save()
        return employee


class EmployeeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = [
            "name",
            "employment_type",
            "hourly_wage",
            "monthly_contracted_hours",
            "work_started_at",
            "is_long_term_contract",
            "status",
        ]
        extra_kwargs = {field: {"required": False} for field in fields}


class EmployeeListItemSerializer(serializers.ModelSerializer):
    employee_id = serializers.IntegerField(source="id")

    class Meta:
        model = Employee
        fields = [
            "employee_id",
            "name",
            "employment_type",
            "hourly_wage",
            "monthly_contracted_hours",
            "work_started_at",
            "is_long_term_contract",
            "status",
        ]
        # rrn_front는 절대 포함하지 않음 — 민감정보 노출 방지 (2026-08-13 결정)




class PaymentCreateSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    year = serializers.IntegerField()
    month = serializers.IntegerField(min_value=1, max_value=12)
    work_hours = serializers.DecimalField(max_digits=6, decimal_places=1, min_value=0)


class PaymentUpdateSerializer(serializers.Serializer):
    work_hours = serializers.DecimalField(max_digits=6, decimal_places=1, min_value=0)


class PaymentListItemSerializer(serializers.ModelSerializer):
    payment_id = serializers.IntegerField(source="id")
    employee_id = serializers.IntegerField(source="employee.id")
    employee_name = serializers.CharField(source="employee.name")
    employment_type = serializers.CharField(source="employee.employment_type")
    is_long_term_contract = serializers.BooleanField(source="employee.is_long_term_contract")
    income_tax = serializers.SerializerMethodField()
    local_income_tax = serializers.SerializerMethodField()
    national_pension = serializers.SerializerMethodField()
    health_insurance = serializers.SerializerMethodField()
    long_term_care = serializers.SerializerMethodField()
    employment_insurance = serializers.SerializerMethodField()
    insurance_total = serializers.SerializerMethodField()
    deductions_total = serializers.SerializerMethodField()
    net_pay = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "payment_id", "employee_id", "employee_name", "employment_type",
            "is_long_term_contract", "year", "month", "work_hours", "gross_pay",
            "withholding_tax", "income_tax", "local_income_tax",
            "national_pension", "health_insurance", "long_term_care",
            "employment_insurance", "insurance_total", "deductions_total", "net_pay",
        ]

    @staticmethod
    def _breakdown(payment):
        # 한 급여 건을 직렬화할 때 같은 계산을 여러 필드에서 반복하지 않는다.
        if not hasattr(payment, "_payslip_data_cache"):
            payment._payslip_data_cache = get_payslip_data(payment)
        return payment._payslip_data_cache

    def get_income_tax(self, payment):
        return self._breakdown(payment)["income_tax"]

    def get_local_income_tax(self, payment):
        return self._breakdown(payment)["local_income_tax"]

    def get_national_pension(self, payment):
        return self._breakdown(payment)["national_pension"]

    def get_health_insurance(self, payment):
        return self._breakdown(payment)["health_insurance"]

    def get_long_term_care(self, payment):
        return self._breakdown(payment)["long_term_care"]

    def get_employment_insurance(self, payment):
        return self._breakdown(payment)["employment_insurance"]

    def get_insurance_total(self, payment):
        data = self._breakdown(payment)
        return (
            data["national_pension"]
            + data["health_insurance"]
            + data["long_term_care"]
            + data["employment_insurance"]
        )

    def get_deductions_total(self, payment):
        return self._breakdown(payment)["deductions_total"]

    def get_net_pay(self, payment):
        return self._breakdown(payment)["net_pay"]
