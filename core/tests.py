from decimal import Decimal
from datetime import timedelta
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, RequestFactory, TestCase
from django.test.utils import override_settings
from django.urls import reverse
from django.utils import timezone

from .admin import ShopOwnerProfileAdmin, approve_riders, approve_stores
from .models import (
    ApprovalStatus,
    AuthOtpToken,
    CodCollectionMode,
    CheckoutSession,
    CustomerProfile,
    KhataBookCollectionRequest,
    KhataBookCollectionStatus,
    KhataBookCycle,
    KhataBookCycleStatus,
    KhataBookSettlementMethod,
    Notification,
    NotificationType,
    Order,
    OrderItem,
    OrderStatus,
    OtpPurpose,
    PaymentMethod,
    PaymentStatus,
    Product,
    RiderProfile,
    RoleType,
    SettlementStatus,
    Shop,
    ShopOwnerProfile,
)
from .forms import UnifiedRegistrationForm
from .views import get_dashboard_url_for_user, reverse_geocode_location


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
            notification_type=NotificationType.RIDER,
        )

        cls.admin_user = User.objects.create_superuser(
            username='admin',
            password='admin123',
            email='admin@example.com',
        )

    def setUp(self):
        self.client = Client()
        self.request_factory = RequestFactory()

    def test_login_route_renders(self):
        response = self.client.get(reverse('core:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sign in to your local delivery workspace')
        self.assertContains(response, 'Continue with Google')
        self.assertContains(response, 'Use passwordless email OTP instead')
        self.assertEqual(response['Cache-Control'], 'no-store, no-cache, must-revalidate, max-age=0')

    def test_register_route_renders(self):
        response = self.client.get(reverse('core:register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Choose Your Role')
        self.assertContains(response, 'Open customer onboarding')
        self.assertEqual(response['Cache-Control'], 'no-store, no-cache, must-revalidate, max-age=0')

    def test_register_details_only_shows_selected_role_fields(self):
        response = self.client.get(f'{reverse("core:register_details")}?account_type={RoleType.CUSTOMER}')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Customer details')
        self.assertContains(response, 'Preferred Language')
        self.assertNotContains(response, 'Shop details')
        self.assertNotContains(response, 'Vehicle Type')
        self.assertNotContains(response, 'Open shop onboarding')

    def test_register_details_shop_shows_map_pin_controls(self):
        response = self.client.get(f'{reverse("core:register_details")}?account_type={RoleType.SHOP}')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Store location pin')
        self.assertContains(response, 'Use Current Location')
        self.assertContains(response, 'Pick On Map')
        self.assertContains(response, 'Confirm Location')
        self.assertContains(response, 'State')

    def test_root_renders_landing_page_for_anonymous_users(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Hyperlocal delivery with proper customer, store, and rider workspaces')
        self.assertContains(response, 'Separate feature pages')

    def test_root_redirects_to_role_dashboard_for_signed_in_user(self):
        self.client.force_login(self.customer_user)
        response = self.client.get(reverse('core:home'))
        self.assertRedirects(response, reverse('core:customer_dashboard'))

    def test_registration_phone_requires_exactly_ten_digits(self):
        form = UnifiedRegistrationForm(
            data={
                'account_type': RoleType.CUSTOMER,
                'full_name': 'Phone Check',
                'phone': '98765',
                'email': 'phonecheck@example.com',
                'password1': 'demo12345',
                'password2': 'demo12345',
                'preferred_language': 'en',
                'address_line_1': '1 MG Road',
                'district': 'Mandya',
                'pincode': '571401',
                'latitude': '12.915300',
                'longitude': '76.643800',
            },
            selected_role=RoleType.CUSTOMER,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('Enter a valid 10 digit mobile number.', form.errors['phone'])

    def test_registration_shows_contact_conflicts_under_specific_fields(self):
        response = self.client.post(
            reverse('core:register_details') + f'?account_type={RoleType.CUSTOMER}',
            {
                'account_type': RoleType.CUSTOMER,
                'full_name': 'Duplicate Contact',
                'phone': self.customer.phone,
                'email': self.customer.email,
                'password1': 'demo12345',
                'password2': 'demo12345',
                'preferred_language': 'en',
                'address_line_1': '1 MG Road',
                'district': 'Mandya',
                'pincode': '571401',
                'latitude': '12.915300',
                'longitude': '76.643800',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'This mobile number is already linked to an existing account.')
        self.assertContains(response, 'This email address is already linked to an existing account.')
        self.assertNotContains(response, 'That phone number or email is already linked to an existing account.')

    @patch('core.views.reverse_geocode_location')
    def test_reverse_geocode_location_api_returns_json(self, reverse_geocode_mock):
        reverse_geocode_mock.return_value = {
            'formatted_address': '12 Market Street, VV Nagar, Mandya 571401',
            'address_line_1': '12 Market Street',
            'locality': 'VV Nagar',
            'city': 'Mandya',
            'district': 'Mandya',
            'state': 'Karnataka',
            'pincode': '571401',
        }

        response = self.client.get(
            reverse('core:reverse_geocode_location_api'),
            {'latitude': '12.915300', 'longitude': '76.643800'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {
                'formatted_address': '12 Market Street, VV Nagar, Mandya 571401',
                'address_line_1': '12 Market Street',
                'locality': 'VV Nagar',
                'city': 'Mandya',
                'district': 'Mandya',
                'state': 'Karnataka',
                'pincode': '571401',
            },
        )

    def test_shop_dashboard_redirects_to_setup_when_shop_record_is_missing(self):
        user = get_user_model().objects.create_user(
            username=f'{RoleType.SHOP}:6666666666',
            password='demo12345',
            email='setup@example.com',
        )
        owner = ShopOwnerProfile.objects.create(
            user=user,
            full_name='Setup Pending',
            phone='6666666666',
            email='setup@example.com',
            approval_status=ApprovalStatus.PENDING,
        )

        self.client.force_login(user)
        response = self.client.get(reverse('core:shop_dashboard'), follow=True)

        self.assertRedirects(response, reverse('core:shop_start'))
        self.assertContains(response, 'Complete your store details to open the store workspace.')
        self.assertFalse(owner.shops.exists())

    def test_shop_owner_can_toggle_store_state_from_dashboard(self):
        self.client.force_login(self.shop_user)

        response = self.client.post(reverse('core:shop_toggle_store_state'))

        self.assertRedirects(response, reverse('core:shop_dashboard'))
        self.shop.refresh_from_db()
        self.assertFalse(self.shop.is_open)
        self.assertTrue(
            Notification.objects.filter(
                shop_owner=self.owner,
                title='Store closed',
                notification_type=NotificationType.STORE,
            ).exists()
        )

    def test_shop_toggle_store_state_keeps_pending_store_closed(self):
        pending_user = get_user_model().objects.create_user(
            username=f'{RoleType.SHOP}:6655555511',
            password='demo12345',
            email='pendingtoggle@example.com',
        )
        pending_owner = ShopOwnerProfile.objects.create(
            user=pending_user,
            full_name='Pending Toggle',
            phone='6655555511',
            email='pendingtoggle@example.com',
            approval_status=ApprovalStatus.PENDING,
        )
        pending_shop = Shop.objects.create(
            owner=pending_owner,
            name='Pending Toggle Mart',
            shop_type='kirana',
            area='VV Nagar',
            address_line_1='44 Market Street',
            district='Mandya',
            pincode='571401',
            approval_status=ApprovalStatus.PENDING,
            is_open=False,
            latitude=Decimal('12.915300'),
            longitude=Decimal('76.643800'),
        )

        self.client.force_login(pending_user)
        response = self.client.post(reverse('core:shop_toggle_store_state'), follow=True)

        self.assertRedirects(response, reverse('core:shop_dashboard'))
        pending_shop.refresh_from_db()
        self.assertFalse(pending_shop.is_open)
        self.assertContains(response, 'Your store can go live only after admin approval.')

    def test_shop_user_without_shop_gets_shop_start_dashboard_url(self):
        user = get_user_model().objects.create_user(
            username=f'{RoleType.SHOP}:6655555555',
            password='demo12345',
            email='start@example.com',
        )
        ShopOwnerProfile.objects.create(
            user=user,
            full_name='Start Pending',
            phone='6655555555',
            email='start@example.com',
            approval_status=ApprovalStatus.PENDING,
        )

        self.assertEqual(get_dashboard_url_for_user(user), reverse('core:shop_start'))

    def test_shop_settings_page_shows_location_editor_controls(self):
        self.client.force_login(self.shop_user)

        response = self.client.get(reverse('core:shop_settings'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Store Location')
        self.assertContains(response, 'Use Current Location')
        self.assertContains(response, 'Pick On Map')
        self.assertContains(response, 'Confirm Location')

    def test_shop_cannot_go_live_when_location_is_not_ready(self):
        self.client.force_login(self.shop_user)
        self.shop.is_open = False
        self.shop.address_line_1 = ''
        self.shop.district = ''
        self.shop.pincode = ''
        self.shop.save(update_fields=['is_open', 'address_line_1', 'district', 'pincode', 'updated_at'])

        response = self.client.post(reverse('core:shop_toggle_store_state'), follow=True)

        self.shop.refresh_from_db()
        self.assertRedirects(response, reverse('core:shop_settings'))
        self.assertFalse(self.shop.is_open)
        self.assertContains(response, 'Set your exact store location in Storefront Settings before going live.')

    def test_shop_start_renders_setup_form_for_authenticated_shop_without_store(self):
        user = get_user_model().objects.create_user(
            username=f'{RoleType.SHOP}:6644444444',
            password='demo12345',
            email='missing-shop@example.com',
        )
        ShopOwnerProfile.objects.create(
            user=user,
            full_name='Missing Shop',
            phone='6644444444',
            email='missing-shop@example.com',
            approval_status=ApprovalStatus.PENDING,
        )

        self.client.force_login(user)
        response = self.client.get(reverse('core:shop_start'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Complete Store Setup')
        self.assertContains(response, 'Save Store Setup')

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
        self.assertIsNone(order.rider)
        self.assertEqual(order.status, OrderStatus.CONFIRMED)
        self.assertEqual(order.items.get().quantity, 2)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 18)
        self.rider.refresh_from_db()
        self.assertTrue(self.rider.is_available)

    def test_customer_can_checkout_with_khatabook_credit(self):
        self.client.force_login(self.customer_user)
        self.client.post(reverse('core:cart_add', args=[self.product.id]), {'quantity': '1'})

        review_response = self.client.post(
            reverse('core:customer_checkout'),
            {'action': 'review', 'payment_method': 'khata', 'customer_notes': 'Add to weekly credit'},
            follow=True,
        )
        self.assertEqual(review_response.status_code, 200)
        self.assertContains(review_response, 'Added to KhataBook')

        checkout_response = self.client.post(
            reverse('core:customer_checkout'),
            {'action': 'confirm'},
            follow=True,
        )
        self.assertEqual(checkout_response.status_code, 200)
        self.assertContains(checkout_response, 'Added to KhataBook')

        order = Order.objects.latest('id')
        cycle = KhataBookCycle.objects.latest('id')
        self.assertEqual(order.payment_method, PaymentMethod.KHATABOOK)
        self.assertEqual(order.payment_status, PaymentStatus.PENDING)
        self.assertEqual(order.khata_cycle, cycle)
        self.assertEqual(order.credit_due_date, cycle.due_date)
        self.assertEqual(cycle.total_amount, order.total_amount)
        self.assertEqual(cycle.status, KhataBookCycleStatus.OPEN)

    def test_customer_can_request_khatabook_collection(self):
        cycle = KhataBookCycle.objects.create(
            customer=self.customer,
            week_start=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=7),
            total_amount=Decimal('53.00'),
        )
        khata_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            khata_cycle=cycle,
            status=OrderStatus.CONFIRMED,
            payment_method=PaymentMethod.KHATABOOK,
            payment_status=PaymentStatus.PENDING,
            total_amount=Decimal('53.00'),
            delivery_fee=Decimal('15.00'),
            delivery_address='1 MG Road, Mandya 571401',
            credit_due_date=cycle.due_date,
        )
        OrderItem.objects.create(order=khata_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))

        self.client.force_login(self.customer_user)
        response = self.client.post(reverse('core:customer_khatabook_request_collection'), follow=True)

        self.assertEqual(response.status_code, 200)
        cycle.refresh_from_db()
        self.assertEqual(cycle.status, KhataBookCycleStatus.COLLECTION_REQUESTED)
        self.assertEqual(cycle.settlement_method, KhataBookSettlementMethod.COD_UPI)
        self.assertContains(response, 'delivery agent might take time to arrive')

    def test_new_checkout_order_stays_in_rider_new_tab_until_acceptance(self):
        pending_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            status=OrderStatus.CONFIRMED,
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
        )
        OrderItem.objects.create(order=pending_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))

        self.client.force_login(self.rider_user)
        response = self.client.get(reverse('core:rider_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, pending_order.display_id)
        self.assertContains(response, 'Accept Order')

        active_response = self.client.get(reverse('core:rider_deliveries'))
        self.assertEqual(active_response.status_code, 200)
        self.assertNotContains(active_response, pending_order.display_id)

    def test_checkout_blocks_when_stock_changes_after_cart_add(self):
        self.client.force_login(self.customer_user)
        self.client.post(reverse('core:cart_add', args=[self.product.id]), {'quantity': '2'})
        self.product.stock = 1
        self.product.save(update_fields=['stock'])

        response = self.client.get(reverse('core:customer_cart'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Checkout is blocked until these issues are fixed')
        self.assertContains(response, 'Only 1 unit(s) are available right now.')

    @override_settings(RAZORPAY_KEY_ID='rzp_test_123', RAZORPAY_KEY_SECRET='secret_123')
    def test_customer_cart_shows_payment_buttons(self):
        self.client.force_login(self.customer_user)
        self.client.post(reverse('core:cart_add', args=[self.product.id]), {'quantity': '1'})

        response = self.client.get(reverse('core:customer_cart'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'RazorPay')
        self.assertContains(response, 'KhataBook')
        self.assertContains(response, 'Cash/UPI on delivery')

    def test_customer_can_update_cart_quantity_inline(self):
        self.client.force_login(self.customer_user)
        self.client.post(reverse('core:cart_add', args=[self.product.id]), {'quantity': '1'})

        response = self.client.post(
            reverse('core:cart_update', args=[self.product.id]),
            {'quantity': '3'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session.get('customer_cart', {}).get(str(self.product.id)), 3)
        self.assertContains(response, 'Cart updated.')

    def test_customer_store_detail_page_lists_products(self):
        self.client.force_login(self.customer_user)
        self.client.post(
            reverse('core:customer_update_location'),
            {'latitude': '12.920000', 'longitude': '76.650000'},
        )

        response = self.client.get(reverse('core:customer_store_detail', args=[self.shop.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.shop.name)
        self.assertContains(response, self.product.name)

    def test_customer_dashboard_requires_live_location_before_listing_stores(self):
        self.client.force_login(self.customer_user)

        response = self.client.get(reverse('core:customer_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Location needed before we show stores')
        self.assertNotContains(response, self.shop.name)

    def test_customer_can_update_location_from_dashboard(self):
        self.client.force_login(self.customer_user)

        with patch(
            'core.views.reverse_geocode_location',
            return_value={
                'formatted_address': 'Conservency Road, Basavanahalli, Chikkamagaluru, Karnataka 577101, India',
                'address_line_1': 'Conservency Road',
                'locality': 'Basavanahalli',
                'city': 'Chikkamagaluru',
                'district': 'Chikkamagaluru',
                'pincode': '577101',
            },
        ):
            response = self.client.post(
                reverse('core:customer_update_location'),
                {'latitude': '12.920000', 'longitude': '76.650000'},
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(str(self.customer.latitude), '12.920000')
        self.assertEqual(str(self.customer.longitude), '76.650000')
        self.assertTrue(self.client.session.get('customer_live_location_confirmed'))
        self.assertEqual(
            self.client.session.get('customer_live_location_label'),
            'Conservency Road, Basavanahalli, Chikkamagaluru, Karnataka 577101, India',
        )
        self.assertEqual(self.client.session.get('customer_live_location_heading'), 'Basavanahalli')
        self.assertContains(response, 'Basavanahalli')
        self.assertContains(response, 'Chikkamagaluru')
        self.assertContains(response, self.shop.name)

    def test_customer_dashboard_shows_dynamic_store_rating_details(self):
        self.client.force_login(self.customer_user)
        self.client.post(
            reverse('core:customer_update_location'),
            {'latitude': '12.920000', 'longitude': '76.650000'},
        )
        self.demo_order.status = OrderStatus.DELIVERED
        self.demo_order.customer_rating = 4
        self.demo_order.save(update_fields=['status', 'customer_rating', 'updated_at'])

        response = self.client.get(reverse('core:customer_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '4.0')
        self.assertContains(response, '1 rating')

    @override_settings(GOOGLE_MAPS_BROWSER_API_KEY='')
    def test_reverse_geocode_location_uses_openstreetmap_fallback_without_google_key(self):
        payload = {
            'display_name': 'Conservency Road, Basavanahalli, Chikkamagaluru, Karnataka 577101, India',
            'address': {
                'road': 'Conservency Road',
                'suburb': 'Basavanahalli',
                'city': 'Chikkamagaluru',
                'postcode': '577101',
            },
        }
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(payload).encode('utf-8')
        mock_context = MagicMock()
        mock_context.__enter__.return_value = mock_response
        mock_context.__exit__.return_value = False

        with patch('core.views.urllib_request.urlopen', return_value=mock_context) as mock_urlopen:
            details = reverse_geocode_location(Decimal('13.024161'), Decimal('74.966951'))

        request = mock_urlopen.call_args[0][0]
        self.assertIn('nominatim.openstreetmap.org/reverse?', request.full_url)
        self.assertEqual(
            details,
            {
                'formatted_address': 'Conservency Road, Basavanahalli, Chikkamagaluru, Karnataka 577101, India',
                'address_line_1': 'Conservency Road',
                'locality': 'Basavanahalli',
                'city': 'Chikkamagaluru',
                'district': 'Basavanahalli',
                'state': '',
                'pincode': '577101',
            },
        )

    def test_customer_can_remove_cart_item_inline(self):
        self.client.force_login(self.customer_user)
        self.client.post(reverse('core:cart_add', args=[self.product.id]), {'quantity': '2'})

        response = self.client.post(
            reverse('core:cart_update', args=[self.product.id]),
            {'quantity': '0'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(str(self.product.id), self.client.session.get('customer_cart', {}))

    def test_customer_can_open_notifications_center(self):
        self.client.force_login(self.customer_user)
        response = self.client.get(reverse('core:notifications'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Notification Centre')
        self.assertContains(response, 'Rider is nearby')
        self.assertContains(response, 'Rider')

    def test_customer_order_detail_uses_email_updates_and_tracking_route_redirects(self):
        self.client.force_login(self.customer_user)
        detail_response = self.client.get(reverse('core:order_detail', args=[self.demo_order.id]))
        tracking_response = self.client.get(reverse('core:order_tracking', args=[self.demo_order.id]), follow=True)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(tracking_response.status_code, 200)
        self.assertContains(detail_response, self.demo_order.display_id)
        self.assertContains(detail_response, 'Email updates')
        self.assertContains(detail_response, 'Rider picked up your order')
        self.assertContains(tracking_response, 'Use order details and email updates instead.')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_rider_can_accept_available_order_and_email_customer(self):
        available_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            status=OrderStatus.CONFIRMED,
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
        )
        OrderItem.objects.create(order=available_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))

        self.client.force_login(self.rider_user)
        response = self.client.post(reverse('core:rider_accept_order', args=[available_order.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        available_order.refresh_from_db()
        self.rider.refresh_from_db()
        self.assertEqual(available_order.rider, self.rider)
        self.assertEqual(available_order.status, OrderStatus.PACKED)
        self.assertFalse(self.rider.is_available)
        self.assertEqual(len(mail.outbox), 2)
        subjects = {message.subject for message in mail.outbox}
        self.assertIn(f'Your order {available_order.display_id} now has a rider', subjects)
        self.assertIn(f'Rider assigned for {available_order.display_id}', subjects)
        self.assertIn(self.rider.full_name, mail.outbox[0].body + mail.outbox[1].body)
        self.assertIn(self.rider.phone, mail.outbox[0].body + mail.outbox[1].body)

    def test_rider_must_be_near_store_to_mark_pickup(self):
        pickup_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            status=OrderStatus.PACKED,
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
        )
        OrderItem.objects.create(order=pickup_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))
        self.rider.latitude = Decimal('13.100000')
        self.rider.longitude = Decimal('76.900000')
        self.rider.save(update_fields=['latitude', 'longitude'])

        self.client.force_login(self.rider_user)
        response = self.client.post(
            reverse('core:rider_update_order_status', args=[pickup_order.id]),
            {'status': OrderStatus.OUT_FOR_DELIVERY},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        pickup_order.refresh_from_db()
        self.assertEqual(pickup_order.status, OrderStatus.PACKED)
        self.assertContains(response, 'Get closer to the store to mark pickup.')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_rider_pickup_email_includes_delivery_otp(self):
        pickup_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            status=OrderStatus.PACKED,
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
            customer_otp='456789',
        )
        OrderItem.objects.create(order=pickup_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))

        self.client.force_login(self.rider_user)
        response = self.client.post(
            reverse('core:rider_update_order_status', args=[pickup_order.id]),
            {'status': OrderStatus.OUT_FOR_DELIVERY},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        pickup_order.refresh_from_db()
        self.assertEqual(pickup_order.status, OrderStatus.OUT_FOR_DELIVERY)
        self.assertEqual(len(mail.outbox), 2)
        combined_mail = '\n'.join(message.subject + '\n' + message.body for message in mail.outbox)
        self.assertIn('has been picked up', combined_mail)
        self.assertIn('picked up by rider', combined_mail)
        self.assertIn('Delivery OTP', combined_mail)
        self.assertIn('456789', combined_mail)
        pickup_note = self.customer.notifications.filter(order=pickup_order).latest('created_at')
        self.assertIn('456789', pickup_note.body)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_rider_can_resend_customer_otp(self):
        delivery_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            status=OrderStatus.OUT_FOR_DELIVERY,
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
            customer_otp='777888',
        )
        OrderItem.objects.create(order=delivery_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))

        self.client.force_login(self.rider_user)
        response = self.client.post(
            reverse('core:rider_resend_customer_otp', args=[delivery_order.id]),
            {'next': reverse('core:rider_deliveries')},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Delivery OTP reminder', mail.outbox[0].subject)
        delivery_order.refresh_from_db()
        self.assertNotEqual(delivery_order.customer_otp, '777888')
        self.assertIn(delivery_order.customer_otp, mail.outbox[0].body)
        resend_note = self.customer.notifications.filter(order=delivery_order).latest('created_at')
        self.assertIn(delivery_order.customer_otp, resend_note.body)
        self.assertEqual(response.request['PATH_INFO'], reverse('core:rider_deliveries'))

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_rider_cannot_resend_customer_otp_during_cooldown(self):
        delivery_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            status=OrderStatus.OUT_FOR_DELIVERY,
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
            customer_otp='777888',
        )
        OrderItem.objects.create(order=delivery_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))
        Notification.objects.create(
            customer=self.customer,
            order=delivery_order,
            title='Delivery OTP resent',
            body='Cooldown test',
            notification_type=NotificationType.RIDER,
        )

        self.client.force_login(self.rider_user)
        response = self.client.post(
            reverse('core:rider_resend_customer_otp', args=[delivery_order.id]),
            {'next': reverse('core:rider_deliveries')},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Wait 45 seconds before resending the OTP again.')
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_rider_cannot_complete_delivery_with_expired_otp(self):
        delivery_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            status=OrderStatus.OUT_FOR_DELIVERY,
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
            customer_otp='654321',
        )
        OrderItem.objects.create(order=delivery_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))
        note = Notification.objects.create(
            customer=self.customer,
            order=delivery_order,
            title='Delivery status updated',
            body='Pickup confirmed and delivery is now in progress.',
            notification_type=NotificationType.RIDER,
        )
        Notification.objects.filter(pk=note.pk).update(
            created_at=timezone.now() - timezone.timedelta(minutes=16),
        )

        self.client.force_login(self.rider_user)
        response = self.client.post(
            reverse('core:rider_update_order_status', args=[delivery_order.id]),
            {'status': OrderStatus.DELIVERED, 'customer_otp': '654321'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        delivery_order.refresh_from_db()
        self.assertEqual(delivery_order.status, OrderStatus.OUT_FOR_DELIVERY)
        self.assertContains(response, 'Customer OTP expired. Resend a fresh OTP before completing delivery.')
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_rider_can_mark_delivered_and_email_customer(self):
        delivery_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            status=OrderStatus.OUT_FOR_DELIVERY,
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
            customer_otp='654321',
        )
        OrderItem.objects.create(order=delivery_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))

        self.client.force_login(self.rider_user)
        response = self.client.post(
            reverse('core:rider_update_order_status', args=[delivery_order.id]),
            {'status': OrderStatus.DELIVERED, 'customer_otp': '654321'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        delivery_order.refresh_from_db()
        self.rider.refresh_from_db()
        self.assertEqual(delivery_order.status, OrderStatus.DELIVERED)
        self.assertTrue(self.rider.is_available)
        self.assertEqual(len(mail.outbox), 2)
        combined_mail = '\n'.join(message.subject + '\n' + message.body for message in mail.outbox)
        self.assertIn('was delivered', combined_mail)
        self.assertIn('delivered successfully', combined_mail)
        self.assertIn('delivered successfully by', self.owner.notifications.filter(order=delivery_order).latest('created_at').body)

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        RAZORPAY_KEY_ID='rzp_test_123',
        RAZORPAY_KEY_SECRET='secret_123',
    )
    @patch('core.views.razorpay_api_request')
    def test_rider_can_send_cod_online_payment_link(self, mock_razorpay_api_request):
        mock_razorpay_api_request.return_value = {
            'id': 'plink_test_123',
            'short_url': 'https://rzp.io/i/cod-online-123',
            'status': 'created',
        }
        delivery_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            status=OrderStatus.OUT_FOR_DELIVERY,
            payment_method=PaymentMethod.COD,
            payment_status=PaymentStatus.PENDING,
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
            customer_otp='654321',
        )
        OrderItem.objects.create(order=delivery_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))

        self.client.force_login(self.rider_user)
        response = self.client.post(
            reverse('core:rider_request_cod_online_payment', args=[delivery_order.id]),
            {'next': reverse('core:rider_deliveries')},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        delivery_order.refresh_from_db()
        self.assertEqual(delivery_order.cod_collection_mode, CodCollectionMode.ONLINE)
        self.assertEqual(delivery_order.cod_payment_link_id, 'plink_test_123')
        self.assertEqual(delivery_order.cod_payment_link_url, 'https://rzp.io/i/cod-online-123')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('https://rzp.io/i/cod-online-123', mail.outbox[0].body)
        self.assertContains(response, 'Recieve Money Online link sent')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_rider_cannot_mark_cod_online_delivery_complete_before_payment(self):
        delivery_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            status=OrderStatus.OUT_FOR_DELIVERY,
            payment_method=PaymentMethod.COD,
            payment_status=PaymentStatus.PENDING,
            cod_collection_mode=CodCollectionMode.ONLINE,
            cod_payment_link_id='plink_test_123',
            cod_payment_link_url='https://rzp.io/i/cod-online-123',
            cod_payment_link_status='created',
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
            customer_otp='654321',
        )
        OrderItem.objects.create(order=delivery_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))

        self.client.force_login(self.rider_user)
        response = self.client.post(
            reverse('core:rider_update_order_status', args=[delivery_order.id]),
            {'status': OrderStatus.DELIVERED, 'customer_otp': '654321'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        delivery_order.refresh_from_db()
        self.assertEqual(delivery_order.status, OrderStatus.OUT_FOR_DELIVERY)
        self.assertContains(response, 'Wait for the customer Razorpay payment link to complete')

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        RAZORPAY_KEY_ID='rzp_test_123',
        RAZORPAY_KEY_SECRET='secret_123',
    )
    @patch('core.views.razorpay_api_request')
    def test_customer_cash_confirmation_creates_rider_settlement_qr(self, mock_razorpay_api_request):
        mock_razorpay_api_request.return_value = {
            'id': 'qr_test_123',
            'image_url': 'https://rzp.io/i/qr-cash-123',
            'status': 'active',
        }
        delivered_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            status=OrderStatus.DELIVERED,
            payment_method=PaymentMethod.COD,
            payment_status=PaymentStatus.PENDING,
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
            delivered_at=timezone.now(),
        )
        OrderItem.objects.create(order=delivered_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))

        self.client.force_login(self.customer_user)
        response = self.client.post(
            reverse('core:customer_confirm_cod_cash', args=[delivered_order.id]),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        delivered_order.refresh_from_db()
        self.assertEqual(delivered_order.payment_status, PaymentStatus.PAID)
        self.assertEqual(delivered_order.cod_collection_mode, CodCollectionMode.CASH)
        self.assertEqual(delivered_order.settlement_status, SettlementStatus.QR_READY)
        self.assertEqual(delivered_order.settlement_qr_id, 'qr_test_123')
        self.assertEqual(delivered_order.settlement_qr_image_url, 'https://rzp.io/i/qr-cash-123')
        self.client.force_login(self.rider_user)
        rider_completed_response = self.client.get(reverse('core:rider_completed_orders'))
        self.assertContains(rider_completed_response, 'https://rzp.io/i/qr-cash-123')
        self.assertContains(rider_completed_response, 'Open QR')

    @override_settings(RAZORPAY_WEBHOOK_SECRET='webhook_secret_123')
    def test_payment_link_webhook_marks_cod_order_paid(self):
        delivery_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            status=OrderStatus.OUT_FOR_DELIVERY,
            payment_method=PaymentMethod.COD,
            payment_status=PaymentStatus.PENDING,
            cod_collection_mode=CodCollectionMode.ONLINE,
            cod_payment_link_id='plink_test_123',
            cod_payment_link_url='https://rzp.io/i/cod-online-123',
            cod_payment_link_status='created',
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
        )
        payload = {
            'event': 'payment_link.paid',
            'payload': {
                'payment_link': {
                    'entity': {
                        'id': 'plink_test_123',
                        'status': 'paid',
                    }
                },
                'payment': {
                    'entity': {
                        'id': 'pay_test_123',
                    }
                },
            },
        }
        body = json.dumps(payload).encode('utf-8')
        signature = hmac.new(b'webhook_secret_123', body, hashlib.sha256).hexdigest()

        response = self.client.post(
            reverse('core:razorpay_webhook'),
            data=body,
            content_type='application/json',
            headers={'X-Razorpay-Signature': signature},
        )

        self.assertEqual(response.status_code, 200)
        delivery_order.refresh_from_db()
        self.assertEqual(delivery_order.payment_status, PaymentStatus.PAID)
        self.assertEqual(delivery_order.payment_reference, 'pay_test_123')
        self.assertEqual(delivery_order.cod_payment_link_status, 'paid')

    @override_settings(RAZORPAY_WEBHOOK_SECRET='webhook_secret_123')
    def test_qr_code_webhook_marks_rider_settlement_paid(self):
        delivered_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            status=OrderStatus.DELIVERED,
            payment_method=PaymentMethod.COD,
            payment_status=PaymentStatus.PAID,
            cod_collection_mode=CodCollectionMode.CASH,
            cash_confirmed_at=timezone.now(),
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
            settlement_status=SettlementStatus.QR_READY,
            settlement_qr_id='qr_test_123',
        )
        payload = {
            'event': 'qr_code.credited',
            'payload': {
                'qr_code': {
                    'entity': {
                        'id': 'qr_test_123',
                    }
                },
                'payment': {
                    'entity': {
                        'id': 'pay_settlement_123',
                    }
                },
            },
        }
        body = json.dumps(payload).encode('utf-8')
        signature = hmac.new(b'webhook_secret_123', body, hashlib.sha256).hexdigest()

        response = self.client.post(
            reverse('core:razorpay_webhook'),
            data=body,
            content_type='application/json',
            headers={'X-Razorpay-Signature': signature},
        )

        self.assertEqual(response.status_code, 200)
        delivered_order.refresh_from_db()
        self.assertEqual(delivered_order.settlement_status, SettlementStatus.PAID)
        self.assertEqual(delivered_order.settlement_payment_id, 'pay_settlement_123')

    def test_rider_completed_and_earnings_pages_render(self):
        self.client.force_login(self.rider_user)

        completed_response = self.client.get(reverse('core:rider_completed_orders'))
        earnings_response = self.client.get(reverse('core:rider_earnings'))

        self.assertEqual(completed_response.status_code, 200)
        self.assertEqual(earnings_response.status_code, 200)
        self.assertContains(completed_response, 'Completed Orders')
        self.assertContains(earnings_response, 'Commission, fixed support, and payout tracker')

    def test_rider_sees_khatabook_delivery_as_credit_order(self):
        khata_cycle = KhataBookCycle.objects.create(
            customer=self.customer,
            week_start=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=7),
            total_amount=Decimal('53.00'),
        )
        khata_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            khata_cycle=khata_cycle,
            status=OrderStatus.OUT_FOR_DELIVERY,
            payment_method=PaymentMethod.KHATABOOK,
            payment_status=PaymentStatus.PENDING,
            total_amount=Decimal('53.00'),
            delivery_fee=Decimal('15.00'),
            delivery_address='1 MG Road, Mandya 571401',
            customer_otp='555666',
            credit_due_date=khata_cycle.due_date,
        )
        OrderItem.objects.create(order=khata_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))

        self.client.force_login(self.rider_user)
        response = self.client.get(reverse('core:rider_deliveries'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'KhataBook credit order')
        self.assertContains(response, 'do not collect money')
        self.assertContains(response, khata_order.display_id)

    def test_customer_collection_request_creates_rider_khatabook_job(self):
        khata_cycle = KhataBookCycle.objects.create(
            customer=self.customer,
            week_start=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=7),
            total_amount=Decimal('53.00'),
        )
        khata_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            khata_cycle=khata_cycle,
            status=OrderStatus.DELIVERED,
            payment_method=PaymentMethod.KHATABOOK,
            payment_status=PaymentStatus.PENDING,
            total_amount=Decimal('53.00'),
            delivery_fee=Decimal('15.00'),
            delivery_address='1 MG Road, Mandya 571401',
            credit_due_date=khata_cycle.due_date,
        )
        OrderItem.objects.create(order=khata_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))

        self.client.force_login(self.customer_user)
        request_response = self.client.post(reverse('core:customer_khatabook_request_collection'), follow=True)
        self.assertEqual(request_response.status_code, 200)

        collection_request = KhataBookCollectionRequest.objects.latest('id')
        self.assertEqual(collection_request.status, KhataBookCollectionStatus.REQUESTED)

        self.client.force_login(self.rider_user)
        dashboard_response = self.client.get(reverse('core:rider_dashboard'))
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, collection_request.display_id)
        self.assertContains(dashboard_response, 'Accept KhataBook Collection')

    def test_rider_can_accept_and_complete_khatabook_collection(self):
        khata_cycle = KhataBookCycle.objects.create(
            customer=self.customer,
            week_start=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=7),
            total_amount=Decimal('53.00'),
        )
        khata_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            khata_cycle=khata_cycle,
            status=OrderStatus.DELIVERED,
            payment_method=PaymentMethod.KHATABOOK,
            payment_status=PaymentStatus.PENDING,
            total_amount=Decimal('53.00'),
            delivery_fee=Decimal('15.00'),
            delivery_address='1 MG Road, Mandya 571401',
            credit_due_date=khata_cycle.due_date,
        )
        OrderItem.objects.create(order=khata_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))
        collection_request = KhataBookCollectionRequest.objects.create(
            customer=self.customer,
            khata_cycle=khata_cycle,
            status=KhataBookCollectionStatus.REQUESTED,
            amount=Decimal('53.00'),
            collection_address='1 MG Road, Mandya 571401',
            collection_otp='112233',
            latitude=self.customer.latitude,
            longitude=self.customer.longitude,
        )

        self.client.force_login(self.rider_user)
        accept_response = self.client.post(
            reverse('core:rider_accept_khatabook_collection', args=[collection_request.id]),
            follow=True,
        )
        self.assertEqual(accept_response.status_code, 200)
        collection_request.refresh_from_db()
        self.rider.refresh_from_db()
        self.assertEqual(collection_request.status, KhataBookCollectionStatus.ACCEPTED)
        self.assertEqual(collection_request.rider, self.rider)
        self.assertEqual(len(collection_request.collection_otp), 6)
        self.assertFalse(self.rider.is_available)

        complete_response = self.client.post(
            reverse('core:rider_complete_khatabook_collection', args=[collection_request.id]),
            {'collection_otp': collection_request.collection_otp},
            follow=True,
        )
        self.assertEqual(complete_response.status_code, 200)
        collection_request.refresh_from_db()
        khata_cycle.refresh_from_db()
        khata_order.refresh_from_db()
        self.rider.refresh_from_db()
        self.assertEqual(collection_request.status, KhataBookCollectionStatus.COMPLETED)
        self.assertEqual(khata_cycle.status, KhataBookCycleStatus.PAID)
        self.assertEqual(khata_order.payment_status, PaymentStatus.PAID)
        self.assertTrue(self.rider.is_available)

    def test_rider_deliveries_self_heal_missing_khatabook_collection_otp(self):
        khata_cycle = KhataBookCycle.objects.create(
            customer=self.customer,
            week_start=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=7),
            total_amount=Decimal('53.00'),
        )
        collection_request = KhataBookCollectionRequest.objects.create(
            customer=self.customer,
            khata_cycle=khata_cycle,
            rider=self.rider,
            status=KhataBookCollectionStatus.ACCEPTED,
            amount=Decimal('53.00'),
            collection_address='1 MG Road, Mandya 571401',
            collection_otp='',
            latitude=self.customer.latitude,
            longitude=self.customer.longitude,
        )
        self.rider.is_available = False
        self.rider.save(update_fields=['is_available', 'updated_at'])

        self.client.force_login(self.rider_user)
        response = self.client.get(reverse('core:rider_deliveries'))

        self.assertEqual(response.status_code, 200)
        collection_request.refresh_from_db()
        self.assertEqual(collection_request.status, KhataBookCollectionStatus.ACCEPTED)
        self.assertEqual(len(collection_request.collection_otp), 6)
        self.assertContains(response, 'Resend KhataBook OTP')

    def test_rider_deliveries_highlight_current_mission(self):
        pickup_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            status=OrderStatus.PACKED,
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
            customer_otp='222333',
        )
        OrderItem.objects.create(order=pickup_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))
        self.client.force_login(self.rider_user)

        response = self.client.get(reverse('core:rider_deliveries'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Current mission')
        self.assertContains(response, reverse('core:support'))
        self.assertEqual(response['Cache-Control'], 'no-store, no-cache, must-revalidate, max-age=0')
        self.assertContains(response, 'Picked Up From Store')

    def test_rider_can_toggle_availability_from_shared_menu(self):
        self.client.force_login(self.rider_user)
        self.rider.is_available = False
        self.rider.save(update_fields=['is_available', 'updated_at'])

        response = self.client.post(
            reverse('core:rider_toggle_availability'),
            {'is_available': 'on', 'next': reverse('core:rider_deliveries')},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.rider.refresh_from_db()
        self.assertTrue(self.rider.is_available)
        self.assertEqual(response.request['PATH_INFO'], reverse('core:rider_deliveries'))

    def test_rider_menu_shows_availability_control(self):
        self.client.force_login(self.rider_user)

        response = self.client.get(reverse('core:rider_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Availability')
        self.assertContains(response, 'You can receive new orders')
        self.assertContains(response, reverse('core:rider_toggle_availability'))

    def test_store_can_mark_confirmed_order_packed(self):
        pack_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            status=OrderStatus.CONFIRMED,
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
        )
        OrderItem.objects.create(order=pack_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))

        self.client.force_login(self.shop_user)
        response = self.client.post(
            reverse('core:shop_update_order_status', args=[pack_order.id]),
            {'status': OrderStatus.PACKED},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        pack_order.refresh_from_db()
        self.assertEqual(pack_order.status, OrderStatus.PACKED)

    def test_store_cannot_cancel_out_for_delivery_order(self):
        transit_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            status=OrderStatus.OUT_FOR_DELIVERY,
            total_amount=Decimal('48.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
        )
        OrderItem.objects.create(order=transit_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))

        self.client.force_login(self.shop_user)
        response = self.client.post(
            reverse('core:shop_update_order_status', args=[transit_order.id]),
            {'status': OrderStatus.CANCELLED, 'cancellation_reason': 'Too late to prepare'},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        transit_order.refresh_from_db()
        self.assertEqual(transit_order.status, OrderStatus.OUT_FOR_DELIVERY)
        self.assertContains(response, 'Cannot move an order from Out For Delivery to Cancelled.')

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

    def test_cancelled_order_detail_shows_cancellation_summary(self):
        cancelled_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            status=OrderStatus.CANCELLED,
            total_amount=Decimal('50.00'),
            delivery_fee=Decimal('20.00'),
            delivery_address='1 MG Road, Mandya 571401',
            cancellation_reason='Store was offline',
            cancelled_by_role=RoleType.SHOP,
        )

        self.client.force_login(self.customer_user)
        response = self.client.get(reverse('core:order_detail', args=[cancelled_order.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Order cancelled')
        self.assertContains(response, 'Cancelled by store owner.')
        self.assertContains(response, 'Store was offline')

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

    def test_customer_can_mark_notification_read(self):
        self.client.force_login(self.customer_user)
        note = self.customer.notifications.filter(is_read=False).latest('created_at')

        response = self.client.post(reverse('core:notification_mark_read', args=[note.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        note.refresh_from_db()
        self.assertTrue(note.is_read)

    def test_customer_orders_show_last_update_and_help(self):
        self.client.force_login(self.customer_user)

        response = self.client.get(reverse('core:customer_orders'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Last update')
        self.assertContains(response, reverse('core:support'))
        self.assertEqual(response['Cache-Control'], 'no-store, no-cache, must-revalidate, max-age=0')

    def test_customer_khatabook_page_renders_weekly_due_section(self):
        cycle = KhataBookCycle.objects.create(
            customer=self.customer,
            week_start=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=7),
            total_amount=Decimal('53.00'),
        )
        khata_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            khata_cycle=cycle,
            status=OrderStatus.CONFIRMED,
            payment_method=PaymentMethod.KHATABOOK,
            payment_status=PaymentStatus.PENDING,
            total_amount=Decimal('53.00'),
            delivery_fee=Decimal('15.00'),
            delivery_address='1 MG Road, Mandya 571401',
            credit_due_date=cycle.due_date,
        )
        OrderItem.objects.create(order=khata_order, product=self.product, quantity=1, unit_price=Decimal('28.00'))

        self.client.force_login(self.customer_user)
        response = self.client.get(reverse('core:customer_khatabook'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Your weekly credit line')
        self.assertContains(response, khata_order.display_id)
        self.assertContains(response, 'Request COD / UPI Collection')

    def test_customer_dashboard_shows_khatabook_default_warning(self):
        overdue_cycle = KhataBookCycle.objects.create(
            customer=self.customer,
            week_start=timezone.localdate() - timedelta(days=7),
            due_date=timezone.localdate() - timedelta(days=1),
            total_amount=Decimal('110.00'),
        )
        overdue_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            khata_cycle=overdue_cycle,
            status=OrderStatus.DELIVERED,
            payment_method=PaymentMethod.KHATABOOK,
            payment_status=PaymentStatus.PENDING,
            total_amount=Decimal('110.00'),
            delivery_fee=Decimal('15.00'),
            delivery_address='1 MG Road, Mandya 571401',
            credit_due_date=overdue_cycle.due_date,
        )
        OrderItem.objects.create(order=overdue_order, product=self.product, quantity=1, unit_price=Decimal('85.00'))

        self.client.force_login(self.customer_user)
        response = self.client.get(reverse('core:customer_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'KhataBook default alert')
        self.assertContains(response, 'Rs. 110.00 is already overdue')
        self.assertTrue(
            Notification.objects.filter(
                customer=self.customer,
                title='KhataBook due overdue',
                notification_type=NotificationType.PAYMENT,
            ).exists()
        )

    def test_shop_khatabook_page_shows_exposure_and_defaulted_credit(self):
        open_cycle = KhataBookCycle.objects.create(
            customer=self.customer,
            week_start=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=4),
            total_amount=Decimal('70.00'),
        )
        overdue_cycle = KhataBookCycle.objects.create(
            customer=self.customer,
            week_start=timezone.localdate() - timedelta(days=7),
            due_date=timezone.localdate() - timedelta(days=1),
            total_amount=Decimal('110.00'),
        )
        open_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            rider=self.rider,
            khata_cycle=open_cycle,
            status=OrderStatus.PACKED,
            payment_method=PaymentMethod.KHATABOOK,
            payment_status=PaymentStatus.PENDING,
            total_amount=Decimal('70.00'),
            delivery_fee=Decimal('15.00'),
            delivery_address='1 MG Road, Mandya 571401',
            credit_due_date=open_cycle.due_date,
        )
        overdue_order = Order.objects.create(
            customer=self.customer,
            shop=self.shop,
            khata_cycle=overdue_cycle,
            status=OrderStatus.DELIVERED,
            payment_method=PaymentMethod.KHATABOOK,
            payment_status=PaymentStatus.PENDING,
            total_amount=Decimal('110.00'),
            delivery_fee=Decimal('15.00'),
            delivery_address='1 MG Road, Mandya 571401',
            credit_due_date=overdue_cycle.due_date,
        )
        OrderItem.objects.create(order=open_order, product=self.product, quantity=1, unit_price=Decimal('45.00'))
        OrderItem.objects.create(order=overdue_order, product=self.product, quantity=1, unit_price=Decimal('85.00'))

        self.client.force_login(self.shop_user)
        response = self.client.get(reverse('core:shop_khatabook'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Credit risk desk for Fresh Basket')
        self.assertContains(response, 'Rs. 140.00 live exposure')
        self.assertContains(response, 'Rs. 70.00')
        self.assertContains(response, 'Rs. 110.00')
        self.assertContains(response, self.rider.full_name)
        self.assertContains(response, 'Current stock left 20')
        self.assertNotContains(response, self.customer.full_name)
        self.assertTrue(
            Notification.objects.filter(
                shop_owner=self.owner,
                title='KhataBook default alert',
                notification_type=NotificationType.PAYMENT,
            ).exists()
        )

    def test_order_detail_disables_html_cache(self):
        self.client.force_login(self.customer_user)

        response = self.client.get(reverse('core:order_detail', args=[self.demo_order.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store, no-cache, must-revalidate, max-age=0')

    def test_shop_orders_show_queue_age_priority(self):
        self.client.force_login(self.shop_user)

        response = self.client.get(reverse('core:shop_orders'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Queue age')

    def test_customer_can_delete_notification(self):
        self.client.force_login(self.customer_user)
        note = Notification.objects.create(
            customer=self.customer,
            title='Temporary alert',
            body='Delete me after review.',
            notification_type=NotificationType.SYSTEM,
        )

        response = self.client.post(reverse('core:notification_delete', args=[note.id]), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Notification.objects.filter(pk=note.id).exists())

    def test_checkout_creates_typed_notifications(self):
        self.client.force_login(self.customer_user)
        self.client.post(reverse('core:cart_add', args=[self.product.id]), {'quantity': '1'})

        self.client.post(
            reverse('core:customer_checkout'),
            {'action': 'review', 'payment_method': 'cod', 'customer_notes': 'Ring the bell'},
            follow=True,
        )
        self.client.post(
            reverse('core:customer_checkout'),
            {'action': 'confirm'},
            follow=True,
        )

        order = Order.objects.latest('id')
        self.assertTrue(
            Notification.objects.filter(
                customer=self.customer,
                order=order,
                title='Order confirmed',
                notification_type=NotificationType.ORDER,
            ).exists()
        )
        self.assertTrue(
            Notification.objects.filter(
                shop_owner=self.owner,
                order=order,
                title='New order placed',
                notification_type=NotificationType.ORDER,
            ).exists()
        )

    @override_settings(RAZORPAY_KEY_ID='rzp_test_123', RAZORPAY_KEY_SECRET='secret_123')
    def test_razorpay_checkout_creates_orders_after_verified_callback(self):
        self.client.force_login(self.customer_user)
        self.client.post(reverse('core:cart_add', args=[self.product.id]), {'quantity': '2'})

        def fake_create_razorpay_order(checkout_session):
            checkout_session.razorpay_order_id = 'order_test_123'
            checkout_session.save(update_fields=['razorpay_order_id', 'updated_at'])
            return {'id': 'order_test_123'}

        with patch('core.views.create_razorpay_order_for_checkout', side_effect=fake_create_razorpay_order):
            self.client.post(
                reverse('core:customer_checkout'),
                {'action': 'review', 'payment_method': 'razorpay', 'customer_notes': 'Leave at gate'},
            )
            review_response = self.client.get(reverse('core:customer_checkout'))

        self.assertEqual(review_response.status_code, 200)
        self.assertContains(review_response, 'Pay Rs.')

        checkout_session = CheckoutSession.objects.latest('id')
        signature = hmac.new(
            b'secret_123',
            b'order_test_123|pay_test_123',
            hashlib.sha256,
        ).hexdigest()

        with patch('core.views.fetch_razorpay_payment', return_value={'id': 'pay_test_123', 'order_id': 'order_test_123', 'amount': 8100, 'status': 'captured'}), patch(
            'core.views.fetch_razorpay_order',
            return_value={'id': 'order_test_123', 'amount': 8100},
        ):
            complete_response = self.client.post(
                reverse('core:customer_razorpay_complete'),
                {
                    'checkout_session_id': checkout_session.id,
                    'razorpay_payment_id': 'pay_test_123',
                    'razorpay_order_id': 'order_test_123',
                    'razorpay_signature': signature,
                },
                follow=True,
            )

        self.assertEqual(complete_response.status_code, 200)
        self.assertContains(complete_response, 'Order placed')
        checkout_session.refresh_from_db()
        self.assertEqual(checkout_session.payment_status, PaymentStatus.PAID)
        self.assertTrue(checkout_session.is_completed)
        order = Order.objects.latest('id')
        self.assertEqual(order.payment_method, PaymentMethod.RAZORPAY)
        self.assertEqual(order.payment_status, PaymentStatus.PAID)
        self.assertEqual(order.checkout_session_id, checkout_session.id)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 18)

    @override_settings(RAZORPAY_WEBHOOK_SECRET='webhook_secret_123')
    def test_razorpay_webhook_can_finalize_paid_checkout(self):
        snapshot = {
            'item_count': 1,
            'subtotal': '28.00',
            'groups': [
                {
                    'shop_id': self.shop.id,
                    'delivery_fee': '15.00',
                    'shopkeeper_commission_fee': '5.00',
                    'platform_fee': '5.00',
                    'subtotal': '28.00',
                    'shop_credit_exposure': '33.00',
                    'total': '53.00',
                    'items': [
                        {
                            'product_id': self.product.id,
                            'product_name': self.product.name,
                            'quantity': 1,
                            'unit_price': '28.00',
                        }
                    ],
                }
            ],
        }
        checkout_session = CheckoutSession.objects.create(
            customer=self.customer,
            payment_method=PaymentMethod.RAZORPAY,
            payment_status=PaymentStatus.PENDING,
            amount=Decimal('53.00'),
            delivery_address='1 MG Road, Mandya 571401',
            customer_notes='',
            cart_snapshot=snapshot,
            cart_signature='snapshot-signature',
            receipt='grx-webhook-1',
            razorpay_order_id='order_webhook_123',
        )
        payload = {
            'event': 'order.paid',
            'payload': {
                'payment': {
                    'entity': {
                        'id': 'pay_webhook_123',
                        'order_id': 'order_webhook_123',
                    }
                }
            },
        }
        raw_body = json.dumps(payload).encode('utf-8')
        signature = hmac.new(b'webhook_secret_123', raw_body, hashlib.sha256).hexdigest()

        response = self.client.post(
            reverse('core:razorpay_webhook'),
            data=raw_body,
            content_type='application/json',
            HTTP_X_RAZORPAY_SIGNATURE=signature,
        )

        self.assertEqual(response.status_code, 200)
        checkout_session.refresh_from_db()
        self.assertEqual(checkout_session.payment_status, PaymentStatus.PAID)
        self.assertTrue(Order.objects.filter(checkout_session=checkout_session).exists())

    def test_registration_flow_sends_mobile_otp_and_creates_customer(self):
        register_payload = {
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
        response = self.client.post(reverse('core:register_details'), register_payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Verify Your Mobile Number')

        otp = AuthOtpToken.objects.filter(
            purpose=OtpPurpose.REGISTER,
            phone='9990001112',
        ).latest('created_at')
        verify_response = self.client.post(
            reverse('core:register_verify'),
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
        self.assertContains(first_response, 'Verify Sign In')
        self.assertEqual(len(mail.outbox), 1)

        otp = AuthOtpToken.objects.filter(
            purpose=OtpPurpose.LOGIN_EMAIL,
            email='ananya@example.com',
        ).latest('created_at')
        second_response = self.client.post(
            reverse('core:login_verify'),
            {'action': 'verify_login_otp', 'code': otp.code},
            follow=True,
        )
        self.assertEqual(second_response.status_code, 200)
        self.assertContains(second_response, 'Ananya')

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_passwordless_email_otp_flow_signs_user_in(self):
        request_response = self.client.post(
            reverse('core:email_otp'),
            {
                'action': 'request',
                'email': 'ananya@example.com',
            },
            follow=True,
        )
        self.assertEqual(request_response.status_code, 200)
        self.assertContains(request_response, 'We sent a 6 digit OTP to your email address.')
        self.assertEqual(len(mail.outbox), 1)

        otp = AuthOtpToken.objects.filter(
            purpose=OtpPurpose.LOGIN_EMAIL,
            email='ananya@example.com',
        ).latest('created_at')
        verify_response = self.client.post(
            reverse('core:email_otp_verify'),
            {
                'action': 'verify',
                'email': 'ananya@example.com',
                'code': otp.code,
            },
            follow=True,
        )

        self.assertEqual(verify_response.status_code, 200)
        self.assertContains(verify_response, 'Ananya')

    def test_email_otp_route_renders(self):
        response = self.client.get(reverse('core:email_otp'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Continue with Email OTP')
        self.assertContains(response, 'Step 1')
        self.assertNotContains(response, 'Step 2')
        self.assertEqual(response['Cache-Control'], 'no-store, no-cache, must-revalidate, max-age=0')

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

    def test_shop_owner_admin_save_syncs_linked_shop_status(self):
        pending_user = get_user_model().objects.create_user(
            username=f'{RoleType.SHOP}:4444444444',
            password='demo12345',
        )
        pending_owner = ShopOwnerProfile.objects.create(
            user=pending_user,
            full_name='Pending Owner Save',
            phone='4444444444',
            email='pending-save@example.com',
            approval_status=ApprovalStatus.PENDING,
        )
        pending_shop = Shop.objects.create(
            owner=pending_owner,
            name='Pending Save Store',
            shop_type='kirana',
            area='Market Road',
            address_line_1='99 Market Road',
            district='Mandya',
            pincode='571401',
            latitude=Decimal('12.915300'),
            longitude=Decimal('76.643800'),
            approval_status=ApprovalStatus.PENDING,
        )
        request = self.request_factory.post('/admin/core/shopownerprofile/')
        request.user = self.admin_user
        admin_instance = ShopOwnerProfileAdmin(ShopOwnerProfile, AdminSite())

        pending_owner.approval_status = ApprovalStatus.APPROVED
        admin_instance.save_model(request, pending_owner, form=None, change=True)

        pending_shop.refresh_from_db()
        self.assertEqual(pending_shop.approval_status, ApprovalStatus.APPROVED)

    def test_shop_dashboard_heals_owner_shop_approval_mismatch(self):
        self.client.force_login(self.shop_user)
        self.owner.approval_status = ApprovalStatus.APPROVED
        self.owner.save(update_fields=['approval_status', 'updated_at'])
        self.shop.approval_status = ApprovalStatus.PENDING
        self.shop.save(update_fields=['approval_status', 'updated_at'])

        response = self.client.get(reverse('core:shop_dashboard'))

        self.shop.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.shop.approval_status, ApprovalStatus.APPROVED)
        self.assertContains(response, 'Owner approval')
        self.assertContains(response, 'Storefront approval')
        self.assertContains(response, 'Approved')

    def test_shop_dashboard_shows_uploaded_store_photo(self):
        self.client.force_login(self.shop_user)
        self.shop.image = 'shops/storefront.jpg'
        self.shop.save(update_fields=['image', 'updated_at'])

        response = self.client.get(reverse('core:shop_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'storefront photo')
        self.assertContains(response, '/media/shops/storefront.jpg')

    def test_shop_dashboard_notifications_panel_spans_full_desktop_row(self):
        self.client.force_login(self.shop_user)

        response = self.client.get(reverse('core:shop_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'shop-dashboard-panel-wide')
        self.assertContains(response, 'shop-dashboard-notification-grid')

    def test_shop_dashboard_renders_requested_management_sections(self):
        self.client.force_login(self.shop_user)

        response = self.client.get(reverse('core:shop_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Store Status &amp; Setup Progress')
        self.assertContains(response, 'Quick Actions')
        self.assertContains(response, "Today's Summary")
        self.assertContains(response, 'Business Overview')
        self.assertContains(response, 'What Needs Attention')
        self.assertContains(response, 'KhataBook / Credit Dashboard')
        self.assertContains(response, 'Storefront Details')
        self.assertContains(response, 'Share Store Link')

    def test_shop_dashboard_exposes_store_share_link_for_signed_in_customers(self):
        self.client.force_login(self.shop_user)

        response = self.client.get(reverse('core:shop_dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('core:customer_store_detail', args=[self.shop.slug]))
        self.assertContains(response, 'Copy Store Link')
