"""신용카드 매출자료 조회 Real CODEF 호출 검증용 관리 명령.

실제 사업자 + 공동인증서를 사용하여 신용카드 매출자료 통합 조회 API를
호출한다.

CODEF 신용카드 매출자료 조회 API:
- organization: "0006"
- endpoint:
  /v1/kr/public/nt/tax-payment/credit-card-sales-data-list
- 인증: 공동인증서 (certFile / certPassword / certType [/ keyFile])
  카카오 간편인증(loginType)이 아니므로 추가인증(CF-03002 2-way) 흐름이
  없다. 1차 요청만으로 완결된다.
- year: YYYY
- startDate / endDate: 조회 분기 "1"~"4" (분기 범위 조회 가능)

실제 CODEF 호출은 integrations.codef.real.RealCodefProvider를 그대로
사용한다. (다른 세 probe와 달리 payload를 여기서 다시 조립하지 않는다 —
인증서 파일 경로 처리 로직이 real.py와 어긋나면 probe만 통과하고 실제
Provider는 실패하는 문제가 생기기 때문에, 이 상품은 Provider를 직접
호출해 항상 같은 코드로 검증한다.)

certFile / keyFile은 CODEF_PROBE_CERT_FILE / CODEF_PROBE_KEY_FILE 경로의
로컬 인증서 파일을 읽어 Base64로 인코딩한다. certPassword는 .env가 없으면
실행 중 대화형으로도 입력받을 수 있다.

.env 예시:
    CODEF_PROBE_CERT_TYPE=1
    CODEF_PROBE_CERT_FILE=/path/to/signCert.der
    CODEF_PROBE_KEY_FILE=/path/to/signPri.key
    CODEF_PROBE_CERT_PASSWORD=

    # 아래는 전부 선택 입력 (필요한 경우에만)
    CODEF_PROBE_DEPT_USER_ID=
    CODEF_PROBE_DEPT_USER_PASS=
    CODEF_PROBE_CARD_SALES_LOGIN_IDENTITY=
    CODEF_PROBE_MANAGE_NO=
    CODEF_PROBE_MANAGE_PASS=

주의:
- 인증서 파일과 비밀번호를 Git에 커밋하지 않는다.
"""

import getpass
import json
import os
from dataclasses import asdict
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from businesses.models import Business
from integrations.codef.base import CodefBusinessAccessError
from integrations.codef.client import CodefClient, CodefClientError
from integrations.codef.real import RealCodefProvider
from transactions.services.normalizers.credit_card_sales_summary import (
    normalize_credit_card_sales_summaries,
)
from transactions.services.normalizers.helpers import (
    TransactionNormalizationError,
)


SUCCESS_CODE = "CF-00000"


def _json_default(value):
    if isinstance(value, Decimal):
        return str(value)

    raise TypeError(
        f"직렬화할 수 없는 값입니다: {value!r}"
    )


def _ensure_cert_password_in_env():
    """certPassword가 .env에 없으면 대화형으로 받아 환경변수에 채운다.

    certFile / keyFile과 달리 비밀번호는 짧은 값이라 대화형 입력이
    실용적이다. RealCodefProvider가 os.environ에서 읽으므로, 여기서
    입력받은 값을 그대로 환경변수에 반영해 둔다.
    """

    if os.environ.get("CODEF_PROBE_CERT_PASSWORD", "").strip():
        return

    try:
        value = getpass.getpass(
            "공동인증서 비밀번호 (CODEF_PROBE_CERT_PASSWORD 미설정): "
        ).strip()
    except EOFError:
        value = ""

    if value:
        os.environ["CODEF_PROBE_CERT_PASSWORD"] = value


def _masked_for_display(payload):
    """터미널 출력용 민감정보 마스킹."""

    masked = dict(payload)

    if masked.get("certFile"):
        masked["certFile"] = "***BASE64_CERT***"

    if masked.get("keyFile"):
        masked["keyFile"] = "***BASE64_KEY***"

    if masked.get("certPassword"):
        masked["certPassword"] = "***RSA_ENCRYPTED***"

    if masked.get("deptUserPass"):
        masked["deptUserPass"] = "***"

    if masked.get("managePass"):
        masked["managePass"] = "***"

    if masked.get("loginIdentity"):
        masked["loginIdentity"] = (
            "*" * len(str(masked["loginIdentity"]))
        )

    return masked


