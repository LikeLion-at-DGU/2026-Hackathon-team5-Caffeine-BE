from django.db import models


class Business(models.Model):
    """사업장 기본 정보와 과세유형 상태를 갖는다.

    business_number는 비어 있어도(null) 동작해야 한다 — 사업자번호가 아직 없는
    상태에서도 사업장 조회/수정을 테스트할 수 있어야 하기 때문.
    """

    business_name = models.CharField(max_length=100)
    business_number = models.CharField(max_length=20, blank=True, null=True)
    industry_code = models.CharField(max_length=20, blank=True)
    business_type = models.CharField(max_length=100, blank=True)  # 업태
    business_item = models.CharField(max_length=100, blank=True)  # 종목
    business_status = models.CharField(max_length=20, default="UNKNOWN")
    tax_type = models.CharField(max_length=20, default="UNKNOWN")
    tax_type_code = models.CharField(max_length=10, blank=True)
    tax_type_changed_date = models.DateField(null=True, blank=True)
    is_demo = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.business_name} ({self.id})"
    
    
    
"""사업장의 과세유형 변경 이력을 저장한다."""
class TaxTypeHistory(models.Model):

    business = models.ForeignKey(Business,on_delete=models.CASCADE,related_name="tax_type_histories",)
    before_code = models.CharField(max_length=10, blank=True)
    after_code = models.CharField(max_length=10)
    effective_date = models.DateField(null=True, blank=True)
    source = models.CharField(max_length=20, default="CODEF")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # 최신 변경 이력부터 조회
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.business_id}: {self.before_code} -> {self.after_code}"