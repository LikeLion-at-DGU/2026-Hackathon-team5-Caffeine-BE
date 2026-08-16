from django.core.management.base import BaseCommand

from businesses.models import Business, CodefConnection
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
    help = "CODEF Mock부터 거래·세금·급여·리포트까지 2026-08 데모 흐름을 생성합니다."

    def add_arguments(self, parser):
        parser.add_argument("--year-month", default="2026-08")
        parser.add_argument(
            "--reset",
            action="store_true",
            help="동일한 데모 사업장을 먼저 삭제하고 다시 만듭니다.",
        )

    def handle(self, *args, **options):
        year, month = parse_year_month(options["year_month"])
        start_date, end_date = month_range(year, month)
        business_number = "1234567890"

        if options["reset"]:
            Business.objects.filter(
                business_number=business_number,
                is_demo=True,
            ).delete()

        business, _ = Business.objects.update_or_create(
            business_number=business_number,
            defaults={
                "business_name": "카페비서 데모 매장",
                "representative_name": "데모 사장님",
                "business_type": "음식점업",
                "business_item": "카페·디저트",
                "business_status": "ACTIVE",
                "tax_type": "GENERAL",
                "tax_type_code": "1",
                "is_demo": True,
                "tax_accountant_email": "tax-demo@example.com",
            },
        )
        for connection_type in ("CARD", "HOMETAX"):
            CodefConnection.objects.update_or_create(
                business=business,
                connection_type=connection_type,
                defaults={
                    "status": "CONNECTED",
                    "connected_id": f"mock-{connection_type.lower()}-{business.id}",
                },
            )

        sync_result = TransactionSyncService().sync(
            business=business,
            start_date=start_date,
            end_date=end_date,
            sources=[
                Transaction.SourceType.CARD_PURCHASE,
                Transaction.SourceType.CASH_RECEIPT_SALE,
                Transaction.SourceType.TAX_INVOICE,
                MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
            ],
        )

        personal_keywords = ("넷플릭스", "올리브영", "개인")
        purchases = Transaction.objects.filter(
            business=business,
            transaction_type=Transaction.TransactionType.PURCHASE,
            transaction_date__gte=start_date,
            transaction_date__lte=end_date,
        )
        for transaction in purchases:
            is_personal = (
                transaction.source_deduction_status
                == Transaction.SourceDeductionStatus.NON_DEDUCTIBLE
                or any(keyword in transaction.merchant_name for keyword in personal_keywords)
            )
            transaction.expense_purpose = (
                Transaction.ExpensePurpose.PERSONAL
                if is_personal
                else Transaction.ExpensePurpose.BUSINESS
            )
            transaction.expense_purpose_source = Transaction.ClassificationSource.USER
            transaction.save(
                update_fields=["expense_purpose", "expense_purpose_source", "updated_at"]
            )
            review = DeductionReviewService.get_or_create(transaction)
            DeductionReviewService.confirm(
                review=review,
                confirmed_status=(
                    DeductionReview.ConfirmedStatus.NON_DEDUCTIBLE
                    if is_personal
                    else DeductionReview.ConfirmedStatus.DEDUCTIBLE
                ),
            )

        employee_specs = [
            ("김민지", "FULL_TIME", 10320, 141),
            ("황사라", "PART_TIME", 12000, 80),
            ("박프리", "FREELANCER", 15000, 60),
        ]
        for name, employment_type, hourly_wage, work_hours in employee_specs:
            employee, _ = Employee.objects.update_or_create(
                business=business,
                name=name,
                defaults={
                    "employment_type": employment_type,
                    "hourly_wage": hourly_wage,
                    "monthly_contracted_hours": work_hours,
                },
            )
            if not Payment.objects.filter(employee=employee, year=year, month=month).exists():
                payment_service.create_payment(
                    business.id,
                    employee.id,
                    year,
                    month,
                    work_hours,
                )

        close = MonthlyClose.objects.filter(
            business=business,
            year=year,
            month=month,
        ).first()
        if close is None or close.status != MonthlyClose.Status.CLOSED:
            MonthlyCloseService.approve(business=business, year=year, month=month)
        report = generate_report(business.id, options["year_month"])

        self.stdout.write(self.style.SUCCESS("카페비서 데모 초안 데이터 생성 완료"))
        self.stdout.write(f"business_id={business.id}")
        self.stdout.write(f"year_month={options['year_month']}")
        self.stdout.write(f"transactions={Transaction.objects.filter(business=business).count()}")
        self.stdout.write(
            f"sales_summaries={MonthlySalesSummary.objects.filter(business=business).count()}"
        )
        self.stdout.write(f"employees={Employee.objects.filter(business=business).count()}")
        self.stdout.write(f"report_id={report.id}")
        self.stdout.write(f"sync_result={sync_result}")
