import django.db.models.deletion
from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("transactions", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="transaction",
            name="expense_purpose",
            field=models.CharField(
                choices=[
                    ("UNCLASSIFIED", "미분류"),
                    ("BUSINESS", "사업 지출"),
                    ("PERSONAL", "개인 지출"),
                ],
                default="UNCLASSIFIED",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="transaction",
            name="expense_purpose_source",
            field=models.CharField(
                choices=[
                    ("UNCLASSIFIED", "미분류"),
                    ("AI", "AI"),
                    ("USER", "사용자"),
                    ("RULE", "규칙"),
                ],
                default="UNCLASSIFIED",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="transaction",
            name="source_deduction_status",
            field=models.CharField(
                choices=[
                    ("UNKNOWN", "원본 정보 없음"),
                    ("DEDUCTIBLE", "CODEF 공제 표시"),
                    ("NON_DEDUCTIBLE", "CODEF 불공제 표시"),
                ],
                default="UNKNOWN",
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="MonthlySalesSummary",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            (
                                "CREDIT_CARD_SALES_SUMMARY",
                                "신용카드 월 매출자료",
                            )
                        ],
                        max_length=30,
                    ),
                ),
                ("year", models.PositiveSmallIntegerField()),
                ("month", models.PositiveSmallIntegerField()),
                ("transaction_count", models.PositiveIntegerField(default=0)),
                (
                    "total_amount",
                    models.DecimalField(decimal_places=2, max_digits=15),
                ),
                ("raw_data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="monthly_sales_summaries",
                        to="businesses.business",
                    ),
                ),
            ],
            options={
                "ordering": ["-year", "-month", "source_type"],
                "indexes": [
                    models.Index(
                        fields=["business", "year", "month"],
                        name="sales_sum_biz_period_idx",
                    )
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("business", "source_type", "year", "month"),
                        name="uniq_monthly_sales_summary",
                    ),
                    models.CheckConstraint(
                        condition=Q(("month__gte", 1), ("month__lte", 12)),
                        name="sales_summary_month_range",
                    ),
                ],
            },
        ),
        migrations.AddIndex(
            model_name="transaction",
            index=models.Index(
                fields=["business", "expense_purpose", "transaction_date"],
                name="txn_biz_purpose_date_idx",
            ),
        ),
    ]
