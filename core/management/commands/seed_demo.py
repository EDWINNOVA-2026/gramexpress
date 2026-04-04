from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from core.models import (
    ApprovalStatus,
    CustomerProfile,
    Notification,
    Order,
    OrderItem,
    OrderStatus,
    PaymentMethod,
    PaymentStatus,
    Product,
    RiderProfile,
    RoleType,
    Shop,
    ShopOwnerProfile,
    ShopType,
    VehicleType,
)


class Command(BaseCommand):
    help = 'Seed the Django web demo with GramExpress sample data.'

    def handle(self, *args, **options):
        User = get_user_model()
        admin_user, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@gramexpress.demo',
                'is_staff': True,
                'is_superuser': True,
            },
        )
        admin_user.set_password('admin123')
        admin_user.save()
        self.stdout.write(self.style.SUCCESS('Admin user ready: admin / admin123'))

        customer_user, _ = User.objects.get_or_create(
            username=f'{RoleType.CUSTOMER}:+919188843299',
            defaults={'email': 'rajesh.kumar@gmail.com', 'first_name': 'Rajesh Kumar'},
        )
        customer_user.set_password('demo12345')
        customer_user.save()

        shop_user, _ = User.objects.get_or_create(
            username=f'{RoleType.SHOP}:+919900010101',
            defaults={'email': 'shivanna@gramexpress.demo', 'first_name': 'Shivanna'},
        )
        shop_user.set_password('demo12345')
        shop_user.save()

        rider_user, _ = User.objects.get_or_create(
            username=f'{RoleType.RIDER}:+919900011111',
            defaults={'email': 'ramesh@gramexpress.demo', 'first_name': 'Ramesh K'},
        )
        rider_user.set_password('demo12345')
        rider_user.save()

        customer, _ = CustomerProfile.objects.update_or_create(
            phone='+919188843299',
            defaults={
                'user': customer_user,
                'full_name': 'Rajesh Kumar',
                'email': 'rajesh.kumar@gmail.com',
                'preferred_language': 'en',
                'address_line_1': '12 Main Street',
                'address_line_2': 'Near Bus Stand',
                'district': 'Hassan',
                'pincode': '573201',
                'latitude': Decimal('12.307200'),
                'longitude': Decimal('76.649200'),
            },
        )

        owner, _ = ShopOwnerProfile.objects.update_or_create(
            phone='+919900010101',
            defaults={
                'user': shop_user,
                'full_name': 'Shivanna',
                'email': 'shivanna@gramexpress.demo',
                'approval_status': ApprovalStatus.APPROVED,
            },
        )
        rider, _ = RiderProfile.objects.update_or_create(
            phone='+919900011111',
            defaults={
                'user': rider_user,
                'full_name': 'Ramesh K',
                'email': 'ramesh@gramexpress.demo',
                'age': 24,
                'vehicle_type': VehicleType.ELECTRIC,
                'approval_status': ApprovalStatus.APPROVED,
                'is_available': True,
                'latitude': Decimal('12.302000'),
                'longitude': Decimal('76.642500'),
            },
        )
        shop, _ = Shop.objects.update_or_create(
            owner=owner,
            name='Srinivasa Kirana',
            defaults={
                'shop_type': ShopType.KIRANA,
                'area': 'Salagame Road',
                'address_line_1': '45 Market Lane',
                'address_line_2': '',
                'district': 'Hassan',
                'pincode': '573201',
                'description': 'Farm-fresh vegetables, milk, grains, and daily needs.',
                'offer': 'Free delivery above Rs. 299',
                'approval_status': ApprovalStatus.APPROVED,
                'is_open': True,
                'rating': Decimal('4.8'),
                'latitude': Decimal('12.308100'),
                'longitude': Decimal('76.645300'),
            },
        )

        milk, _ = Product.objects.update_or_create(
            shop=shop,
            name='Nandini Milk',
            defaults={
                'subtitle': 'Fresh milk pouch',
                'category': 'grocery',
                'unit': '1 litre',
                'price': Decimal('52.00'),
                'stock': 50,
                'tag': 'Daily essentials',
            },
        )
        eggs, _ = Product.objects.update_or_create(
            shop=shop,
            name='Organic Desi Eggs',
            defaults={
                'subtitle': 'Farm fresh eggs',
                'category': 'grocery',
                'unit': '6 pack',
                'price': Decimal('78.00'),
                'stock': 30,
                'tag': 'Protein pick',
            },
        )

        order, _ = Order.objects.update_or_create(
            customer=customer,
            shop=shop,
            rider=rider,
            delivery_address='12 Main Street, Near Bus Stand, Hassan, 573201',
            defaults={
                'status': OrderStatus.OUT_FOR_DELIVERY,
                'payment_method': PaymentMethod.COD,
                'payment_status': PaymentStatus.PENDING,
                'delivery_fee': Decimal('20.00'),
                'total_amount': Decimal('150.00'),
                'customer_notes': 'Deliver near bus stand gate.',
            },
        )
        OrderItem.objects.update_or_create(
            order=order,
            product=milk,
            defaults={'quantity': 1, 'unit_price': milk.price},
        )
        OrderItem.objects.update_or_create(
            order=order,
            product=eggs,
            defaults={'quantity': 1, 'unit_price': eggs.price},
        )
        order.recalculate_total()
        order.save(update_fields=['total_amount'])

        Notification.objects.get_or_create(
            customer=customer,
            title='Welcome back',
            body='Your seeded customer account is ready for multi-store checkout.',
        )
        Notification.objects.get_or_create(
            shop_owner=owner,
            title='Store live',
            body='Your seeded store account is approved and ready for product edits.',
        )
        Notification.objects.get_or_create(
            rider=rider,
            title='Rider ready',
            body='Your seeded rider account is approved and available for dispatch.',
        )

        self.stdout.write(self.style.SUCCESS('Seeded demo customer, shop, rider, products, order, and notifications.'))
