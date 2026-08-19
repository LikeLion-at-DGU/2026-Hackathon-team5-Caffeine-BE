# Generated manually to match settings/models.py Subscription changes
# (PAST_DUE / EXPIRED status 추가, last_payment_error 필드 추가)

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('settings', '0003_delete_businessprofile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='subscription',
            name='status',
            field=models.CharField(
                choices=[
                    ('ACTIVE', '구독 이용 중'),
                    ('PAST_DUE', '결제 실패'),
                    ('CANCELLED', '구독 취소됨'),
                    ('EXPIRED', '이용 종료'),
                ],
                default='ACTIVE',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='subscription',
            name='last_payment_error',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
