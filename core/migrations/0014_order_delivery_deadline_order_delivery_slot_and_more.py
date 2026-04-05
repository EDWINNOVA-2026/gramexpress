from datetime import timedelta
import math
from decimal import Decimal
from django.db import migrations, models


def backfill_delivery_slot_fields(apps, schema_editor):
    Order = apps.get_model('core', 'Order')
    for order in Order.objects.select_related('shop', 'customer').all():
        if not order.delivery_deadline:
            order.delivery_deadline = order.created_at + timedelta(hours=4)
        if not order.delivery_slot:
            order.delivery_slot = 'ECO'
        if not order.distance_km and order.shop_id and order.customer_id:
            lat1 = math.radians(float(order.shop.latitude))
            lat2 = math.radians(float(order.customer.latitude))
            delta_lat = math.radians(float(order.customer.latitude - order.shop.latitude))
            delta_lng = math.radians(float(order.customer.longitude - order.shop.longitude))
            a = (
                math.sin(delta_lat / 2) ** 2
                + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lng / 2) ** 2
            )
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            order.distance_km = Decimal(str(round(6371 * c, 2)))
        order.save(update_fields=['delivery_deadline', 'delivery_slot', 'distance_km', 'updated_at'])


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0013_standardize_order_delivery_fee'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='delivery_deadline',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='order',
            name='delivery_slot',
            field=models.CharField(choices=[('PRIORITY', 'Priority Delivery'), ('ECO', 'Eco Delivery'), ('COST_SAVER', 'Cost Saver'), ('BUDGET', 'Budget Delivery')], default='ECO', max_length=20),
        ),
        migrations.AddField(
            model_name='order',
            name='distance_km',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=6),
        ),
        migrations.RunPython(backfill_delivery_slot_fields, noop_reverse),
    ]
