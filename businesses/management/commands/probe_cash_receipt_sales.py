"""현금영수증 매출내역 Real CODEF 호출을 Django shell 대신 검증하는 실험용 명령.

정식 /codef-auth/, BusinessViewSet, Serializer는 건드리지 않는다 — "Django shell에서
CODEF를 직접 호출해 성공부터 확인하고, 그 다음에 정식 API로 옮기자"는 방침 그대로,
그 shell 호출을 반복 실행 가능한 명령으로 옮겨놓은 것뿐이다.

organization/path는 상품 페이지에서 확인한 값을 사용한다. 현재 현금영수증 매출내역
상품 페이지에서 organization="0003"을 확인했으며, path는 해당 상품의 실제 Endpoint
경로를 --path로 넘긴다.

사용자 이름·휴대폰 번호·identity(사용자 주민번호/사업자번호)는 CLI 플래그로 받지 않는다 — 셸
history와 `ps aux` 같은 프로세스 목록에 그대로 남기 때문이다. 대신:
  1) .env에 CODEF_PROBE_USER_NAME / CODEF_PROBE_PHONE_NO / CODEF_PROBE_IDENTITY를
     로컬 테스트 전용으로 미리 넣어두면 그 값을 그대로 쓰고,
  2) 없으면 실행 중에 물어본다 (전화번호·식별값은 getpass로 화면에 표시하지 않음).
필요 없는 값은 그냥 Enter로 건너뛰면 된다.

사용 예시 (1차 요청 — 카카오 간편인증 시작):

    python manage.py probe_cash_receipt_sales \\
        --business-id 1 \\
        --start-date 20260801 --end-date 20260803 \\
        --organization <상품 페이지에서 확인한 값> \\
        --path <상품 페이지에서 확인한 Endpoint>

CF-03002가 나오면 사업자가 휴대폰에서 카카오 인증을 완료한 뒤, 2차 요청은
상품 명세에서 확인한 simpleAuth 값을 명시적으로 넘겨 다시 실행한다 (loginTypeLevel
의 "1"=카카오와는 다른 값이니 그대로 재사용하지 말 것):

    python manage.py probe_cash_receipt_sales \\
        --business-id 1 \\
        --start-date 20260801 --end-date 20260803 \\
        --organization <위와 동일> --path <위와 동일> \\
        --simple-auth <상품 명세에서 확인한 값> \\
        --job-index 0 --thread-index 0 --jti <jti> --two-way-timestamp <timestamp>
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
from transactions.services.normalizers.cash_receipt_sale import (
    normalize_cash_receipt_sales,
)
from transactions.services.normalizers.helpers import TransactionNormalizationError

SUCCESS_CODE = "CF-00000"

TWO_WAY_ARG_NAMES = ("job_index", "thread_index", "jti", "two_way_timestamp")

# (payload 필드명, .env 변수명, 프롬프트 문구, getpass 사용 여부).
# CLI 플래그로 노출하지 않는다 — 셸 history/프로세스 목록에 남는 걸 막기 위함.
_SENSITIVE_FIELD_SPECS = (
    ("userName", "CODEF_PROBE_USER_NAME", "홈택스 사용자 이름", False),
    ("phoneNo", "CODEF_PROBE_PHONE_NO", "휴대폰 번호", True),
    (
        "identity",
        "CODEF_PROBE_IDENTITY",
        "사용자 주민번호/사업자번호",
        True,
    ),
)


def _json_default(value):
    if isinstance(value, (Decimal, date, time)):
        return str(value)
    raise TypeError(f"직렬화할 수 없는 값입니다: {value!r}")


def _resolve_sensitive_value(env_var_name, prompt_label, *, use_getpass):
    """민감값을 .env(로컬 테스트 전용) 또는 실행 중 입력으로 받는다.

    stdin이 없는 환경(자동화된 테스트 등)에서는 EOFError를 빈 값으로 처리한다
    — 명령이 멈추거나 죽지 않게 하기 위함이며, 빈 값이면 payload에서 그냥
    빠진다(선택 입력과 동일하게 취급).
    """
    value = os.environ.get(env_var_name, "").strip()
    if value:
        return value

    prompt = f"{prompt_label} (선택, 비워두려면 Enter): "
    reader = getpass.getpass if use_getpass else input
    try:
        return reader(prompt).strip()
    except EOFError:
        return ""


def _mask_phone(phone):
    digits = "".join(character for character in str(phone) if character.isdigit())
    if len(digits) <= 7:
        return "*" * len(digits)
    return f"{digits[:3]}{'*' * (len(digits) - 7)}{digits[-4:]}"


def _masked_for_display(payload):
    """출력 전용으로 민감 필드를 마스킹한 사본을 만든다.

    실제로 CODEF에 보내는 payload는 이 함수를 거치지 않은 원본이다 — 여기서는
    화면/터미널에 찍히는 내용만 가린다.
    """
    masked = dict(payload)
    if masked.get("userName"):
        masked["userName"] = "***"
    if masked.get("phoneNo"):
        masked["phoneNo"] = _mask_phone(masked["phoneNo"])
    if masked.get("identity"):
        masked["identity"] = "*" * len(str(masked["identity"]))
    return masked


class Command(BaseCommand):
    help = (
        "현금영수증 매출내역 Real CODEF 상품을 카카오 간편인증 1차/2차 요청으로 "
        "직접 검증한다. 정식 API가 아니라 실험/검증 전용 명령이다."
    )

    def add_arguments(self, parser):
        parser.add_argument("--business-id", type=int, required=True)
        parser.add_argument("--start-date", required=True, help="YYYYMMDD")
        parser.add_argument("--end-date", required=True, help="YYYYMMDD")

        # 추측 금지 — CODEF 개발자센터 상품 페이지에서 직접 확인한 값만 넣는다.
        parser.add_argument(
            "--organization",
            required=True,
            help="현금영수증 매출내역 상품의 organization 값 (현재 확인값: 0003)",
        )
        parser.add_argument(
            "--path",
            required=True,
            help="상품 페이지의 요청 Endpoint 경로 (예: /v1/kr/public/nt/...)",
        )

        # 카카오 간편인증 코드값 — 현금영수증 '매입내역' 문서 예시 기준 기본값.
        # '매출내역'도 동일한지는 상품 페이지에서 별도 확인이 필요하다.
        parser.add_argument("--login-type", default="5")
        parser.add_argument("--login-type-level", default="1")

        # 2차(추가인증 완료 후) 요청 전용 값. loginTypeLevel(카카오 선택)과는
        # 별개의 파라미터라 기본값을 두지 않는다 — 상품 명세에서 확인해 넘긴다.
        parser.add_argument(
            "--simple-auth",
            help="2차 요청 전용. 상품 명세에서 확인한 값 (loginTypeLevel과 혼동 금지)",
        )

        parser.add_argument(
            "--extra",
            action="append",
            default=[],
            help=(
                "상품 문서에 있는 추가 필수 필드. key=value 형식, 여러 번 지정 가능. "
                "이름·전화번호·identity 등 민감값은 여기 넣지 말 것 — 실행 중 따로 물어본다."
            ),
        )

        # 넷 다 채워지면 2차(추가인증 완료 후) 요청으로 처리한다.
        parser.add_argument("--job-index", type=int)
        parser.add_argument("--thread-index", type=int)
        parser.add_argument("--jti")
        parser.add_argument("--two-way-timestamp", type=int)

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="CODEF로 실제 전송하지 않고 조립된 payload(민감값은 마스킹)만 출력한다.",
        )

    def handle(self, *args, **options):
        try:
            business = Business.objects.get(pk=options["business_id"])
        except Business.DoesNotExist as exc:
            raise CommandError(
                f"business_id={options['business_id']}를 찾을 수 없습니다."
            ) from exc

        if business.business_number:
            self.stdout.write(
                f"business_number={business.business_number} "
                "(현금영수증 매출내역의 identity와 별도 값일 수 있으므로 상품 명세에 맞춰 입력하세요)"
            )

        extra_fields = {}
        for item in options["extra"]:
            if "=" not in item:
                raise CommandError(f"--extra는 key=value 형식이어야 합니다: {item!r}")
            key, value = item.split("=", 1)
            extra_fields[key] = value

        sensitive_fields = {}
        for field_name, env_var, label, use_getpass in _SENSITIVE_FIELD_SPECS:
            value = _resolve_sensitive_value(env_var, label, use_getpass=use_getpass)
            if value:
                sensitive_fields[field_name] = value

        payload = {
            "organization": options["organization"],
            "loginType": options["login_type"],
            "loginTypeLevel": options["login_type_level"],
            "startDate": options["start_date"],
            "endDate": options["end_date"],
            **sensitive_fields,
            **extra_fields,
        }

        two_way_values = {name: options[name] for name in TWO_WAY_ARG_NAMES}
        provided = [name for name, value in two_way_values.items() if value not in (None, "")]

        if provided and len(provided) != len(TWO_WAY_ARG_NAMES):
            missing = [name for name in TWO_WAY_ARG_NAMES if name not in provided]
            raise CommandError(
                "2차 요청은 --job-index/--thread-index/--jti/--two-way-timestamp를 "
                f"모두 넘겨야 합니다. 빠진 값: {missing}"
            )

        is_continue_request = len(provided) == len(TWO_WAY_ARG_NAMES)

        if is_continue_request:
            if not options["simple_auth"]:
                raise CommandError(
                    "2차 요청에는 --simple-auth가 필요합니다 (기본값 없음). "
                    "loginTypeLevel(카카오 선택 값)과 다른 파라미터이니 상품 명세에서 "
                    "확인한 simpleAuth 값을 그대로 넘기세요."
                )
            two_way_info = {
                "jobIndex": two_way_values["job_index"],
                "threadIndex": two_way_values["thread_index"],
                "jti": two_way_values["jti"],
                "twoWayTimestamp": two_way_values["two_way_timestamp"],
            }
            payload = build_two_way_payload(
                payload,
                two_way_info,
                simple_auth=options["simple_auth"],
            )
            self.stdout.write(self.style.WARNING("2차 요청(twoWayInfo 포함)을 조립했습니다."))
        else:
            self.stdout.write("1차 요청을 조립했습니다.")

        self.stdout.write(
            json.dumps(_masked_for_display(payload), ensure_ascii=False, indent=2)
        )

        if options["dry_run"]:
            self.stdout.write("")
            self.stdout.write("--dry-run이므로 CODEF로 전송하지 않았습니다.")
            return

        client = CodefClient()

        try:
            raw = client.post(options["path"], payload)
        except CodefClientError as exc:
            raise CommandError(f"CODEF 클라이언트 오류: {exc}") from exc

        self.stdout.write("")
        self.stdout.write(
            "CODEF 응답 (마스킹 없음 — 운영 로그로 그대로 옮기지 말 것):"
        )
        self.stdout.write(json.dumps(raw, ensure_ascii=False, indent=2))

        if is_two_way_required(raw):
            info = extract_two_way_info(raw)
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "CF-03002: 추가인증이 필요합니다. 사업자가 휴대폰에서 카카오 인증을 "
                    "완료한 뒤, 아래 값과 상품 명세의 simpleAuth 값으로 같은 명령을 다시 "
                    "실행하세요."
                )
            )
            for key, value in info.items():
                self.stdout.write(f"  {key} = {value!r}")
            return

        code = (raw.get("result") or {}).get("code")

        if code != SUCCESS_CODE:
            message = (raw.get("result") or {}).get("message", "")
            self.stdout.write("")
            self.stdout.write(
                self.style.ERROR(f"실패 또는 예상치 못한 코드: {code!r} {message!r}")
            )
            return

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("CF-00000: 성공. normalizer 결과 미리보기:"))

        try:
            normalized_items = normalize_cash_receipt_sales(raw)
        except TransactionNormalizationError as exc:
            self.stdout.write(self.style.ERROR(f"normalizer 처리 실패: {exc}"))
            return

        for item in normalized_items:
            self.stdout.write(
                json.dumps(asdict(item), ensure_ascii=False, default=_json_default)
            )