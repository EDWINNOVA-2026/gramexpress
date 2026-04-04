from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase
from django.test.utils import override_settings
from django.urls import reverse

from .admin import approve_riders, approve_stores
from .models import (
    ApprovalStatus,
    AuthOtpToken,
    CustomerProfile,
    Notification,
    Order,
    OrderItem,
    OrderStatus,
    OtpPurpose,
    Product,
    RiderProfile,
    RoleType,
    Shop,
    ShopOwnerProfile,
)


class CoreFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.customer_user = User.objects.create_user(
            username=f'{RoleType.CUSTOMER}:9999999999',
            password='demo12345',
            email='ananya@example.com',
        )
        cls.customer = CustomerProfile.objects.create(
            user=cls.customer_user,
            full_name='Ananya',
            phone='9999999999',
            email='ananya@example.com',
            address_line_1='1 MG Road',
            district='Mandya',
            pincode='571401',
            latitude=Decimal('12.915300'),
            longitude=Decimal('76.643800'),
        )

        cls.shop_user = User.objects.create_user(
            username=f'{RoleType.SHOP}:8888888888',
            password='demo12345',
            email='mahesh@example.com',
        )
        cls.owner = ShopOwnerProfile.objects.create(
            user=cls.shop_user,
            full_name='Mahesh',
            phone='8888888888',
            email='mahesh@example.com',
            approval_status=ApprovalStatus.APPROVED,
        )
        cls.shop = Shop.objects.create(
            owner=cls.owner,
            name='Fresh Basket',
            shop_type='kirana',
            area='VV Nagar',
            address_line_1='12 Market Street',
            district='Mandya',
            pincode='571401',
            approval_status=ApprovalStatus.APPROVED,
            is_open=True,
            latitude=Decimal('12.915300'),
            longitude=Decimal('76.643800'),
        )
        cls.product = Product.objects.create(
            shop=cls.shop,
            name='Milk',
            subtitle='Fresh packet',
            category='Dairy',
            unit='500 ml',
            price=Decimal('28.00'),
            stock=20,
        )

        cls.rider_user = User.objects.create_user(
            username=f'{RoleType.RIDER}:7777777777',
            password='demo12345',
            email='suresh@example.com',
        )
        cls.rider = RiderProfile.objects.create(
            user=cls.rider_user,
            full_name='Suresh',
            phone='7777777777',
            email='suresh@example.com',
            age=24,
            vehicle_type='electric',
            approval_status=ApprovalStatus.APPROVED,
            is_available=True,
            latitude=Decimal('12.915300'),
            longitude=Decimal('76.643800'),
        )

        cls.demo_order = Order.objects.create(
            customer=cls.customer,
            shop=cls.shop,
            rider=cls.rider,
            status=OrderStatus.OUT_FOR_DELIVERY,
            total_amount=Decimal('76.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
            customer_otp='123456',
        )
        OrderItem.objects.create(
            order=cls.demo_order,
            product=cls.product,
            quantity=2,
            unit_price=Decimal('28.00'),
        )
        Notification.objects.create(
            customer=cls.customer,
            order=cls.demo_order,
            title='Rider is nearby',
            body='Suresh is bringing your order now.',
        )

        cls.admin_user = User.objects.create_superuser(
            username='admin',
            password='admin123',
            email='admin@example.com',
        )

    def setUp(self):
        self.client = Client()

    def test_login_route_renders(self):
        response = self.client.get(reverse('core:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sign in to your local delivery workspace')
        self.assertContains(response, 'Continue with Google')

    def test_register_route_renders(self):
        response = self.client.get(reverse('core:register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create Account')
        self.assertContains(response, 'Send Mobile OTP')

    def test_root_redirects_to_login_for_anonymous_users(self):
        response = self.client.get(reverse('core:home'))
        self.assertRedirects(response, reverse('core:login'))

    def test_root_redirects_to_role_dashboard_for_signed_in_user(self):
        self.client.force_login(self.customer_user)
        response = self.client.get(reverse('core:home'))
        self.assertRedirects(response, reverse('core:customer_dashboard'))

    def test_customer_can_add_to_cart_and_checkout(self):
        self.client.force_login(self.customer_user)
        before_count = Order.objects.count()
        add_response = self.client.post(reverse('core:cart_add', args=[self.product.id]), {'quantity': '2'})
        self.assertEqual(add_response.status_code, 302)

        review_response = self.client.post(
            reverse('core:customer_checkout'),
            {'action': 'review', 'payment_method': 'cod', 'customer_notes': 'Leave at gate'},
            follow=True,
        )
        self.assertEqual(review_response.status_code, 200)
        self.assertContains(review_response, 'Review your order')

        checkout_response = self.client.post(
            reverse('core:customer_checkout'),
            {'action': 'confirm'},
            follow=True,
        )
        self.assertEqual(checkout_response.status_code, 200)
        self.assertContains(checkout_response, 'Order placed')
        self.assertEqual(Order.objects.count(), before_count + 1)
        order = Order.objects.latest('id')
        self.assertEqual(order.customer, self.customer)
        self.assertEqual(order.shop, self.shop)
        self.assertEqual(order.rider, self.rider)
        self.assertEqual(order.status, OrderStatus.CONFIRMED)
        self.assertEqual(order.items.get().quantity, 2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 18)

    def test_checkout_blocks_when_stock_changes_after_cart_add(self):
        self.client.force_login(self.customer_user)
        self.client.post(reverse('core:cart_add', args=[self.product.id]), {'quantity': '2'})
        self.product.stock = 1
        self.product.save(update_fields=['stock'])

        response = self.client.get(reverse('core:customer_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Checkout is blocked until these issues are fixed')
        self.assertContains(response, 'Only 1 unit(s) are available right now.')

    def test_customer_can_open_notifications_center(self):
        self.client.force_login(self.customer_user)
        response = self.client.get(reverse('core:notifications'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Notification Centre')
        self.assertContains(response, 'Rider is nearby')

    def test_customer_can_open_order_detail_and_tracking(self):
        self.client.force_login(self.customer_user)
        detail_response = self.client.get(reverse('core:order_detail', args=[self.demo_order.id]))
        tracking_response = self.client.get(reverse('core:order_tracking', args=[self.demo_order.id]))
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(tracking_response.status_code, 200)
        self.assertContains(detail_response, self.demo_order.display_id)
        self.assertContains(tracking_response, 'Live Tracking')

    def test_customer_can_cancel_confirmed_order_and_restore_stock(self):
        product = Product.objects.create(
            shop=self.shop,
            name='Soap',
            subtitle='Bath bar',
            category='Personal Care',
            unit='1 pack',
            price=Decimal('30.00'),
            stock=2,
        )
        cancellable_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            status=OrderStatus.CONFIRMED,
            total_amount=Decimal('50.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
        )
        OrderItem.objects.create(order=cancellable_order, product=product, quantity=1, unit_price=Decimal('30.00'))

        self.client.force_login(self.customer_user)
        response = self.client.post(
            reverse('core:customer_cancel_order', args=[cancellable_order.id]),
            {'cancellation_reason': 'Ordered by mistake'},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        cancellable_order.refresh_from_db()
        product.refresh_from_db()
        self.rider.refresh_from_db()
        self.assertEqual(cancellable_order.status, OrderStatus.CANCELLED)
        self.assertEqual(cancellable_order.cancellation_reason, 'Ordered by mistake')
        self.assertEqual(product.stock, 3)
        self.assertTrue(self.rider.is_available)

    def test_customer_can_reorder_delivered_items(self):
        reorder_product = Product.objects.create(
            shop=self.shop,
            name='Biscuits',
            subtitle='Tea snack',
            category='Snacks',
            unit='2 packs',
            price=Decimal('40.00'),
            stock=4,
        )
        delivered_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            status=OrderStatus.DELIVERED,
            total_amount=Decimal('60.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
        )
        OrderItem.objects.create(order=delivered_order, product=reorder_product, quantity=2, unit_price=Decimal('20.00'))

        self.client.force_login(self.customer_user)
        response = self.client.post(reverse('core:customer_reorder', args=[delivered_order.id]), follow=True)
        self.assertEqual(response.status_code, 200)
        session_cart = self.client.session.get('customer_cart', {})
        self.assertEqual(session_cart[str(reorder_product.id)], 2)

    def test_registration_flow_sends_mobile_otp_and_creates_customer(self):
        register_payload = {
            'action': 'register',
            'account_type': RoleType.CUSTOMER,
            'full_name': 'New User',
            'phone': '9990001112',
            'email': 'newuser@example.com',
            'password1': 'newpass12345',
            'password2': 'newpass12345',
            'preferred_language': 'en',
            'address_line_1': '5 Market Road',
            'address_line_2': '',
            'district': 'Mandya',
            'pincode': '571401',
            'latitude': '12.915300',
            'longitude': '76.643800',
        }
        response = self.client.post(reverse('core:register'), register_payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Verify your mobile number')

        otp = AuthOtpToken.objects.filter(
            purpose=OtpPurpose.REGISTER,
            phone='9990001112',
        ).latest('created_at')
        verify_response = self.client.post(
            reverse('core:register'),
            {'action': 'verify_register_otp', 'code': otp.code},
            follow=True,
        )
        self.assertEqual(verify_response.status_code, 200)
        self.assertTrue(CustomerProfile.objects.filter(phone='9990001112').exists())
        self.assertContains(verify_response, 'New User')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_email_login_requires_otp_before_completion(self):
        first_response = self.client.post(
            reverse('core:login'),
            {
                'action': 'login',
                'identity': 'ananya@example.com',
                'password': 'demo12345',
            },
            follow=True,
        )
        self.assertEqual(first_response.status_code, 200)
        self.assertContains(first_response, 'Check your inbox')
        self.assertEqual(len(mail.outbox), 1)

        otp = AuthOtpToken.objects.filter(
            purpose=OtpPurpose.LOGIN_EMAIL,
            email='ananya@example.com',
        ).latest('created_at')
        second_response = self.client.post(
            reverse('core:login'),
            {'action': 'verify_login_otp', 'code': otp.code},
            follow=True,
        )
        self.assertEqual(second_response.status_code, 200)
        self.assertContains(second_response, 'Ananya')

    def test_admin_actions_can_approve_pending_entities(self):
        pending_user = get_user_model().objects.create_user(
            username=f'{RoleType.SHOP}:6666666666',
            password='demo12345',
        )
        pending_owner = ShopOwnerProfile.objects.create(
            user=pending_user,
            full_name='Pending Owner',
            phone='6666666666',
            email='pending-owner@example.com',
        )
        pending_shop = Shop.objects.create(
            owner=pending_owner,
            name='Pending Store',
            shop_type='medical',
            area='Ring Road',
            address_line_1='45 Ring Road',
            district='Mandya',
            pincode='571401',
            latitude=Decimal('12.915300'),
            longitude=Decimal('76.643800'),
        )
        pending_rider_user = get_user_model().objects.create_user(
            username=f'{RoleType.RIDER}:5555555555',
            password='demo12345',
        )
        pending_rider = RiderProfile.objects.create(
            user=pending_rider_user,
            full_name='Pending Rider',
            phone='5555555555',
            email='pending-rider@example.com',
            age=28,
            vehicle_type='petrol',
            latitude=Decimal('12.915300'),
            longitude=Decimal('76.643800'),
        )

        self.client.force_login(self.admin_user)
        admin_response = self.client.get('/admin/')

        approve_stores(None, None, Shop.objects.filter(pk=pending_shop.id))
        approve_riders(None, None, RiderProfile.objects.filter(pk=pending_rider.id))

        pending_shop.refresh_from_db()
        pending_owner.refresh_from_db()
        pending_rider.refresh_from_db()

        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(pending_shop.approval_status, ApprovalStatus.APPROVED)
        self.assertTrue(pending_shop.is_open)
        self.assertEqual(pending_owner.approval_status, ApprovalStatus.APPROVED)
        self.assertEqual(pending_rider.approval_status, ApprovalStatus.APPROVED)
        self.assertTrue(pending_rider.is_available)
