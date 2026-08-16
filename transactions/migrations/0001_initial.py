# Generated manually for Django 5.2 compatibility.

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("businesses", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Transaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "source_type",
                    models.CharField(
                        choices=[
                            ("CARD_PURCHASE", "카드 매입"),
                            ("CASH_RECEIPT_PURCHASE", "현금영수증 매입"),
                            ("CASH_RECEIPT_SALE", "현금영수증 매출"),
                            ("TAX_INVOICE", "전자세금계산서"),
                        ],
                        max_length=30,
                    ),
                ),
                ("external_id", models.CharField(max_length=255)),
                (
                    "transaction_type",
                    models.CharField(choices=[("PURCHASE", "매입"), ("SALE", "매출")], max_length=10),
                ),
                ("transaction_date", models.DateField()),
                ("transaction_time", models.TimeField(blank=True, null=True)),
                ("merchant_name", models.CharField(blank=True, max_length=255)),
                ("merchant_business_number", models.CharField(blank=True, max_length=20)),
                ("supply_amount", models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ("vat_amount", models.DecimalField(decimal_places=2, default=0, max_digits=15)),
                ("total_amount", models.DecimalField(decimal_places=2, max_digits=15)),
                ("approval_no", models.CharField(blank=True, max_length=100)),
                (
                    "cancel_status",
                    models.CharField(
                        choices=[("NORMAL", "정상"), ("CANCELLED", "취소")],
                        default="NORMAL",
                        max_length=10,
                    ),
                ),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("UNCLASSIFIED", "미분류"),
                            ("RAW_MATERIAL", "원재료"),
                            ("RENT", "임차료"),
                            ("UTILITIES", "공과금"),
                            ("SUPPLIES", "소모품"),
                            ("ADVERTISING", "광고비"),
                            ("DELIVERY", "운송·배달비"),
                            ("FEES", "수수료"),
                            ("EQUIPMENT", "시설·장비"),
                            ("OTHER", "기타"),
                        ],
                        default="UNCLASSIFIED",
                        max_length=30,
                    ),
                ),
                (
                    "classification_source",
                    models.CharField(
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
                (
                    "classification_confidence",
                    models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True),
                ),
                ("raw_data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transactions",
                        to="businesses.business",
                    ),
                ),
            ],
            options={
                "ordering": ["-transaction_date", "-transaction_time", "-id"],
                "indexes": [
                    models.Index(fields=["business", "transaction_date"], name="txn_biz_date_idx"),
                    models.Index(
                        fields=["business", "transaction_type", "transaction_date"],
                        name="txn_biz_type_date_idx",
                    ),
                    models.Index(fields=["business", "category"], name="txn_biz_category_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("business", "source_type", "external_id"),
                        name="uniq_transaction_external_id",
                    ),
                    models.CheckConstraint(
                        condition=(
                            Q(("classification_confidence__isnull", True))
                            | Q(
                                ("classification_confidence__gte", 0),
                                ("classification_confidence__lte", 1),
                            )
                        ),
                        name="transaction_confidence_range",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="TransactionDuplicate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "확인 대기"),
                            ("CONFIRMED", "중복 확정"),
                            ("DISMISSED", "중복 아님"),
                        ],
                        default="PENDING",
                        max_length=10,
                    ),
                ),
                ("confidence", models.DecimalField(blank=True, decimal_places=4, max_digits=5, null=True)),
                ("detection_reason", models.JSONField(blank=True, default=dict)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transaction_duplicates",
                        to="businesses.business",
                    ),
                ),
                (
                    "primary_transaction",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="duplicate_candidates_as_primary",
                        to="transactions.transaction",
                    ),
                ),
                (
                    "suspected_transaction",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="duplicate_candidates_as_suspected",
                        to="transactions.transaction",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "-id"],
                "indexes": [
                    models.Index(fields=["business", "status"], name="txn_dup_biz_status_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("primary_transaction", "suspected_transaction"),
                        name="uniq_transaction_duplicate_pair",
                    ),
                    models.CheckConstraint(
                        condition=~Q(("primary_transaction", F("suspected_transaction"))),
                        name="duplicate_transactions_differ",
                    ),
                    models.CheckConstraint(
                        condition=(
                            Q(("confidence__isnull", True))
                            | Q(("confidence__gte", 0), ("confidence__lte", 1))
                        ),
                        name="duplicate_confidence_range",
                    ),
                ],
            },
        ),
    ]
