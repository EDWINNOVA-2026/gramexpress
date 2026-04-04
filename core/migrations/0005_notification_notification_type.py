from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0004_order_cancellation_reason_order_cancelled_by_role'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='notification_type',
            field=models.CharField(
                choices=[
                    ('order', 'Order'),
                    ('store', 'Store'),
                    ('rider', 'Rider'),
                    ('payment', 'Payment'),
                    ('promo', 'Promo'),
                    ('system', 'System'),
                ],
                default='system',
                max_length=12,
            ),
        ),
    ]
