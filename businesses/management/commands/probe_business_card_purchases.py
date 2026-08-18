"""사업용 신용카드 매입 Real CODEF 호출 검증용 관리 명령.

CODEF 상품:
현금영수증 사업용 신용카드 매입세액 공제 확인/변경 조회 API

- organization: "0003"
- endpoint:
  /v1/kr/public/nt/cash-receipt/
  deduction-of-business-credit-card-purchase-amount

카카오 간편인증:
- loginType: "5"
- loginTypeLevel: "1"
- userName 필수
- loginIdentity 필수 (생년월일 8자리 YYYYMMDD)
- phoneNo 필수

조회 기간:
- searchType="0": 일별, startDate=YYYYMMDD
- searchType="1": 월별, startDate=YYYYMM
- searchType="2": 분기별, startDate=YYYY + 분기번호

예:
2026년 6월
    --search-type 1
    --start-date 202606

민감정보는 로컬 .env에서 가져온다.

.env:
    CODEF_PROBE_USER_NAME=...
    CODEF_PROBE_PHONE_NO=...
    CODEF_PROBE_LOGIN_IDENTITY=...
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
from transactions.services.normalizers.business_card_purchase import (
    normalize_business_card_purchases,
)
from transactions.services.normalizers.helpers import (
    TransactionNormalizationError,
)


SUCCESS_CODE = "CF-00000"

CODEF_PATH = (
    "/v1/kr/public/nt/cash-receipt/"
    "deduction-of-business-credit-card-purchase-amount"
)

TWO_WAY_ARG_NAMES = (
    "job_index",
    "thread_index",
    "jti",
    "two_way_timestamp",
)


# payload field / env / prompt / getpass 여부
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
    value = os.environ.get(
        env_var_name,
        "",
    ).strip()

    if value:
        return value

    prompt = (
        f"{prompt_label} "
        "(비워두려면 Enter): "
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
        char
        for char in str(phone)
        if char.isdigit()
    )

    if len(digits) <= 7:
        return "*" * len(digits)

    return (
        f"{digits[:3]}"
        f"{'*' * (len(digits) - 7)}"
        f"{digits[-4:]}"
    )


def _masked_for_display(payload):
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

    return masked


def _validate_start_date(
    search_type,
    start_date,
):
    """searchType에 맞는 startDate 형식을 검사한다."""

    if not start_date.isdigit():
        raise CommandError(
            "startDate는 숫자만 입력해야 합니다."
        )

    if search_type == "0":
        if len(start_date) != 8:
            raise CommandError(
                "searchType='0'(일별)은 "
                "--start-date YYYYMMDD 형식입니다."
            )

    elif search_type == "1":
        if len(start_date) != 6:
            raise CommandError(
                "searchType='1'(월별)은 "
                "--start-date YYYYMM 형식입니다."
            )

    elif search_type == "2":
        if (
            len(start_date) != 5
            or start_date[-1] not in "1234"
        ):
            raise CommandError(
                "searchType='2'(분기별)은 "
                "--start-date YYYY분기번호 형식입니다. "
                "예: 2026년 2분기 → 20262"
            )

    else:
        raise CommandError(
            "--search-type은 "
            "0(일별), 1(월별), 2(분기별) 중 하나여야 합니다."
        )


class Command(BaseCommand):
    help = (
        "CODEF 사업용 신용카드 매입세액 "
        "조회 API를 카카오 간편인증으로 검증한다."
    )

    def add_arguments(
        self,
        parser,
    ):
        parser.add_argument(
            "--business-id",
            type=int,
            required=True,
        )

        parser.add_argument(
            "--search-type",
            default="1",
            choices=("0", "1", "2"),
            help=(
                "조회 기간 구분: "
                "0=일별, 1=월별, 2=분기별 "
                "(기본값: 1)"
            ),
        )

        parser.add_argument(
            "--start-date",
            required=True,
            help=(
                "searchType에 따라 "
                "YYYYMMDD / YYYYMM / YYYY분기번호"
            ),
        )

        parser.add_argument(
            "--inquiry-type",
            default="0",
            choices=("0", "1", "2"),
            help=(
                "공제여부: "
                "0=전체, 1=공제대상, "
                "2=불공제대상 (기본값: 0)"
            ),
        )

        parser.add_argument(
            "--detail-yn",
            default="1",
            choices=("0", "1"),
            help=(
                "카드정보 포함 여부: "
                "0=미포함, 1=포함 "
                "(기본값: 1)"
            ),
        )

        parser.add_argument(
            "--simple-auth",
            help=(
                '2차 요청 전용: '
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
                "CODEF로 전송하지 않고 "
                "payload만 확인한다."
            ),
        )

    def handle(
        self,
        *args,
        **options,
    ):
        # --------------------------------------------
        # 1. Business 확인
        # --------------------------------------------

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

        # --------------------------------------------
        # 2. 조회 기간 검증
        # --------------------------------------------

        _validate_start_date(
            options["search_type"],
            options["start_date"],
        )

        # --------------------------------------------
        # 3. 민감정보
        # --------------------------------------------

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
                sensitive_fields[
                    field_name
                ] = value

        # --------------------------------------------
        # 4. 카카오 간편인증 필수값
        # --------------------------------------------

        required_fields = (
            "userName",
            "phoneNo",
            "loginIdentity",
        )

        missing = [
            field
            for field in required_fields
            if not sensitive_fields.get(field)
        ]

        if missing:
            raise CommandError(
                "카카오 간편인증 필수값 누락: "
                + ", ".join(missing)
            )

        login_identity = str(
            sensitive_fields[
                "loginIdentity"
            ]
        )

        if not (
            login_identity.isdigit()
            and len(login_identity) == 8
        ):
            raise CommandError(
                "loginIdentity는 "
                "생년월일 8자리(YYYYMMDD)여야 합니다."
            )

        # --------------------------------------------
        # 5. 1차 Payload
        # --------------------------------------------

        payload = {
            "organization": "0003",

            # 회원 간편인증
            "loginType": "5",

            # 카카오톡
            "loginTypeLevel": "1",

            **sensitive_fields,

            # 0 일 / 1 월 / 2 분기
            "searchType":
                options["search_type"],

            "startDate":
                options["start_date"],

            # 0 전체 / 1 공제 / 2 불공제
            "inquiryType":
                options["inquiry_type"],

            # 카드 정보 포함
            "detailYN":
                options["detail_yn"],
        }

        # --------------------------------------------
        # 6. 2-way 요청 여부
        # --------------------------------------------

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
            missing_two_way = [
                name
                for name
                in TWO_WAY_ARG_NAMES
                if two_way_values[name]
                in (None, "")
            ]

            raise CommandError(
                "2차 요청에는 "
                "--job-index / "
                "--thread-index / "
                "--jti / "
                "--two-way-timestamp가 "
                "모두 필요합니다. "
                f"빠진 값: {missing_two_way}"
            )

        is_continue_request = (
            len(provided)
            == len(TWO_WAY_ARG_NAMES)
        )

        # --------------------------------------------
        # 7. 2차 요청 Payload
        # --------------------------------------------

        if is_continue_request:

            if not options["simple_auth"]:
                raise CommandError(
                    "2차 요청에는 "
                    "--simple-auth 1이 필요합니다."
                )

            two_way_info = {
                "jobIndex":
                    two_way_values[
                        "job_index"
                    ],

                "threadIndex":
                    two_way_values[
                        "thread_index"
                    ],

                "jti":
                    two_way_values[
                        "jti"
                    ],

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
                    "사업용 신용카드 매입 "
                    "2차 요청을 조립했습니다."
                )
            )

        else:
            self.stdout.write(
                "사업용 신용카드 매입 "
                "1차 요청을 조립했습니다."
            )

        # --------------------------------------------
        # 8. Payload 출력
        # --------------------------------------------

        self.stdout.write(
            json.dumps(
                _masked_for_display(
                    payload
                ),
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
        # 9. CODEF 호출
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
        # 10. Raw 응답
        # --------------------------------------------

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

        # --------------------------------------------
        # 11. CF-03002 추가인증
        # --------------------------------------------

        if is_two_way_required(raw):

            info = extract_two_way_info(
                raw
            )

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

        # --------------------------------------------
        # 12. 응답 코드
        # --------------------------------------------

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

        # --------------------------------------------
        # 13. Normalizer
        # --------------------------------------------

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "CF-00000: "
                "사업용 신용카드 매입 조회 성공."
            )
        )

        try:
            normalized_items = (
                normalize_business_card_purchases(
                    raw
                )
            )

        except TransactionNormalizationError as exc:

            self.stdout.write(
                self.style.ERROR(
                    "normalizer 처리 실패: "
                    f"{exc}"
                )
            )

            return

        # --------------------------------------------
        # 14. Normalizer 결과
        # --------------------------------------------

        self.stdout.write("")

        self.stdout.write(
            self.style.SUCCESS(
                "normalizer 결과 미리보기:"
            )
        )

        if not normalized_items:

            self.stdout.write(
                "(조회 기간 내 "
                "사업용 신용카드 매입 데이터 없음)"
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