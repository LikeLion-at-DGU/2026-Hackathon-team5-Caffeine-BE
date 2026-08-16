from django.db import models

class Business(models.Model):
    """사업장 기본 정보와 과세유형 상태를 갖는다.

    business_number는 비어 있어도(null) 동작해야 한다 — 사업자번호가 아직 없는
    상태에서도 사업장 조회/수정을 테스트할 수 있어야 하기 때문.
    """

    business_name = models.CharField(max_length=100)
    representative_name = models.CharField(max_length=50, blank=True) #추가
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
    tax_accountant_email = models.EmailField(null=True, blank=True)

    def __str__(self):
        return f"{self.business_name} ({self.id})"
    
    
"""사업장의 과세유형 변경 이력을 저장"""
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
    
    
"""사업장별 CARD/HOMETAX 연결 상태를 저장"""
class CodefConnection(models.Model):

    CONNECTION_TYPES = [
        ("CARD", "CARD"),
        ("HOMETAX", "HOMETAX"),
    ]

    AUTH_STATUS = [
        ("DISCONNECTED", "DISCONNECTED"),
        ("AUTH_REQUIRED", "AUTH_REQUIRED"),
        ("CONNECTED", "CONNECTED"),
        ("FAILED", "FAILED"),
    ]

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="codef_connections",
    )
    connection_type = models.CharField(
        max_length=20,
        choices=CONNECTION_TYPES,
    )
    status = models.CharField(
        max_length=20,
        choices=AUTH_STATUS,
        default="DISCONNECTED",
    )

    # 연결 성공 시 발급된 Connected ID
    connected_id = models.CharField(max_length=255, blank=True)

    # HOMETAX 2-way 인증 진행에 필요한 임시 정보
    continue_2way = models.BooleanField(default=False)
    method = models.CharField(max_length=50, blank=True)
    job_index = models.IntegerField(null=True, blank=True)
    thread_index = models.IntegerField(null=True, blank=True)
    jti = models.CharField(max_length=255, blank=True)
    two_way_timestamp = models.BigIntegerField(null=True, blank=True)

    last_error_code = models.CharField(max_length=50, blank=True)
    last_error_message = models.TextField(blank=True)

    # 최근 CODEF 응답을 디버깅용으로 저장
    last_raw_response = models.JSONField(null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # 사업장별 연결 유형(CARD/HOMETAX)은 하나의 레코드만 유지한다.
            models.UniqueConstraint(
                fields=["business", "connection_type"],
                name="uniq_business_codef_connection",
            )
        ]

    def __str__(self):
        return f"{self.business_id}/{self.connection_type}: {self.status}"