from django.db import models
from businesses.models import Business
from payroll.utils.encryption import encrypt_rrn_front, decrypt_rrn_front


class Employee(models.Model):
    EMPLOYMENT_TYPE_CHOICES = [
        ("FULL_TIME", "4대보험 정직원"),
        ("PART_TIME", "단시간 근로자(주 15시간 미만)"),
        ("FREELANCER", "3.3% 프리랜서"),
    ]

    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name="employees")
    name = models.CharField(max_length=50)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES)
    hourly_wage = models.PositiveIntegerField()
    monthly_contracted_hours = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True
    )
    work_started_at = models.DateField(null=True, blank=True)
    is_long_term_contract = models.BooleanField(default=False)
    rrn_front_encrypted = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def set_rrn_front(self, plain_value: str) -> None:
        """평문 rrn_front를 받아 암호화해서 저장 필드에 세팅."""
        self.rrn_front_encrypted = encrypt_rrn_front(plain_value) if plain_value else ""

    def get_rrn_front(self) -> str:
        """저장된 암호문을 복호화해서 반환. 목록 응답에는 절대 쓰지 않을 것."""
        return decrypt_rrn_front(self.rrn_front_encrypted) if self.rrn_front_encrypted else ""

    def __str__(self) -> str:
        return f"{self.name} ({self.get_employment_type_display()})"

class Payment(models.Model):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="payments")
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()
    work_hours = models.DecimalField(max_digits=6, decimal_places=1)
    gross_pay = models.PositiveIntegerField()
    withholding_tax = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "year", "month"], name="uniq_employee_payment_per_month"
            )
        ]

    def __str__(self) -> str:
        return f"{self.employee.name} {self.year}-{self.month:02d}"