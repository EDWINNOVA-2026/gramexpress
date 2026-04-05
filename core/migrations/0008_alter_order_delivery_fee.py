from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_order_cash_confirmed_at_order_cod_collection_mode_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='delivery_fee',
            field=models.DecimalField(decimal_places=2, default=Decimal('15.00'), max_digits=10),
        ),
    ]
