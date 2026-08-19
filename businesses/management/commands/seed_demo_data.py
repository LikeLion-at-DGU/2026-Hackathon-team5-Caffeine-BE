from datetime import date
from django.core.management.base import BaseCommand

from businesses.models import Business, CodefConnection
from integrations.codef.mock import MockCodefProvider
from payroll.models import Employee, Payment
from payroll.services import payment_service
from reports.services.report_service import generate_report
from tax.models import DeductionReview, MonthlyClose
from tax.services.closing_service import MonthlyCloseService
from tax.services.deduction_service import DeductionReviewService
from tax.services.periods import month_range, parse_year_month
from transactions.models import MonthlySalesSummary, Transaction
from transactions.services.sync_service import TransactionSyncService


class Command(BaseCommand):
    help = "CODEF Mock부터 앵무101 김포마산점의 3~8월 6개월치 거래·세금·급여·리포트 데모 흐름을 생성합니다."

    def add_arguments(self, parser):
        parser.add_argument("--year-month", default="2026-08")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="동일한 데모 사업장을 먼저 삭제하고 다시 만듭니다.",
        )

    def handle(self, *args, **options):
        year, month = parse_year_month(options["year_month"])
        business_number = "1234567890"

        if options["reset"]:
            Business.objects.filter(id=1).delete()
            Business.objects.filter(business_number=business_number, is_demo=True).delete()

        business, _ = Business.objects.update_or_create(
            id=1,
            defaults={
                "business_number": business_number,
                "business_name": "앵무101 김포마산점",
                "representative_name": "유지은",
                "birth_date": "1988-05-12",
                "phone_number": "010-1234-5678",
                "industry_code": "552303",
                "business_type": "음식점업",
                "business_item": "커피전문점 및 디저트",
                "business_status": "ACTIVE",
                "tax_type": "GENERAL",
                "tax_type_code": "1",
                "is_demo": True,
                "tax_accountant_email": "tax-demo@angmu101.com",
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

        sync_result = TransactionSyncService(provider=MockCodefProvider()).sync(
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

        # 개인 지출 분류 및 공제 확정 처리 (실수로 긁은 편의점/넷플릭스/올리브영/스타벅스 등)
        personal_keywords = ("넷플릭스", "올리브영", "개인", "GS25", "스타벅스", "데일리리빙")
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
            transaction.save(update_fields=["expense_purpose", "expense_purpose_source", "updated_at"])

            review = DeductionReviewService.get_or_create(transaction)
            DeductionReviewService.confirm(
                review=review,
                confirmed_status=(
                    DeductionReview.ConfirmedStatus.NON_DEDUCTIBLE
                    if is_personal
                    else DeductionReview.ConfirmedStatus.DEDUCTIBLE
                ),
            )

        # 직원 3명 등록
        employee_specs = [
            ("김민지", "FULL_TIME", 10320, 141),
            ("황사라", "PART_TIME", 12000, 80),
            ("박프리", "FREELANCER", 15000, 60),
        ]
        for name, employment_type, hourly_wage, work_hours in employee_specs:
            Employee.objects.update_or_create(
                business=business,
                name=name,
                defaults={
                    "employment_type": employment_type,
                    "hourly_wage": hourly_wage,
                    "monthly_contracted_hours": work_hours,
                },
            )

        # 3월 ~ 8월 6개월간 매월 급여 생성 및 마감 처리
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

            close = MonthlyClose.objects.filter(business=business, year=2026, month=m).first()
            if close is None or close.status != MonthlyClose.Status.CLOSED:
                MonthlyCloseService.approve(business=business, year=2026, month=m)

        report = generate_report(business.id, options["year_month"])

        self.stdout.write(self.style.SUCCESS("앵무101 김포마산점 6개월(3~8월) 데모 데이터 생성 완료"))
        self.stdout.write(f"business_id={business.id}")
        self.stdout.write(f"business_name={business.business_name}")
        self.stdout.write(f"year_month={options['year_month']}")
        self.stdout.write(f"transactions={Transaction.objects.filter(business=business).count()}")
        self.stdout.write(f"sales_summaries={MonthlySalesSummary.objects.filter(business=business).count()}")
        self.stdout.write(f"employees={Employee.objects.filter(business=business).count()}")
        self.stdout.write(f"report_id={report.id}")
        self.stdout.write(f"sync_result={sync_result['outcome']}")
