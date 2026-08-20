from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from rest_framework.authtoken.models import Token

from benchmark.models import AIDiagnosisHistory, IndustryBenchmark
from analytics.services.monthly_summary_service import get_monthly_tax_summary
from businesses.models import Business
from payroll.models import Employee, Payment
from tax.models import DeductionReview, MonthlyClose
from transactions.models import MonthlySalesSummary, Transaction


@override_settings(OPENAI_API_KEY="")
class SeedDemoDataCommandTests(TestCase):
    def _reset_demo(self):
        output = StringIO()
        call_command("seed_demo_data", "--reset", stdout=output)
        return output.getvalue()

    def test_reset_restores_exact_six_month_demo_snapshot(self):
        other_business = Business.objects.create(
            id=2,
            business_name="보존할 다른 사업장",
            business_number="9999999999",
        )
        other_history = AIDiagnosisHistory.objects.create(
            business=other_business,
            year_month="2026-08",
        )

        first_output = self._reset_demo()
        business = Business.objects.get(pk=1)

        self.assertEqual(business.business_name, "수아네 커피집")
        self.assertEqual(business.business_number, "2148678901")
        self.assertTrue(business.is_demo)
        self.assertEqual(Transaction.objects.filter(business=business).count(), 48)
        self.assertEqual(MonthlySalesSummary.objects.filter(business=business).count(), 6)
        self.assertEqual(Employee.objects.filter(business=business).count(), 3)
        self.assertEqual(
            set(Employee.objects.filter(business=business).values_list("name", flat=True)),
            {"이도현", "박서연", "최우식"},
        )
        self.assertEqual(Payment.objects.filter(employee__business=business).count(), 18)
        for demo_month in range(3, 9):
            summary = get_monthly_tax_summary(business.id, 2026, demo_month)
            self.assertGreater(summary["total_sales"], 9_000_000)
            self.assertGreater(summary["total_expense"], 3_000_000)
            self.assertGreater(summary["net_profit"], 0)
            self.assertGreater(summary["profit_margin"], 20)
        self.assertEqual(
            MonthlyClose.objects.filter(
                business=business,
                year=2026,
                status=MonthlyClose.Status.CLOSED,
            ).count(),
            5,
        )
        self.assertFalse(
            MonthlyClose.objects.filter(business=business, year=2026, month=8).exists()
        )
        self.assertEqual(
            DeductionReview.objects.filter(transaction__business=business).count(),
            Transaction.objects.filter(
                business=business,
                transaction_type=Transaction.TransactionType.PURCHASE,
            ).count(),
        )
        self.assertEqual(
            IndustryBenchmark.objects.filter(
                region="성수동 상권",
                business_type="커피-음료",
                year_month__range=("2026-03", "2026-08"),
            ).count(),
            6,
        )
        self.assertIn("transactions=48", first_output)
        self.assertIn("payments=18", first_output)

        # 시연 중 추가·수정된 급여도 두 번째 reset에서 완전히 사라져야 한다.
        Employee.objects.create(
            business=business,
            name="시연 중 추가한 직원",
            employment_type="PART_TIME",
            hourly_wage=50_000,
        )
        payment = Payment.objects.get(
            employee__business=business,
            employee__name="박서연",
            year=2026,
            month=8,
        )
        payment.gross_pay = 99_999_999
        payment.save(update_fields=["gross_pay"])

        self._reset_demo()
        business = Business.objects.get(pk=1)
        restored_payment = Payment.objects.get(
            employee__business=business,
            employee__name="박서연",
            year=2026,
            month=8,
        )

        self.assertEqual(Employee.objects.filter(business=business).count(), 3)
        self.assertEqual(Payment.objects.filter(employee__business=business).count(), 18)
        self.assertEqual(restored_payment.gross_pay, 816_000)
        self.assertTrue(AIDiagnosisHistory.objects.filter(pk=other_history.pk).exists())
        self.assertEqual(
            Token.objects.get(user__username="demo").key,
            "demo-caffeine-token-2026",
        )

    def test_reset_refuses_to_delete_non_demo_business_id_one(self):
        Business.objects.create(
            id=1,
            business_name="실제 사업장",
            business_number="1111111111",
            is_demo=False,
        )

        with self.assertRaisesMessage(CommandError, "안전을 위해 중단"):
            self._reset_demo()

        self.assertTrue(Business.objects.filter(pk=1, business_name="실제 사업장").exists())
