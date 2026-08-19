from django.db import models


class Business(models.Model):
    """사업장 기본 정보 및 과세유형 상태."""

    business_name = models.CharField(max_length=100)
    representative_name = models.CharField(max_length=50, blank=True)
    business_number = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )
    industry_code = models.CharField(max_length=20, blank=True)
    business_type = models.CharField(max_length=100, blank=True)  # 업태
    business_item = models.CharField(max_length=100, blank=True)  # 종목

    business_status = models.CharField(
        max_length=20,
        default="UNKNOWN",
    )
    tax_type = models.CharField(
        max_length=20,
        default="UNKNOWN",
    )
    tax_type_code = models.CharField(max_length=10, blank=True)
    tax_type_changed_date = models.DateField(
        null=True,
        blank=True,
    )

    is_demo = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    tax_accountant_email = models.EmailField(
        null=True,
        blank=True,
    )

    def __str__(self):
        return f"{self.business_name} ({self.id})"


class TaxTypeHistory(models.Model):
    """사업장의 과세유형 변경 이력."""

    business = models.ForeignKey(
        Business,
        on_delete=models.CASCADE,
        related_name="tax_type_histories",
    )
    before_code = models.CharField(max_length=10, blank=True)
    after_code = models.CharField(max_length=10)
    effective_date = models.DateField(null=True, blank=True)
    source = models.CharField(max_length=20, default="CODEF")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # 최신 변경 이력부터 조회
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.business_id}: "
            f"{self.before_code} -> {self.after_code}"
        )


class CodefConnection(models.Model):
    """사업장별 CODEF 연결 및 2-way 인증 상태."""

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

    # CODEF 연결 성공 시 발급되는 Connected ID
    connected_id = models.CharField(
        max_length=255,
        blank=True,
    )

    # CODEF 2-way 추가인증 재요청에 필요한 정보
    continue_2way = models.BooleanField(default=False)
    method = models.CharField(max_length=50, blank=True)
    job_index = models.IntegerField(null=True, blank=True)
    thread_index = models.IntegerField(null=True, blank=True)
    jti = models.CharField(max_length=255, blank=True)
    two_way_timestamp = models.BigIntegerField(
        null=True,
        blank=True,
    )

    # 최근 CODEF 오류 정보
    last_error_code = models.CharField(
        max_length=50,
        blank=True,
    )
    last_error_message = models.TextField(blank=True)

    # 디버깅용 최근 CODEF 원본 응답
    last_raw_response = models.JSONField(
        null=True,
        blank=True,
    )

    # Transaction Sync 중 추가인증이 발생한 요청 정보.
    # 인증 완료 후 어떤 거래 조회를 재개해야 하는지 식별하는 데 사용한다.
    pending_source = models.CharField(
        max_length=50,
        blank=True,
    )
    pending_operation = models.CharField(
        max_length=50,
        blank=True,
    )
    pending_start_date = models.DateField(
        null=True,
        blank=True,
    )
    pending_end_date = models.DateField(
        null=True,
        blank=True,
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            # 사업장별 CARD/HOMETAX 연결은 하나씩만 유지
            models.UniqueConstraint(
                fields=[
                    "business",
                    "connection_type",
                ],
                name="uniq_business_codef_connection",
            )
        ]

    def __str__(self):
        return (
            f"{self.business_id}/"
            f"{self.connection_type}: "
            f"{self.status}"
        )