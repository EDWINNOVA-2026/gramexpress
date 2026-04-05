from decimal import Decimal

from django.db import migrations


def standardize_order_delivery_fee(apps, schema_editor):
    Order = apps.get_model('core', 'Order')
    Order.objects.exclude(delivery_fee=Decimal('15.00')).update(delivery_fee=Decimal('15.00'))


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0012_product_description_product_image_product_is_visible_and_more'),
    ]

    operations = [
        migrations.RunPython(standardize_order_delivery_fee, noop_reverse),
    ]
