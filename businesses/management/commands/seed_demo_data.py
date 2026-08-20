from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from rest_framework.authtoken.models import Token

from benchmark.models import IndustryBenchmark
from businesses.models import Business, CodefConnection
from integrations.codef.mock import MockCodefProvider
from payroll.models import Employee, Payment
from payroll.services import payment_service
from reports.services.report_service import generate_report
from tax.models import DeductionReview, MonthlyClose
from tax.services.closing_service import MonthlyCloseService
from tax.services.deduction_service import DeductionReviewService
from tax.services.periods import parse_year_month
from transactions.models import MonthlySalesSummary, Transaction
from transactions.services.sync_service import TransactionSyncService


class Command(BaseCommand):
    help = "CODEF Mock부터 수아네 커피집의 3~8월 6개월치 거래·세금·급여·리포트 데모 흐름을 생성합니다."

    DEMO_TOKEN_KEY = "demo-caffeine-token-2026"
    DEMO_BUSINESS_NUMBER = "2148678901"
    DEMO_CATEGORY_KEYWORDS = (
        (Transaction.Category.RAW_MATERIAL, ("매일유업", "일리카페", "스위트시럽", "베이커리팩토리")),
        (Transaction.Category.UTILITIES, ("한국전력",)),
        (Transaction.Category.SUPPLIES, ("코스트코", "쿠팡 비즈니스", "삼원위생", "팩플러스")),
        (Transaction.Category.FEES, ("나이스정보통신",)),
    )
    BENCHMARK_SPECS = {
        3: (10_000_000, "34.00", "27.00", "13.00", "5.50", "15.00"),
        4: (10_400_000, "33.50", "26.50", "12.80", "5.20", "16.00"),
        5: (10_800_000, "33.00", "26.00", "12.60", "5.00", "16.50"),
        6: (11_200_000, "32.80", "25.50", "12.50", "4.90", "17.00"),
        7: (11_600_000, "32.50", "25.30", "12.50", "4.80", "17.20"),
        8: (12_000_000, "32.00", "25.00", "12.50", "4.80", "16.80"),
    }

    def add_arguments(self, parser):
        parser.add_argument("--year-month", default="2026-08")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="동일한 데모 사업장을 먼저 삭제하고 다시 만듭니다.",
        )

    def handle(self, *args, **options):
        parse_year_month(options["year_month"])
        business_number = self.DEMO_BUSINESS_NUMBER

        # 1. 고정 데모 유저 및 토큰 생성
        demo_user, _ = User.objects.get_or_create(
            username="demo",
            defaults={"email": "demo@suanecoffee.com", "first_name": "수아", "last_name": "조"},
        )
        demo_user.first_name = "수아"
        demo_user.last_name = "조"
        demo_user.email = "demo@suanecoffee.com"
        demo_user.set_password("demo1234")
        demo_user.save()

        # 프론트엔드가 로그인 없이도 고정 토큰으로 데모 API를 호출할 수 있도록
        # 매번 동일한 키를 보장한다. 같은 키가 다른 사용자에게 할당된 경우에는
        # 해당 사용자의 인증정보를 빼앗지 않고 명시적으로 실패한다.
        token_with_fixed_key = Token.objects.filter(
            key=self.DEMO_TOKEN_KEY,
        ).first()
        if (
            token_with_fixed_key is not None
            and token_with_fixed_key.user_id != demo_user.id
        ):
            raise CommandError(
                "고정 데모 토큰이 이미 다른 사용자에게 할당되어 있습니다."
            )

        Token.objects.filter(user=demo_user).exclude(
            key=self.DEMO_TOKEN_KEY,
        ).delete()
        token, _ = Token.objects.get_or_create(
            key=self.DEMO_TOKEN_KEY,
            defaults={"user": demo_user},
        )

        existing_id_one = Business.objects.filter(id=1).first()
        if existing_id_one and not (
            existing_id_one.is_demo
            and existing_id_one.business_number == business_number
        ):
            raise CommandError(
                "business_id=1이 수아네 커피집 데모 사업장이 아니므로 안전을 위해 중단합니다."
            )

        if options["reset"]:
            # 데모 사업장 FK 하위 데이터만 cascade로 정리한다. 다른 사업자의
            # 거래·급여·리포트·AI 진단 이력은 절대 삭제하지 않는다.
            Business.objects.filter(
                business_number=business_number,
                is_demo=True,
            ).delete()

        business, _ = Business.objects.update_or_create(
            id=1,
            defaults={
                "owner": demo_user,
                "business_number": business_number,
                "business_name": "수아네 커피집",
                "representative_name": "조수아",
                "birth_date": "2003-05-24",
                "phone_number": "010-2458-1046",
                "industry_code": "552303",
                "business_type": "음식점업",
                "business_item": "커피전문점 및 음료",
                "business_status": "ACTIVE",
                "tax_type": "GENERAL",
                "tax_type_code": "1",
                "is_demo": True,
                "tax_accountant_email": "tax@suanecoffee.com",
            },
        )

        for connection_type in ("CARD", "HOMETAX"):
            CodefConnection.objects.update_or_create(
                business=business,
                connection_type=connection_type,
                defaults={
                    "status": "CONNECTED",
                    "connected_id": f"cid-{connection_type.lower()}-{business.id}",
                },
            )

        # 3월부터 8월까지 6개월간의 전체 거래 동기화
        sync_start_date = date(2026, 3, 1)
        sync_end_date = date(2026, 8, 31)

        TransactionSyncService(provider=MockCodefProvider()).sync(
            business=business,
            start_date=sync_start_date,
            end_date=sync_end_date,
            sources=[
                Transaction.SourceType.CARD_PURCHASE,
                Transaction.SourceType.CASH_RECEIPT_SALE,
                Transaction.SourceType.TAX_INVOICE,
                MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
            ],
        )

        # 개인 지출 분류 및 공제 확정 처리 (CU 편의점/유튜브 프리미엄/무신사/블루보틀 등)
        # 분류 결과는 외부 LLM 호출에 의존하지 않는 고정 시연 스냅샷으로 만든다.
        personal_keywords = ("유튜브", "무신사", "블루보틀", "CU", "편의점", "개인")
        purchases = Transaction.objects.filter(
            business=business,
            transaction_type=Transaction.TransactionType.PURCHASE,
        )
        for transaction in purchases:
            is_personal = (
                transaction.source_deduction_status == Transaction.SourceDeductionStatus.NON_DEDUCTIBLE
                or any(keyword in transaction.merchant_name for keyword in personal_keywords)
            )
            transaction.expense_purpose = (
                Transaction.ExpensePurpose.PERSONAL if is_personal else Transaction.ExpensePurpose.BUSINESS
            )
            transaction.expense_purpose_source = Transaction.ClassificationSource.USER

            demo_category = self._demo_category(transaction.merchant_name)
            if demo_category and not is_personal:
                transaction.category = demo_category
                transaction.classification_source = Transaction.ClassificationSource.AI
                transaction.classification_confidence = Decimal("0.9500")

            transaction.save(update_fields=[
                "expense_purpose",
                "expense_purpose_source",
                "category",
                "classification_source",
                "classification_confidence",
                "updated_at",
            ])

            review = DeductionReviewService.get_or_create(transaction)
            DeductionReviewService.confirm(
                review=review,
                confirmed_status=(
                    DeductionReview.ConfirmedStatus.NON_DEDUCTIBLE
                    if is_personal
                    else DeductionReview.ConfirmedStatus.DEDUCTIBLE
                ),
            )

        # 직원 3명 등록 (이도현, 박서연, 최우식)
        employee_specs = [
            ("이도현", "FULL_TIME", 11500, 160, False),
            # 3월~8월 계속 근무하는 데모 단시간 근로자로 고용보험 적용 대상이다.
            ("박서연", "PART_TIME", 10200, 80, True),
            ("최우식", "FREELANCER", 15000, 40, False),
        ]
        for name, employment_type, hourly_wage, work_hours, is_long_term_contract in employee_specs:
            Employee.objects.update_or_create(
                business=business,
                name=name,
                defaults={
                    "employment_type": employment_type,
                    "hourly_wage": hourly_wage,
                    "monthly_contracted_hours": work_hours,
                    "is_long_term_contract": is_long_term_contract,
                },
            )

        # 3월 ~ 8월 6개월간 매월 급여 생성
        for m in range(3, 9):
            for emp in Employee.objects.filter(business=business):
                if not Payment.objects.filter(employee=emp, year=2026, month=m).exists():
                    payment_service.create_payment(
                        business.id,
                        emp.id,
                        2026,
                        m,
                        emp.monthly_contracted_hours,
                    )

        # 3월~8월 성수동 커피·음료 상권 비교 데이터도 같은 값으로 복원한다.
        for benchmark_month, spec in self.BENCHMARK_SPECS.items():
            revenue, raw, labor, rent, supplies, profit = spec
            IndustryBenchmark.objects.update_or_create(
                region="성수동 상권",
                business_type="커피-음료",
                year_month=f"2026-{benchmark_month:02d}",
                defaults={
                    "raw_material_ratio": Decimal(raw),
                    "labor_ratio": Decimal(labor),
                    "rent_ratio": Decimal(rent),
                    "supplies_ratio": Decimal(supplies),
                    "operating_profit_ratio": Decimal(profit),
                    "benchmark_monthly_revenue": revenue,
                    "peak_time_ratio": Decimal("31.60"),
                    "weekday_ratio": Decimal("62.30"),
                    "weekend_ratio": Decimal("37.70"),
                    "source": "SEOUL_OPEN_API_DEMO_SNAPSHOT",
                },
            )

        # 3월 ~ 7월 과거 월은 마감(CLOSED) 처리
        for m in range(3, 8):
            close = MonthlyClose.objects.filter(business=business, year=2026, month=m).first()
            if close is None or close.status != MonthlyClose.Status.CLOSED:
                MonthlyCloseService.approve(business=business, year=2026, month=m)

        # 마감된 가장 최근 월(7월) 정기 리포트 생성
        try:
            generate_report(business.id, "2026-07")
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS("수아네 커피집 6개월(3~8월) 신규 데모 데이터 생성 완료"))
        self.stdout.write(f"demo_user=demo / demo1234")
        self.stdout.write(f"demo_token={token.key}")
        self.stdout.write(f"business_id={business.id}")
        self.stdout.write(f"business_name={business.business_name}")
        self.stdout.write(f"representative_name={business.representative_name}")
        self.stdout.write(f"birth_date={business.birth_date}")
        self.stdout.write(f"phone_number={business.phone_number}")
        self.stdout.write(f"year_month={options['year_month']}")
        self.stdout.write(f"transactions={Transaction.objects.filter(business=business).count()}")
        self.stdout.write(f"sales_summaries={MonthlySalesSummary.objects.filter(business=business).count()}")
        self.stdout.write(f"employees={Employee.objects.filter(business=business).count()}")
        self.stdout.write(f"payments={Payment.objects.filter(employee__business=business).count()}")
        self.stdout.write(f"monthly_closes={MonthlyClose.objects.filter(business=business).count()}")
        self.stdout.write("demo_period=2026-03~2026-08 / 2026-08 OPEN")

    @classmethod
    def _demo_category(cls, merchant_name):
        for category, keywords in cls.DEMO_CATEGORY_KEYWORDS:
            if any(keyword in (merchant_name or "") for keyword in keywords):
                return category
        return None
