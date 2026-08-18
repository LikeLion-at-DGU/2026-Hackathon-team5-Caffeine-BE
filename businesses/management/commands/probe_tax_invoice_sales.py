"""전자세금계산서 매출 Real CODEF 호출 검증용 관리 명령.

실제 사업자 + 카카오 간편인증을 사용하여
전자세금계산서 통합 API의 매출 데이터를 조회한다.

CODEF 전자세금계산서 통합 API:
- organization: "0002"
- endpoint:
  /v1/kr/public/nt/tax-invoice/integrated-check-list
- loginType: "5" = 회원 간편인증
- loginTypeLevel: "1" = 카카오톡
- inquiryType: "01" = 전자세금계산서
- transeType: "01" = 매출
- searchType: "01" = 작성일자
- sortby: "1" = 작성일자
- orderBy: "0" = 최신순

민감정보는 .env에서 가져온다.

.env 예시:
    CODEF_PROBE_USER_NAME=...
    CODEF_PROBE_PHONE_NO=...
    CODEF_PROBE_LOGIN_IDENTITY=...
    CODEF_PROBE_IDENTITY=...
"""

import getpass
import json
import os
from dataclasses import asdict
from datetime import date, time
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from businesses.models import Business
from integrations.codef.client import (
    CodefClient,
    CodefClientError,
    build_two_way_payload,
    extract_two_way_info,
    is_two_way_required,
)
from transactions.models import Transaction
from transactions.services.normalizers.tax_invoice import normalize_tax_invoices
from transactions.services.normalizers.helpers import TransactionNormalizationError


SUCCESS_CODE = "CF-00000"

CODEF_PATH = "/v1/kr/public/nt/tax-invoice/integrated-check-list"

TWO_WAY_ARG_NAMES = (
    "job_index",
    "thread_index",
    "jti",
    "two_way_timestamp",
)


# (payload 필드명, .env 변수명, 입력 안내, getpass 사용 여부)
_SENSITIVE_FIELD_SPECS = (
    (
        "userName",
        "CODEF_PROBE_USER_NAME",
        "홈택스 사용자 이름",
        False,
    ),
    (
        "phoneNo",
        "CODEF_PROBE_PHONE_NO",
        "휴대폰 번호",
        True,
    ),
    (
        "loginIdentity",
        "CODEF_PROBE_LOGIN_IDENTITY",
        "카카오 인증자 생년월일 8자리(YYYYMMDD)",
        True,
    ),
    (
        "identity",
        "CODEF_PROBE_IDENTITY",
        "조회 대상 사업자번호",
        True,
    ),
)


def _json_default(value):
    if isinstance(value, (Decimal, date, time)):
        return str(value)

    raise TypeError(
        f"직렬화할 수 없는 값입니다: {value!r}"
    )


def _resolve_sensitive_value(
    env_var_name,
    prompt_label,
    *,
    use_getpass,
):
    """민감정보를 .env 또는 실행 중 입력으로 받는다."""

    value = os.environ.get(env_var_name, "").strip()

    if value:
        return value

    prompt = (
        f"{prompt_label} "
        "(선택, 비워두려면 Enter): "
    )

    reader = (
        getpass.getpass
        if use_getpass
        else input
    )

    try:
        return reader(prompt).strip()
    except EOFError:
        return ""


def _mask_phone(phone):
    digits = "".join(
        character
        for character in str(phone)
        if character.isdigit()
    )

    if len(digits) <= 7:
        return "*" * len(digits)

    return (
        f"{digits[:3]}"
        f"{'*' * (len(digits) - 7)}"
        f"{digits[-4:]}"
    )


def _masked_for_display(payload):
    """터미널 출력용 민감정보 마스킹."""

    masked = dict(payload)

    if masked.get("userName"):
        masked["userName"] = "***"

    if masked.get("phoneNo"):
        masked["phoneNo"] = _mask_phone(
            masked["phoneNo"]
        )

    if masked.get("loginIdentity"):
        masked["loginIdentity"] = (
            "*" * len(
                str(masked["loginIdentity"])
            )
        )

    if masked.get("identity"):
        masked["identity"] = (
            "*" * len(
                str(masked["identity"])
            )
        )

    return masked


