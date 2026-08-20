from decimal import Decimal
from django.test import TestCase

from businesses.models import Business
from transactions.models import Transaction, MonthlySalesSummary
from payroll.models import Employee, Payment
from benchmark.models import IndustryBenchmark
from benchmark.services.calculator import BenchmarkCalculator


class BenchmarkCalculatorTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            business_name="카페비서 1호점",
            business_number="1234567890",
        )
        self.benchmark = IndustryBenchmark.objects.create(
            region="성수동 상권",
            business_type="커피-음료",
            year_month="2026-08",
            raw_material_ratio=Decimal("32.00"),
            labor_ratio=Decimal("25.00"),
            rent_ratio=Decimal("12.50"),
            supplies_ratio=Decimal("4.80"),
            operating_profit_ratio=Decimal("16.80"),
            benchmark_monthly_revenue=10400000,
        )

    def test_calculate_with_real_transactions_and_payroll(self):
        # 1. 매출 생성 (12,000,000원)
        MonthlySalesSummary.objects.create(
            business=self.business,
            year=2026,
            month=8,
            source_type=MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
            total_amount=Decimal("12000000"),
            transaction_count=120,
        )

        # 2. 식자재 매입 (4,380,000원 = 36.5%)
        Transaction.objects.create(
            business=self.business,
            external_id="TX-TEST-001",
            transaction_date="2026-08-10",
            transaction_type=Transaction.TransactionType.PURCHASE,
            source_type=Transaction.SourceType.CARD_PURCHASE,
            category=Transaction.Category.RAW_MATERIAL,
            expense_purpose=Transaction.ExpensePurpose.BUSINESS,
            total_amount=Decimal("4380000"),
            supply_amount=Decimal("3981818"),
            vat_amount=Decimal("398182"),
        )

        # 3. 직원 급여 (2,796,000원 = 23.3%)
        emp = Employee.objects.create(
            business=self.business,
            name="알바생",
            employment_type="PART_TIME",
            hourly_wage=10000,
        )
        Payment.objects.create(
            employee=emp,
            year=2026,
            month=8,
            work_hours=Decimal("279.6"),
            gross_pay=2796000,
            withholding_tax=0,
        )

        result = BenchmarkCalculator.calculate(self.business, year=2026, month=8)

        self.assertEqual(result.business_id, self.business.id)
        self.assertEqual(result.total_revenue, 12000000)
        self.assertEqual(result.raw_material_ratio, 36.5)
        self.assertEqual(result.benchmark_raw_material_ratio, 32.0)
        self.assertEqual(result.raw_material_diff_pct, 4.5)
        self.assertEqual(len(result.category_comparison), 4)
        self.assertEqual(len(result.monthly_trends), 6)

    def test_empty_month_does_not_invent_demo_revenue_or_expenses(self):
        result = BenchmarkCalculator.calculate(self.business, year=2026, month=7)

        self.assertEqual(result.total_revenue, 0)
        self.assertEqual(result.total_expense, 0)
        self.assertEqual(result.raw_material_ratio, 0.0)

    def test_revenue_sources_are_combined_and_personal_expense_is_excluded(self):
        MonthlySalesSummary.objects.create(
            business=self.business,
            year=2026,
            month=8,
            source_type=MonthlySalesSummary.SourceType.CREDIT_CARD_SALES_SUMMARY,
            total_amount=Decimal("9000000"),
            transaction_count=90,
        )
        Transaction.objects.create(
            business=self.business,
            external_id="SALE-CASH-1",
            transaction_date="2026-08-03",
            transaction_type=Transaction.TransactionType.SALE,
            source_type=Transaction.SourceType.CASH_RECEIPT_SALE,
            total_amount=Decimal("500000"),
        )
        Transaction.objects.create(
            business=self.business,
            external_id="PERSONAL-1",
            transaction_date="2026-08-04",
            transaction_type=Transaction.TransactionType.PURCHASE,
            source_type=Transaction.SourceType.CARD_PURCHASE,
            expense_purpose=Transaction.ExpensePurpose.PERSONAL,
            category=Transaction.Category.RAW_MATERIAL,
            total_amount=Decimal("1000000"),
        )

        result = BenchmarkCalculator.calculate(self.business, year=2026, month=8)

        self.assertEqual(result.total_revenue, 9_500_000)
        self.assertEqual(result.total_expense, 0)
        self.assertEqual(result.raw_material_ratio, 0.0)
