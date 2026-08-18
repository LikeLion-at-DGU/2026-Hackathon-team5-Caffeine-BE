"""신용카드 매출자료 Real CODEF 호출 검증용 관리 명령.

CODEF 상품:
신용카드 매출자료 조회 API

- organization: "0006"
- endpoint:
  /v1/kr/public/nt/tax-payment/credit-card-sales-data-list

인증:
- 공동인증서 필수
- 카카오 간편인증 / 2-way 방식 아님

조회:
- year: YYYY
- startDate: 시작 분기 ("1" ~ "4")
- endDate: 종료 분기 ("1" ~ "4")

예:
2026년 2분기 조회
    --year 2026
    --start-quarter 2
    --end-quarter 2

민감정보와 인증서 경로는 로컬 .env로 관리한다.

.env 예시:

    CODEF_PROBE_CERT_TYPE=1
    CODEF_PROBE_CERT_FILE=C:/private/signCert.der
    CODEF_PROBE_KEY_FILE=C:/private/signPri.key
    CODEF_PROBE_CERT_PASSWORD=인증서비밀번호

주의:
- 인증서 파일과 비밀번호를 Git에 커밋하지 않는다.
- certPassword는 CODEF Public Key로 RSA 암호화해서 전송한다.
"""

import base64
import json
import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from businesses.models import Business
from integrations.codef.client import (
    CodefClient,
    CodefClientError,
    encrypt_with_public_key,
)


SUCCESS_CODE = "CF-00000"

CODEF_PATH = (
    "/v1/kr/public/nt/tax-payment/"
    "credit-card-sales-data-list"
)


def _read_base64_file(file_path, label):
    """인증서 파일을 읽어 Base64 문자열로 변환한다."""

    if not file_path:
        raise CommandError(
            f"{label} 경로가 설정되지 않았습니다."
        )

    path = Path(file_path)

    if not path.exists():
        raise CommandError(
            f"{label} 파일을 찾을 수 없습니다: {path}"
        )

    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CommandError(
            f"{label} 파일을 읽을 수 없습니다: {exc}"
        ) from exc

    return base64.b64encode(raw).decode("ascii")


def _mask_payload(payload):
    """터미널 출력용 민감값 마스킹."""

    masked = dict(payload)

    if masked.get("certFile"):
        masked["certFile"] = "***BASE64_CERT***"

    if masked.get("keyFile"):
        masked["keyFile"] = "***BASE64_KEY***"

    if masked.get("certPassword"):
        masked["certPassword"] = "***RSA_ENCRYPTED***"

    if masked.get("deptUserPass"):
        masked["deptUserPass"] = "***"

    if masked.get("loginIdentity"):
        masked["loginIdentity"] = (
            "*" * len(str(masked["loginIdentity"]))
        )

    if masked.get("managePass"):
        masked["managePass"] = "***"

    return masked