class Command(BaseCommand):
    help = (
        "전자세금계산서 매출 Real CODEF API를 "
        "카카오 간편인증으로 검증한다."
    )

    def add_arguments(self, parser):

        parser.add_argument(
            "--business-id",
            type=int,
            required=True,
        )

        parser.add_argument(
            "--start-date",
            required=True,
            help="조회 시작일 YYYYMMDD",
        )

        parser.add_argument(
            "--end-date",
            required=True,
            help="조회 종료일 YYYYMMDD",
        )

        parser.add_argument(
            "--simple-auth",
            help=(
                '2차 요청 전용. '
                '"0"=cancel, "1"=ok'
            ),
        )

        parser.add_argument(
            "--job-index",
            type=int,
        )

        parser.add_argument(
            "--thread-index",
            type=int,
        )

        parser.add_argument(
            "--jti",
        )

        parser.add_argument(
            "--two-way-timestamp",
            type=int,
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "CODEF에 전송하지 않고 "
                "payload만 확인한다."
            ),
        )

    def handle(self, *args, **options):

        # --------------------------------------------------
        # 1. Business 확인
        # --------------------------------------------------

        try:
            business = Business.objects.get(
                pk=options["business_id"]
            )

        except Business.DoesNotExist as exc:
            raise CommandError(
                f"business_id="
                f"{options['business_id']}를 "
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

        # --------------------------------------------------
        # 2. 민감정보 가져오기
        # --------------------------------------------------

        sensitive_fields = {}

        for (
            field_name,
            env_var,
            label,
            use_getpass,
        ) in _SENSITIVE_FIELD_SPECS:

            value = _resolve_sensitive_value(
                env_var,
                label,
                use_getpass=use_getpass,
            )

            if value:
                sensitive_fields[field_name] = value

        # --------------------------------------------------
        # 3. 카카오 간편인증 필수값 검증
        # --------------------------------------------------

        required_sensitive = (
            "userName",
            "loginIdentity",
            "phoneNo",
        )

        missing = [
            field
            for field in required_sensitive
            if not sensitive_fields.get(field)
        ]

        if missing:
            raise CommandError(
                "카카오 간편인증 필수값 누락: "
                + ", ".join(missing)
            )

        login_identity = str(
            sensitive_fields["loginIdentity"]
        )

        if not (
            login_identity.isdigit()
            and len(login_identity) == 8
        ):
            raise CommandError(
                "loginIdentity는 "
                "생년월일 8자리(YYYYMMDD)여야 합니다."
            )

        # --------------------------------------------------
        # 4. 전자세금계산서 매출 1차 payload
        # --------------------------------------------------

        payload = {
            "organization": "0002",

            "loginType": "5",
            "loginTypeLevel": "1",

            **sensitive_fields,

            # 전자세금계산서
            "inquiryType": "01",

            # 작성일자 기준 조회
            "searchType": "01",

            "startDate": options["start_date"],
            "endDate": options["end_date"],

            # 작성일자 정렬
            "sortby": "1",

            # 최신순
            "orderBy": "0",

            # 매출
            "transeType": "01",

            # 일반 조회
            "type": "0",

            # 페이징
            "startPageNo": "1",
            "pageCount": "40",
        }

        # --------------------------------------------------
        # 5. 2-way 요청 여부 확인
        # --------------------------------------------------

        two_way_values = {
            name: options[name]
            for name in TWO_WAY_ARG_NAMES
        }

        provided = [
            name
            for name, value
            in two_way_values.items()
            if value not in (None, "")
        ]

        if (
            provided
            and len(provided)
            != len(TWO_WAY_ARG_NAMES)
        ):
            missing = [
                name
                for name
                in TWO_WAY_ARG_NAMES
                if name not in provided
            ]

            raise CommandError(
                "2차 요청에는 "
                "--job-index / "
                "--thread-index / "
                "--jti / "
                "--two-way-timestamp "
                "전부 필요합니다. "
                f"빠진 값: {missing}"
            )

        is_continue_request = (
            len(provided)
            == len(TWO_WAY_ARG_NAMES)
        )

        # --------------------------------------------------
        # 6. 2차 요청 payload 추가
        # --------------------------------------------------

        if is_continue_request:

            if not options["simple_auth"]:
                raise CommandError(
                    "2차 요청에는 "
                    "--simple-auth 1이 필요합니다."
                )

            two_way_info = {
                "jobIndex":
                    two_way_values["job_index"],

                "threadIndex":
                    two_way_values["thread_index"],

                "jti":
                    two_way_values["jti"],

                "twoWayTimestamp":
                    two_way_values[
                        "two_way_timestamp"
                    ],
            }

            payload = build_two_way_payload(
                payload,
                two_way_info,
                simple_auth=options[
                    "simple_auth"
                ],
            )

            self.stdout.write(
                self.style.WARNING(
                    "전자세금계산서 매출 "
                    "2차 요청을 조립했습니다."
                )
            )

        else:
            self.stdout.write(
                "전자세금계산서 매출 "
                "1차 요청을 조립했습니다."
            )

        # --------------------------------------------------
        # 7. payload 출력
        # --------------------------------------------------

        self.stdout.write(
            json.dumps(
                _masked_for_display(payload),
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

        # --------------------------------------------------
        # 8. CODEF 호출
        # --------------------------------------------------

        client = CodefClient()

        try:
            raw = client.post(
                CODEF_PATH,
                payload,
            )

        except CodefClientError as exc:
            raise CommandError(
                f"CODEF 클라이언트 오류: {exc}"
            ) from exc

        # --------------------------------------------------
        # 9. Raw 응답
        # --------------------------------------------------

        self.stdout.write("")

        self.stdout.write(
            "CODEF 응답 "
            "(실데이터가 포함될 수 있으므로 "
            "운영 로그/PR에 복사하지 말 것):"
        )

        self.stdout.write(
            json.dumps(
                raw,
                ensure_ascii=False,
                indent=2,
            )
        )

        # --------------------------------------------------
        # 10. CF-03002 추가인증
        # --------------------------------------------------

        if is_two_way_required(raw):

            info = extract_two_way_info(raw)

            self.stdout.write("")

            self.stdout.write(
                self.style.WARNING(
                    "CF-03002: "
                    "카카오 추가인증이 필요합니다."
                )
            )

            self.stdout.write(
                "카카오 인증 완료 후 "
                "아래 값으로 2차 요청하세요."
            )

            for key, value in info.items():
                self.stdout.write(
                    f"  {key} = {value!r}"
                )

            return

        # --------------------------------------------------
        # 11. 결과 코드 확인
        # --------------------------------------------------

        result = raw.get("result") or {}

        code = result.get("code")
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

        # --------------------------------------------------
        # 12. 전자세금계산서 매출 Normalizer
        # --------------------------------------------------

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "CF-00000: "
                "전자세금계산서 매출 조회 성공."
            )
        )

        try:
            normalized_items = (
                normalize_tax_invoices(
                    raw,
                    Transaction.TransactionType.SALE,
                )
            )

        except TransactionNormalizationError as exc:

            self.stdout.write(
                self.style.ERROR(
                    f"normalizer 처리 실패: {exc}"
                )
            )

            return

        # --------------------------------------------------
        # 13. Normalizer 결과 출력
        # --------------------------------------------------

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "normalizer 결과 미리보기:"
            )
        )

        if not normalized_items:
            self.stdout.write(
                "(조회 기간 내 "
                "전자세금계산서 매출 데이터 없음)"
            )
            return

        for item in normalized_items:

            self.stdout.write(
                json.dumps(
                    asdict(item),
                    ensure_ascii=False,
                    default=_json_default,
                )
            )