class Command(BaseCommand):
    help = (
        "신용카드 매출자료 조회 Real CODEF API를 "
        "공동인증서로 검증한다."
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
            help="조회시작 분기",
        )

        parser.add_argument(
            "--end-quarter",
            required=True,
            choices=("1", "2", "3", "4"),
            help="조회종료 분기",
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
        #    이 API는 payload에 사업자번호(identity)가 없으므로
        #    business_number는 조회 조건에 쓰이지 않는다.
        #    여기서는 어느 사업장 기준 테스트인지 기록/확인 용도로만 쓴다.
        # --------------------------------------------------

        try:
            business = Business.objects.get(pk=options["business_id"])
        except Business.DoesNotExist as exc:
            raise CommandError(
                f"business_id={options['business_id']}를 찾을 수 없습니다."
            ) from exc

        self.stdout.write(f"business_id={business.id}")

        if business.business_number:
            self.stdout.write(
                "business_number=********** "
                "(DB 등록 확인, payload에는 사용되지 않음)"
            )

        # --------------------------------------------------
        # 2. 조회 연도/분기 검증 (RealCodefProvider와 별개로
        #    CLI 인자 자체도 여기서 먼저 걸러 에러 메시지를 더 명확히 한다)
        # --------------------------------------------------

        year = options["year"].strip()

        if not (year.isdigit() and len(year) == 4):
            raise CommandError("--year는 YYYY 4자리여야 합니다.")

        start_quarter = options["start_quarter"]
        end_quarter = options["end_quarter"]

        if int(start_quarter) > int(end_quarter):
            raise CommandError(
                "--start-quarter가 --end-quarter보다 늦을 수 없습니다."
            )

        # --------------------------------------------------
        # 3. certPassword만 대화형 입력 허용
        #    certFile / keyFile은 파일 경로이므로 .env 필수.
        # --------------------------------------------------

        _ensure_cert_password_in_env()

        # --------------------------------------------------
        # 4. payload 미리보기
        #    RealCodefProvider와 동일한 payload를 실제로 조립해 본 뒤
        #    마스킹해서 보여준다. (내부 헬퍼를 그대로 사용하므로
        #    여기서 보여주는 payload와 실제 전송 payload가 항상 같다.)
        # --------------------------------------------------

        provider = RealCodefProvider(client=CodefClient())

        # 진단 명령과 실제 요청의 인증서 처리 규칙이 달라지지 않도록 제공자의
        # 필드 생성 로직을 재사용한다. 연도와 분기는 CODEF 원본 형식을 유지한다.
        try:
            certificate_fields = (
                provider._get_credit_card_sales_certificate_fields()
            )
        except CodefBusinessAccessError as exc:
            raise CommandError(str(exc)) from exc

        payload = {
            "organization": provider.CREDIT_CARD_SALES_ORGANIZATION,
            **certificate_fields,
            "year": year,
            "startDate": start_quarter,
            "endDate": end_quarter,
        }

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
                "--dry-run이므로 CODEF로 전송하지 않았습니다."
            )
            return

        # --------------------------------------------------
        # 5. CODEF 호출
        #    이 상품은 공동인증서 기반이라 CF-03002 추가인증(2-way)
        #    분기가 없다 — 1차 요청이 곧 최종 요청이다.
        # --------------------------------------------------

        try:
            raw = provider.client.post(
                provider.CREDIT_CARD_SALES_PATH,
                payload,
            )
        except CodefClientError as exc:
            raise CommandError(f"CODEF 클라이언트 오류: {exc}") from exc

        # --------------------------------------------------
        # 6. Raw 응답
        # --------------------------------------------------

        self.stdout.write("")
        self.stdout.write(
            "CODEF 응답 "
            "(실데이터가 포함될 수 있으므로 "
            "운영 로그/PR에 복사하지 말 것):"
        )
        self.stdout.write(
            json.dumps(raw, ensure_ascii=False, indent=2)
        )

        # --------------------------------------------------
        # 7. 결과 코드 확인
        # --------------------------------------------------

        result = raw.get("result") or {}
        code = result.get("code")
        message = result.get("message", "")

        if code != SUCCESS_CODE:
            self.stdout.write("")
            self.stdout.write(
                self.style.ERROR(
                    f"실패 또는 예상치 못한 코드: {code!r} {message!r}"
                )
            )
            return

        # --------------------------------------------------
        # 8. 신용카드 매출자료 Normalizer
        # --------------------------------------------------

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "CF-00000: 신용카드 매출자료 조회 성공."
            )
        )

        try:
            normalized_items = normalize_credit_card_sales_summaries(raw)
        except TransactionNormalizationError as exc:
            self.stdout.write(
                self.style.ERROR(f"normalizer 처리 실패: {exc}")
            )
            return

        # --------------------------------------------------
        # 9. Normalizer 결과 출력
        # --------------------------------------------------

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS("normalizer 결과 미리보기:")
        )

        if not normalized_items:
            self.stdout.write(
                "(조회 기간 내 신용카드 매출자료 없음)"
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