class Command(BaseCommand):
    help = (
        "CODEF 신용카드 매출자료 조회 API를 "
        "공동인증서로 직접 검증한다."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--business-id",
            type=int,
            required=True,
        )

        parser.add_argument(
            "--year",
            required=True,
            help="조회 연도 YYYY",
        )

        parser.add_argument(
            "--start-quarter",
            required=True,
            choices=("1", "2", "3", "4"),
            help="조회 시작 분기 1~4",
        )

        parser.add_argument(
            "--end-quarter",
            required=True,
            choices=("1", "2", "3", "4"),
            help="조회 종료 분기 1~4",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "CODEF로 전송하지 않고 "
                "payload 구성만 확인한다."
            ),
        )

    def handle(self, *args, **options):

        # --------------------------------------------
        # 1. 사업자 확인
        # --------------------------------------------

        try:
            business = Business.objects.get(
                pk=options["business_id"]
            )

        except Business.DoesNotExist as exc:
            raise CommandError(
                f"business_id={options['business_id']}를 "
                "찾을 수 없습니다."
            ) from exc

        self.stdout.write(
            f"business_id={business.id}"
        )

        if business.business_number:
            self.stdout.write(
                "business_number=********** "
                "(DB 등록 확인)"
            )

        # --------------------------------------------
        # 2. 조회연도 검증
        # --------------------------------------------

        year = options["year"]

        if not (
            year.isdigit()
            and len(year) == 4
        ):
            raise CommandError(
                "--year는 YYYY 형식이어야 합니다."
            )

        start_quarter = int(
            options["start_quarter"]
        )

        end_quarter = int(
            options["end_quarter"]
        )

        if start_quarter > end_quarter:
            raise CommandError(
                "시작 분기가 종료 분기보다 "
                "클 수 없습니다."
            )

        # --------------------------------------------
        # 3. 인증서 설정
        # --------------------------------------------

        cert_type = os.environ.get(
            "CODEF_PROBE_CERT_TYPE",
            "1",
        ).strip()

        cert_file_path = os.environ.get(
            "CODEF_PROBE_CERT_FILE",
            "",
        ).strip()

        key_file_path = os.environ.get(
            "CODEF_PROBE_KEY_FILE",
            "",
        ).strip()

        cert_password = os.environ.get(
            "CODEF_PROBE_CERT_PASSWORD",
            "",
        )

        if not cert_password:
            raise CommandError(
                "CODEF_PROBE_CERT_PASSWORD가 "
                ".env에 없습니다."
            )

        # --------------------------------------------
        # 4. 인증서 파일 처리
        # --------------------------------------------

        cert_file = _read_base64_file(
            cert_file_path,
            "certFile",
        )

        payload = {
            "organization": "0006",

            "certType": cert_type,

            "certFile": cert_file,

            "year": year,

            "startDate":
                options["start_quarter"],

            "endDate":
                options["end_quarter"],
        }

        # der/key 인증서
        if cert_type == "1":

            key_file = _read_base64_file(
                key_file_path,
                "keyFile",
            )

            payload["keyFile"] = key_file

        # --------------------------------------------
        # 5. 인증서 비밀번호 RSA 암호화
        # --------------------------------------------

        try:
            encrypted_password = (
                encrypt_with_public_key(
                    cert_password
                )
            )

        except CodefClientError as exc:
            raise CommandError(
                "인증서 비밀번호 RSA 암호화 실패: "
                f"{exc}"
            ) from exc

        payload[
            "certPassword"
        ] = encrypted_password

        # --------------------------------------------
        # 6. 선택 입력
        # --------------------------------------------

        optional_env_fields = {
            "deptUserId":
                "CODEF_PROBE_DEPT_USER_ID",

            "deptUserPass":
                "CODEF_PROBE_DEPT_USER_PASS",

            "loginIdentity":
                "CODEF_PROBE_CARD_LOGIN_IDENTITY",

            "manageNo":
                "CODEF_PROBE_MANAGE_NO",

            "managePass":
                "CODEF_PROBE_MANAGE_PASS",
        }

        for (
            payload_key,
            env_key,
        ) in optional_env_fields.items():

            value = os.environ.get(
                env_key,
                "",
            ).strip()

            if value:
                payload[
                    payload_key
                ] = value

        # --------------------------------------------
        # 7. Payload 확인
        # --------------------------------------------

        self.stdout.write(
            "신용카드 매출자료 요청 payload:"
        )

        self.stdout.write(
            json.dumps(
                _mask_payload(payload),
                ensure_ascii=False,
                indent=2,
            )
        )

        if options["dry_run"]:

            self.stdout.write("")

            self.stdout.write(
                "--dry-run이므로 "
                "CODEF로 전송하지 않았습니다."
            )

            return

        # --------------------------------------------
        # 8. CODEF 호출
        # --------------------------------------------

        client = CodefClient()

        try:
            raw = client.post(
                CODEF_PATH,
                payload,
            )

        except CodefClientError as exc:
            raise CommandError(
                "CODEF 클라이언트 오류: "
                f"{exc}"
            ) from exc

        # --------------------------------------------
        # 9. 결과
        # --------------------------------------------

        self.stdout.write("")

        self.stdout.write(
            "CODEF 응답 "
            "(실데이터가 포함될 수 있으므로 "
            "PR/운영 로그에 복사하지 말 것):"
        )

        self.stdout.write(
            json.dumps(
                raw,
                ensure_ascii=False,
                indent=2,
            )
        )

        result = raw.get(
            "result"
        ) or {}

        code = result.get(
            "code"
        )

        message = result.get(
            "message",
            "",
        )

        if code != SUCCESS_CODE:

            self.stdout.write("")

            self.stdout.write(
                self.style.ERROR(
                    "실패 또는 예상치 못한 코드: "
                    f"{code!r} {message!r}"
                )
            )

            return

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "CF-00000: "
                "신용카드 매출자료 조회 성공."
            )
        )