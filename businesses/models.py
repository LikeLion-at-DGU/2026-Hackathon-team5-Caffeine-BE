from django.conf import settings
from django.db import models


class Business(models.Model):
    """사업장 기본 정보 및 과세유형 상태."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="businesses",
        null=True,
        blank=True,
    )
    business_name = models.CharField(max_length=100)
    representative_name = models.CharField(max_length=50, blank=True)
    birth_date = models.CharField(max_length=20, default="1988-05-12", blank=True)  # 생년월일 (YYYY-MM-DD 또는 6자리)
    phone_number = models.CharField(max_length=30, default="010-1234-5678", blank=True)  # 대표자 휴대폰 번호
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
        # 화면과 감사 로그에서 최근 변경을 먼저 보여준다.
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

    # 재인증 없이 외부 계정을 조회하기 위한 CODEF 연결 식별자.
    connected_id = models.CharField(
        max_length=255,
        blank=True,
    )

    # CODEF 추가인증 재요청에 필요한 일회성 상태.
    continue_2way = models.BooleanField(default=False)
    method = models.CharField(max_length=50, blank=True)
    job_index = models.IntegerField(null=True, blank=True)
    thread_index = models.IntegerField(null=True, blank=True)
    jti = models.CharField(max_length=255, blank=True)
    two_way_timestamp = models.BigIntegerField(
        null=True,
        blank=True,
    )

    # 사용자 안내와 재시도 판단에 사용하는 최근 오류.
    last_error_code = models.CharField(
        max_length=50,
        blank=True,
    )
    last_error_message = models.TextField(blank=True)

    # 장애 분석을 위해 보관하는 최근 CODEF 응답.
    last_raw_response = models.JSONField(
        null=True,
        blank=True,
    )

    # 추가인증이 끝난 뒤 중단된 거래 동기화를 이어가기 위한 요청 정보.
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
            # 같은 사업장과 연결 유형의 상태가 중복되지 않도록 제한한다.
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
