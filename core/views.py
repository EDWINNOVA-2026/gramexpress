import json
import math
import random
import re
from collections import defaultdict
from decimal import Decimal
from functools import wraps
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Avg
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    CustomerOnboardingForm,
    CustomerOrderMetaForm,
    CustomerProfileForm,
    EmailOtpVerifyForm,
    LoginForm,
    LoginOtpVerifyForm,
    ProductForm,
    RatingForm,
    RiderLocationForm,
    RiderOnboardingForm,
    ShopOwnerOnboardingForm,
    ShopUpdateForm,
    StoreRatingForm,
    UnifiedRegistrationForm,
)
from .models import (
    ApprovalStatus,
    AuthOtpToken,
    CustomerProfile,
    EmailOtpToken,
    Notification,
    Order,
    OrderItem,
    OrderStatus,
    OtpChannel,
    OtpPurpose,
    PaymentMethod,
    PaymentStatus,
    Product,
    RiderProfile,
    RoleType,
    Shop,
    ShopOwnerProfile,
)

CART_SESSION_KEY = 'customer_cart'
PENDING_LOGIN_SESSION_KEY = 'pending_email_login'
PENDING_REGISTRATION_SESSION_KEY = 'pending_registration'
PENDING_CHECKOUT_SESSION_KEY = 'pending_checkout'
LAST_CHECKOUT_SESSION_KEY = 'last_checkout'
DEFAULT_LATITUDE = Decimal('12.915300')
DEFAULT_LONGITUDE = Decimal('76.643800')
DEFAULT_DELIVERY_RADIUS_KM = 20
ACCOUNT_ROLE_CHOICES = [RoleType.CUSTOMER, RoleType.SHOP, RoleType.RIDER]
TWILIO_API_BASE = 'https://api.twilio.com/2010-04-01/Accounts'
PHONE_SANITIZER = re.compile(r'[^\d+]')
SERIALIZABLE_REGISTRATION_FIELDS = [
    'account_type',
    'full_name',
    'phone',
    'email',
    'password1',
    'password2',
    'preferred_language',
    'address_line_1',
    'address_line_2',
    'district',
    'pincode',
    'latitude',
    'longitude',
    'shop_name',
    'shop_type',
    'area',
    'description',
    'offer',
    'age',
    'vehicle_type',
]


class CheckoutValidationError(Exception):
    pass


def normalize_phone(phone: str) -> str:
    phone = PHONE_SANITIZER.sub('', (phone or '').strip())
    if phone.startswith('++'):
        phone = phone.lstrip('+')
    return phone


def serialize_registration_data(cleaned_data: dict[str, Any]) -> dict[str, Any]:
    payload = {}
    for field_name in SERIALIZABLE_REGISTRATION_FIELDS:
        value = cleaned_data.get(field_name)
        if isinstance(value, Decimal):
            payload[field_name] = format(value, 'f')
        else:
            payload[field_name] = value
    return payload


def mask_email(email: str) -> str:
    local, _, domain = email.partition('@')
    if not domain:
        return email
    return f'{local[:2]}***@{domain}'


def find_profiles_for_identity(identity: str) -> list[tuple[str, Any]]:
    identity = (identity or '').strip()
    matches: list[tuple[str, Any]] = []
    if '@' in identity:
        profile_sets = [
            (RoleType.CUSTOMER, CustomerProfile.objects.filter(email__iexact=identity, user__isnull=False)),
            (RoleType.SHOP, ShopOwnerProfile.objects.filter(email__iexact=identity, user__isnull=False)),
            (RoleType.RIDER, RiderProfile.objects.filter(email__iexact=identity, user__isnull=False)),
        ]
    else:
        phone = normalize_phone(identity)
        profile_sets = [
            (RoleType.CUSTOMER, CustomerProfile.objects.filter(phone=phone, user__isnull=False)),
            (RoleType.SHOP, ShopOwnerProfile.objects.filter(phone=phone, user__isnull=False)),
            (RoleType.RIDER, RiderProfile.objects.filter(phone=phone, user__isnull=False)),
        ]
    for role, queryset in profile_sets:
        for profile in queryset.select_related('user'):
            matches.append((role, profile))
    return matches


def find_user_by_identity(identity: str):
    identity = (identity or '').strip()
    if not identity:
        return None, None, 'Enter your phone number or email.'

    profile_matches = find_profiles_for_identity(identity)
    if len(profile_matches) > 1:
        return None, None, 'That contact is linked to multiple roles. Use the original role account contact.'
    if profile_matches:
        role, profile = profile_matches[0]
        return profile.user, role, None

    User = get_user_model()
    admin_user = User.objects.filter(username=identity).first()
    if not admin_user and '@' in identity:
        admin_user = User.objects.filter(email__iexact=identity, is_staff=True).first()
    if admin_user:
        return admin_user, RoleType.ADMIN if admin_user.is_staff else None, None
    return None, None, 'No account matched that phone number or email.'


def contact_exists_elsewhere(*, phone: str, email: str) -> bool:
    phone = normalize_phone(phone)
    email = (email or '').strip()
    return any(
        [
            CustomerProfile.objects.filter(phone=phone).exists(),
            ShopOwnerProfile.objects.filter(phone=phone).exists(),
            RiderProfile.objects.filter(phone=phone).exists(),
            bool(email)
            and (
                CustomerProfile.objects.filter(email__iexact=email).exists()
                or ShopOwnerProfile.objects.filter(email__iexact=email).exists()
                or RiderProfile.objects.filter(email__iexact=email).exists()
            ),
        ]
    )


def create_auth_otp(
    *,
    purpose: str,
    channel: str,
    code: str | None = None,
    user=None,
    role: str = '',
    email: str = '',
    phone: str = '',
    metadata: dict[str, Any] | None = None,
):
    return AuthOtpToken.objects.create(
        user=user,
        role=role,
        purpose=purpose,
        channel=channel,
        email=email,
        phone=normalize_phone(phone),
        code=code or f'{random.randint(0, 999999):06d}',
        expires_at=timezone.now() + timezone.timedelta(minutes=getattr(settings, 'OTP_EXPIRY_MINUTES', 10)),
        metadata=metadata or {},
    )


def send_email_otp(*, email: str, code: str, subject: str, intro: str) -> tuple[bool, str]:
    try:
        send_mail(
            subject=subject,
            message=f'{intro}\n\nOTP: {code}\nThis code expires in {getattr(settings, "OTP_EXPIRY_MINUTES", 10)} minutes.',
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@gramexpress.demo'),
            recipient_list=[email],
            fail_silently=False,
        )
        return True, 'Email OTP sent successfully.'
    except Exception:
        return False, 'Email OTP could not be sent with the current mail settings.'


def send_sms_otp(*, phone: str, code: str, intro: str) -> tuple[bool, str]:
    backend = getattr(settings, 'SMS_BACKEND', 'console').lower()
    phone = normalize_phone(phone)
    message = f'{intro} OTP: {code}. Valid for {getattr(settings, "OTP_EXPIRY_MINUTES", 10)} minutes.'
    if backend == 'console':
        print(f'[GramExpress SMS OTP] {phone}: {message}')
        return True, 'Mobile OTP generated with console SMS backend.'

    if backend == 'twilio':
        account_sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
        auth_token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
        from_number = getattr(settings, 'SMS_FROM', '')
        if not all([account_sid, auth_token, from_number]):
            return False, 'Twilio SMS credentials are incomplete.'
        endpoint = f'{TWILIO_API_BASE}/{account_sid}/Messages.json'
        payload = urllib_parse.urlencode(
            {
                'To': phone,
                'From': from_number,
                'Body': message,
            }
        ).encode()
        auth_handler = urllib_request.HTTPBasicAuthHandler()
        auth_handler.add_password(
            realm=None,
            uri=endpoint,
            user=account_sid,
            passwd=auth_token,
        )
        opener = urllib_request.build_opener(auth_handler)
        request = urllib_request.Request(endpoint, data=payload)
        try:
            with opener.open(request, timeout=15):
                return True, 'Mobile OTP sent successfully.'
        except urllib_error.URLError:
            return False, 'Twilio SMS delivery failed. Check your credentials and sender number.'

    return False, f'Unsupported SMS backend "{backend}".'


def verify_google_credential(credential: str) -> tuple[dict[str, Any] | None, str | None]:
    client_id = getattr(settings, 'GOOGLE_CLIENT_ID', '')
    if not client_id:
        return None, 'Google sign-in is not configured yet.'
    url = f'https://oauth2.googleapis.com/tokeninfo?id_token={urllib_parse.quote(credential)}'
    try:
        with urllib_request.urlopen(url, timeout=15) as response:
            payload = response.read().decode()
    except urllib_error.URLError:
        return None, 'Google sign-in verification failed. Try again in a moment.'

    parsed = json.loads(payload)
    if parsed.get('aud') != client_id:
        return None, 'Google sign-in client ID does not match this app.'
    if parsed.get('email_verified') not in ['true', True]:
        return None, 'Your Google email must be verified before sign in.'
    return parsed, None


def create_account_from_registration(cleaned_data: dict[str, Any]):
    role = cleaned_data['account_type']
    phone = normalize_phone(cleaned_data['phone'])
    email = cleaned_data['email'].strip().lower()
    user = create_or_update_role_user(
        role,
        phone,
        email,
        cleaned_data['password1'],
        cleaned_data['full_name'],
    )
    if role == RoleType.CUSTOMER:
        customer, _ = CustomerProfile.objects.update_or_create(
            phone=phone,
            defaults={
                'user': user,
                'full_name': cleaned_data['full_name'],
                'email': email,
                'preferred_language': cleaned_data['preferred_language'],
                'address_line_1': cleaned_data['address_line_1'],
                'address_line_2': cleaned_data.get('address_line_2', ''),
                'district': cleaned_data['district'],
                'pincode': cleaned_data['pincode'],
                'latitude': cleaned_data['latitude'],
                'longitude': cleaned_data['longitude'],
            },
        )
        create_notification(
            customer=customer,
            title='Account ready',
            body='Your customer account is ready. Browse nearby stores and build a multi-store cart.',
        )
        return user, customer

    if role == RoleType.SHOP:
        owner, _ = ShopOwnerProfile.objects.update_or_create(
            phone=phone,
            defaults={
                'user': user,
                'full_name': cleaned_data['full_name'],
                'email': email,
                'approval_status': ApprovalStatus.PENDING,
            },
        )
        shop, _ = Shop.objects.update_or_create(
            owner=owner,
            name=cleaned_data['shop_name'],
            defaults={
                'shop_type': cleaned_data['shop_type'],
                'area': cleaned_data['area'],
                'address_line_1': cleaned_data['address_line_1'],
                'address_line_2': cleaned_data.get('address_line_2', ''),
                'district': cleaned_data['district'],
                'pincode': cleaned_data['pincode'],
                'description': cleaned_data.get('description') or 'Pending admin approval',
                'offer': cleaned_data.get('offer') or 'Fresh local delivery',
                'latitude': cleaned_data['latitude'],
                'longitude': cleaned_data['longitude'],
                'approval_status': ApprovalStatus.PENDING,
                'is_open': False,
            },
        )
        create_notification(
            shop_owner=owner,
            title='Store sent for approval',
            body=f'{shop.name} is waiting for admin approval before it goes live.',
        )
        return user, owner

    rider, _ = RiderProfile.objects.update_or_create(
        phone=phone,
        defaults={
            'user': user,
            'full_name': cleaned_data['full_name'],
            'email': email,
            'age': cleaned_data['age'],
            'vehicle_type': cleaned_data['vehicle_type'],
            'latitude': cleaned_data['latitude'],
            'longitude': cleaned_data['longitude'],
            'approval_status': ApprovalStatus.PENDING,
        },
    )
    create_notification(
        rider=rider,
        title='Rider profile submitted',
        body='Your rider account is under review. Admin approval is required before you can accept deliveries.',
    )
    return user, rider


def kilometers_between(lat1: Decimal, lng1: Decimal, lat2: Decimal, lng2: Decimal) -> float:
    earth_radius = 6371
    lat1_r = math.radians(float(lat1))
    lat2_r = math.radians(float(lat2))
    delta_lat = math.radians(float(lat2 - lat1))
    delta_lng = math.radians(float(lng2 - lng1))
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(delta_lng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(earth_radius * c, 1)


def set_distance(target: Any, source_lat: Decimal, source_lng: Decimal) -> Any:
    target.distance_km = kilometers_between(source_lat, source_lng, target.latitude, target.longitude)
    return target


def build_google_route_url(origin_lat: Decimal, origin_lng: Decimal, dest_lat: Decimal, dest_lng: Decimal) -> str:
    return (
        'https://www.google.com/maps/dir/?api=1'
        f'&origin={origin_lat},{origin_lng}&destination={dest_lat},{dest_lng}&travelmode=driving'
    )


def get_role_profile(user):
    if not user.is_authenticated:
        return None, None
    if hasattr(user, 'customer_profile'):
        return RoleType.CUSTOMER, user.customer_profile
    if hasattr(user, 'shop_owner_profile'):
        return RoleType.SHOP, user.shop_owner_profile
    if hasattr(user, 'rider_profile'):
        return RoleType.RIDER, user.rider_profile
    if user.is_staff:
        return RoleType.ADMIN, user
    return None, None


def get_dashboard_url_for_user(user) -> str:
    role, _ = get_role_profile(user)
    if role == RoleType.CUSTOMER:
        return reverse('core:customer_dashboard')
    if role == RoleType.SHOP:
        return reverse('core:shop_dashboard')
    if role == RoleType.RIDER:
        return reverse('core:rider_dashboard')
    if role == RoleType.ADMIN:
        return reverse('admin:index')
    return reverse('core:login')


def role_required(role: str):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            active_role, profile = get_role_profile(request.user)
            if active_role != role:
                messages.error(request, f'This area is only for {role} accounts.')
                return redirect('core:login')
            request.role_profile = profile
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def cart_from_session(request: HttpRequest) -> dict[str, int]:
    return request.session.get(CART_SESSION_KEY, {})


def save_cart(request: HttpRequest, cart: dict[str, int]) -> None:
    request.session[CART_SESSION_KEY] = cart
    request.session.modified = True


def build_cart_context(request: HttpRequest):
    cart = cart_from_session(request)
    product_ids = [int(product_id) for product_id in cart.keys()]
    products = Product.objects.filter(pk__in=product_ids).select_related('shop')
    product_map = {product.id: product for product in products}
    items = []
    grouped = defaultdict(list)
    subtotal = Decimal('0.00')
    validation_errors = []

    for product_id, quantity in cart.items():
        product = product_map.get(int(product_id))
        if not product or quantity <= 0:
            continue
        issues = []
        if product.shop.approval_status != ApprovalStatus.APPROVED or not product.shop.is_open:
            issues.append('This store is currently unavailable for checkout.')
        if product.stock <= 0:
            issues.append('This item is out of stock.')
        elif quantity > product.stock:
            issues.append(f'Only {product.stock} unit(s) are available right now.')
        line_total = product.price * quantity
        item = {
            'product': product,
            'quantity': quantity,
            'line_total': line_total,
            'issues': issues,
            'has_blocking_issue': bool(issues),
        }
        items.append(item)
        grouped[product.shop].append(item)
        subtotal += line_total
        validation_errors.extend(
            [f'{product.name}: {issue}' for issue in issues]
        )

    groups = []
    for shop, shop_items in grouped.items():
        groups.append(
            {
                'shop': shop,
                'items': shop_items,
                'subtotal': sum(item['line_total'] for item in shop_items),
                'has_blocking_issue': any(item['has_blocking_issue'] for item in shop_items),
            }
        )
    return {
        'items': items,
        'groups': groups,
        'item_count': sum(item['quantity'] for item in items),
        'subtotal': subtotal,
        'validation_errors': validation_errors,
        'has_blocking_issues': bool(validation_errors),
    }


def build_delivery_address(customer: CustomerProfile) -> str:
    return ', '.join(
        part
        for part in [
            customer.address_line_1,
            customer.address_line_2,
            customer.district,
            customer.pincode,
        ]
        if part
    )


def save_pending_checkout(request: HttpRequest, *, payment_method: str, customer_notes: str) -> None:
    request.session[PENDING_CHECKOUT_SESSION_KEY] = {
        'payment_method': payment_method,
        'customer_notes': customer_notes,
    }
    request.session.modified = True


def pending_checkout_data(request: HttpRequest) -> dict[str, str]:
    return request.session.get(PENDING_CHECKOUT_SESSION_KEY, {})


def clear_pending_checkout(request: HttpRequest) -> None:
    request.session.pop(PENDING_CHECKOUT_SESSION_KEY, None)


def build_checkout_context(*, customer: CustomerProfile, cart: dict[str, Any], checkout_data: dict[str, str]) -> dict[str, Any]:
    payment_method = checkout_data.get('payment_method', PaymentMethod.COD)
    customer_notes = checkout_data.get('customer_notes', '')
    totals = []
    estimated_total = Decimal('0.00')
    for group in cart['groups']:
        group_total = group['subtotal'] + Decimal('20.00')
        totals.append(
            {
                'shop': group['shop'],
                'subtotal': group['subtotal'],
                'delivery_fee': Decimal('20.00'),
                'total': group_total,
                'item_count': sum(item['quantity'] for item in group['items']),
            }
        )
        estimated_total += group_total
    return {
        'customer': customer,
        'cart': cart,
        'checkout_data': checkout_data,
        'payment_method': payment_method,
        'payment_method_label': dict(PaymentMethod.choices).get(payment_method, payment_method),
        'customer_notes': customer_notes,
        'delivery_address': build_delivery_address(customer),
        'group_totals': totals,
        'estimated_total': estimated_total,
        'estimated_eta': '40-55 min',
        'is_cod': payment_method == PaymentMethod.COD,
    }


def validate_checkout_cart(cart: dict[str, Any]) -> None:
    if not cart['items']:
        raise CheckoutValidationError('Your cart is empty. Add items before checkout.')
    if cart['has_blocking_issues']:
        raise CheckoutValidationError('Please fix the cart issues before continuing to checkout.')


def create_notification(*, customer=None, shop_owner=None, rider=None, order=None, title: str, body: str) -> None:
    Notification.objects.create(
        customer=customer,
        shop_owner=shop_owner,
        rider=rider,
        order=order,
        title=title,
        body=body,
    )


def user_notifications(user):
    queryset = notification_queryset_for_user(user)
    return queryset[:6]


def notification_queryset_for_user(user):
    role, profile = get_role_profile(user)
    if role == RoleType.CUSTOMER:
        return profile.notifications.select_related('order')
    if role == RoleType.SHOP:
        return profile.notifications.select_related('order')
    if role == RoleType.RIDER:
        return profile.notifications.select_related('order')
    return Notification.objects.none()


def group_notifications(notifications):
    today = timezone.localdate()
    grouped = {
        'Today': [],
        'Yesterday': [],
        'This Week': [],
        'Older': [],
    }
    for note in notifications:
        created_date = timezone.localtime(note.created_at).date()
        if created_date == today:
            grouped['Today'].append(note)
        elif created_date == today - timezone.timedelta(days=1):
            grouped['Yesterday'].append(note)
        elif created_date >= today - timezone.timedelta(days=7):
            grouped['This Week'].append(note)
        else:
            grouped['Older'].append(note)
    return [(label, items) for label, items in grouped.items() if items]


def notification_target_url(note: Notification) -> str:
    if note.order_id:
        return reverse('core:order_detail', args=[note.order_id])
    return reverse('core:notifications')


def get_order_for_user(user, order_id: int):
    role, profile = get_role_profile(user)
    queryset = Order.objects.select_related('customer', 'shop__owner', 'rider').prefetch_related('items__product')
    if role == RoleType.CUSTOMER:
        return get_object_or_404(queryset, pk=order_id, customer=profile)
    if role == RoleType.SHOP:
        return get_object_or_404(queryset, pk=order_id, shop__owner=profile)
    if role == RoleType.RIDER:
        return get_object_or_404(queryset, pk=order_id, rider=profile)
    if role == RoleType.ADMIN:
        return get_object_or_404(queryset, pk=order_id)
    raise Http404('Order not found')


def build_order_timeline(order: Order) -> list[dict[str, Any]]:
    events = [
        {
            'key': 'placed',
            'label': 'Order placed',
            'caption': f'{order.display_id} created successfully.',
            'completed': True,
            'current': order.status == OrderStatus.PENDING,
            'timestamp': order.created_at,
        },
        {
            'key': 'confirmed',
            'label': 'Store confirmed',
            'caption': 'Store accepted the order for preparation.',
            'completed': order.status in [OrderStatus.CONFIRMED, OrderStatus.PACKED, OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED],
            'current': order.status == OrderStatus.CONFIRMED,
            'timestamp': order.updated_at if order.status in [OrderStatus.CONFIRMED, OrderStatus.PACKED, OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED] else None,
        },
        {
            'key': 'packed',
            'label': 'Packed and ready',
            'caption': 'Store has packed the items and handed them toward dispatch.',
            'completed': order.status in [OrderStatus.PACKED, OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED],
            'current': order.status == OrderStatus.PACKED,
            'timestamp': order.updated_at if order.status in [OrderStatus.PACKED, OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED] else None,
        },
        {
            'key': 'transit',
            'label': 'Out for delivery',
            'caption': 'Rider is moving toward the customer address.',
            'completed': order.status in [OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED],
            'current': order.status == OrderStatus.OUT_FOR_DELIVERY,
            'timestamp': order.updated_at if order.status in [OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED] else None,
        },
        {
            'key': 'delivered',
            'label': 'Delivered',
            'caption': 'Order handoff completed successfully.',
            'completed': order.status == OrderStatus.DELIVERED,
            'current': order.status == OrderStatus.DELIVERED,
            'timestamp': order.delivered_at,
        },
    ]
    if order.status == OrderStatus.CANCELLED:
        for event in events:
            event['current'] = False
        events.append(
            {
                'key': 'cancelled',
                'label': 'Cancelled',
                'caption': order.cancellation_reason or 'This order was cancelled before delivery.',
                'completed': True,
                'current': True,
                'timestamp': order.updated_at,
            }
        )
    return events


def create_or_update_role_user(role: str, phone: str, email: str, password: str, full_name: str):
    User = get_user_model()
    phone = normalize_phone(phone)
    username = f'{role}:{phone}'
    user, _ = User.objects.get_or_create(
        username=username,
        defaults={
            'email': email.strip().lower(),
            'first_name': full_name,
        },
    )
    user.email = email.strip().lower()
    user.first_name = full_name
    user.set_password(password)
    user.save()
    return user


def find_role_user(role: str, identity: str):
    User = get_user_model()
    identity = identity.strip()
    if role == RoleType.ADMIN:
        return User.objects.filter(username=identity).first()

    if '@' in identity:
        if role == RoleType.CUSTOMER:
            profile = CustomerProfile.objects.filter(email__iexact=identity, user__isnull=False).first()
        elif role == RoleType.SHOP:
            profile = ShopOwnerProfile.objects.filter(email__iexact=identity, user__isnull=False).first()
        else:
            profile = RiderProfile.objects.filter(email__iexact=identity, user__isnull=False).first()
        return profile.user if profile else None
    return User.objects.filter(username=f'{role}:{normalize_phone(identity)}').first()

def nearest_available_rider(shop: Shop):
    approved_riders = RiderProfile.objects.filter(
        approval_status=ApprovalStatus.APPROVED,
        is_available=True,
    )
    rider_pool = []
    approved_count = approved_riders.count()
    for rider in approved_riders:
        rider.dispatch_radius_km = rider.max_service_radius_km if approved_count < 3 else rider.service_radius_km
        rider.pickup_distance_km = kilometers_between(rider.latitude, rider.longitude, shop.latitude, shop.longitude)
        if rider.pickup_distance_km <= rider.dispatch_radius_km:
            rider_pool.append(rider)
    rider_pool.sort(key=lambda candidate: (candidate.pickup_distance_km, candidate.full_name))
    return rider_pool[0] if rider_pool else None


def refresh_ratings():
    for shop in Shop.objects.all():
        rating = shop.orders.filter(customer_rating__isnull=False).aggregate(avg=Avg('customer_rating'))['avg']
        if rating:
            shop.rating = round(Decimal(str(rating)), 1)
            shop.save(update_fields=['rating'])
    for rider in RiderProfile.objects.all():
        rating = rider.orders.filter(store_rating__isnull=False).aggregate(avg=Avg('store_rating'))['avg']
        if rating:
            rider.rating = round(Decimal(str(rating)), 1)
            rider.save(update_fields=['rating'])


def home(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_for_user(request.user))
    return redirect('core:login')


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_for_user(request.user))
    pending_login = request.session.get(PENDING_LOGIN_SESSION_KEY, {})
    login_form = LoginForm(
        initial={
            'identity': request.GET.get('email')
            or request.GET.get('identity')
            or pending_login.get('email', '')
        }
    )
    otp_form = LoginOtpVerifyForm()

    if request.method == 'POST':
        action = request.POST.get('action', 'login')
        if action == 'login':
            login_form = LoginForm(request.POST)
            if login_form.is_valid():
                identity = login_form.cleaned_data['identity'].strip()
                password = login_form.cleaned_data['password']
                user, role, error = find_user_by_identity(identity)
                if error:
                    login_form.add_error('identity', error)
                else:
                    authenticated = authenticate(
                        request,
                        username=user.username if user else '',
                        password=password,
                    )
                    if not authenticated:
                        login_form.add_error('password', 'Your password is not correct for this account.')
                    elif '@' in identity and role != RoleType.ADMIN:
                        email = authenticated.email.strip().lower()
                        token = create_auth_otp(
                            purpose=OtpPurpose.LOGIN_EMAIL,
                            channel=OtpChannel.EMAIL,
                            user=authenticated,
                            role=role or '',
                            email=email,
                        )
                        delivered, detail = send_email_otp(
                            email=email,
                            code=token.code,
                            subject='Your GramExpress sign-in OTP',
                            intro='Use this OTP to finish signing in to GramExpress.',
                        )
                        if delivered:
                            request.session[PENDING_LOGIN_SESSION_KEY] = {
                                'user_id': authenticated.id,
                                'email': email,
                            }
                            request.session.modified = True
                            messages.success(request, 'We sent a 6 digit OTP to your email address.')
                        else:
                            token.delete()
                            messages.error(request, detail)
                    else:
                        request.session.pop(PENDING_LOGIN_SESSION_KEY, None)
                        login(request, authenticated)
                        messages.success(request, 'Signed in successfully.')
                        return redirect(get_dashboard_url_for_user(authenticated))
        elif action in ['verify_login_otp', 'resend_login_otp']:
            pending_login = request.session.get(PENDING_LOGIN_SESSION_KEY)
            if not pending_login:
                messages.error(request, 'Your email sign-in session expired. Please enter your details again.')
                return redirect('core:login')
            user = get_user_model().objects.filter(pk=pending_login.get('user_id')).first()
            if not user:
                request.session.pop(PENDING_LOGIN_SESSION_KEY, None)
                messages.error(request, 'That email login session is no longer valid.')
                return redirect('core:login')

            if action == 'resend_login_otp':
                token = create_auth_otp(
                    purpose=OtpPurpose.LOGIN_EMAIL,
                    channel=OtpChannel.EMAIL,
                    user=user,
                    role=get_role_profile(user)[0] or '',
                    email=pending_login['email'],
                )
                delivered, detail = send_email_otp(
                    email=pending_login['email'],
                    code=token.code,
                    subject='Your GramExpress sign-in OTP',
                    intro='Use this OTP to finish signing in to GramExpress.',
                )
                if delivered:
                    messages.success(request, 'A fresh OTP was sent to your email.')
                else:
                    token.delete()
                    messages.error(request, detail)
            else:
                otp_form = LoginOtpVerifyForm(request.POST)
                if otp_form.is_valid():
                    token = (
                        AuthOtpToken.objects.filter(
                            user=user,
                            purpose=OtpPurpose.LOGIN_EMAIL,
                            channel=OtpChannel.EMAIL,
                            email__iexact=pending_login['email'],
                            code=otp_form.cleaned_data['code'],
                            is_used=False,
                        )
                        .order_by('-created_at')
                        .first()
                    )
                    if token and token.is_valid:
                        token.is_used = True
                        token.save(update_fields=['is_used'])
                        request.session.pop(PENDING_LOGIN_SESSION_KEY, None)
                        login(request, user)
                        messages.success(request, 'Email verification completed. Welcome back.')
                        return redirect(get_dashboard_url_for_user(user))
                    otp_form.add_error('code', 'That OTP is invalid or expired.')

    pending_login = request.session.get(PENDING_LOGIN_SESSION_KEY, {})
    return render(
        request,
        'core/login.html',
        {
            'form': login_form,
            'otp_form': otp_form,
            'pending_login': pending_login,
            'pending_login_masked_email': mask_email(pending_login['email']) if pending_login else '',
            'google_client_id': getattr(settings, 'GOOGLE_CLIENT_ID', ''),
        },
    )


@require_POST
def google_auth_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_for_user(request.user))

    credential = request.POST.get('credential', '').strip()
    if not credential:
        messages.error(request, 'Google sign-in did not return a credential.')
        return redirect('core:login')

    google_payload, error = verify_google_credential(credential)
    if error:
        messages.error(request, error)
        return redirect('core:login')

    email = google_payload.get('email', '').strip().lower()
    user, _, lookup_error = find_user_by_identity(email)
    if lookup_error or not user:
        params = urllib_parse.urlencode(
            {
                'email': email,
                'full_name': google_payload.get('name', ''),
            }
        )
        messages.info(request, 'Choose your role and finish registration to use Google sign-in with this email.')
        return redirect(f'{reverse("core:register")}?{params}')

    login(request, user)
    messages.success(request, 'Signed in with Google successfully.')
    return redirect(get_dashboard_url_for_user(user))


def register_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_for_user(request.user))
    pending_registration = request.session.get(PENDING_REGISTRATION_SESSION_KEY, {})
    initial_data = pending_registration or {
        'account_type': request.GET.get('account_type', RoleType.CUSTOMER),
        'full_name': request.GET.get('full_name', ''),
        'email': request.GET.get('email', ''),
        'latitude': DEFAULT_LATITUDE,
        'longitude': DEFAULT_LONGITUDE,
    }
    form = UnifiedRegistrationForm(initial=initial_data)
    otp_form = LoginOtpVerifyForm()

    if request.method == 'POST':
        action = request.POST.get('action', 'register')
        if action == 'register':
            form = UnifiedRegistrationForm(request.POST)
            if form.is_valid():
                cleaned_data = form.cleaned_data.copy()
                cleaned_data['phone'] = normalize_phone(cleaned_data['phone'])
                cleaned_data['email'] = cleaned_data['email'].strip().lower()
                if contact_exists_elsewhere(phone=cleaned_data['phone'], email=cleaned_data['email']):
                    form.add_error(None, 'That phone number or email is already linked to an existing account.')
                else:
                    payload = serialize_registration_data(cleaned_data)
                    token = create_auth_otp(
                        purpose=OtpPurpose.REGISTER,
                        channel=OtpChannel.SMS,
                        role=payload['account_type'],
                        phone=payload['phone'],
                        metadata={'full_name': payload['full_name']},
                    )
                    delivered, detail = send_sms_otp(
                        phone=payload['phone'],
                        code=token.code,
                        intro='Your GramExpress registration code is',
                    )
                    if delivered:
                        request.session[PENDING_REGISTRATION_SESSION_KEY] = payload
                        request.session.modified = True
                        messages.success(request, 'We sent a mobile OTP to verify your registration.')
                    else:
                        token.delete()
                        form.add_error(None, detail)
        elif action in ['verify_register_otp', 'resend_register_otp']:
            pending_registration = request.session.get(PENDING_REGISTRATION_SESSION_KEY)
            if not pending_registration:
                messages.error(request, 'Your registration session expired. Please fill the form again.')
                return redirect('core:register')

            form = UnifiedRegistrationForm(initial=pending_registration)
            if action == 'resend_register_otp':
                token = create_auth_otp(
                    purpose=OtpPurpose.REGISTER,
                    channel=OtpChannel.SMS,
                    role=pending_registration['account_type'],
                    phone=pending_registration['phone'],
                    metadata={'full_name': pending_registration['full_name']},
                )
                delivered, detail = send_sms_otp(
                    phone=pending_registration['phone'],
                    code=token.code,
                    intro='Your GramExpress registration code is',
                )
                if delivered:
                    messages.success(request, 'A fresh mobile OTP was sent.')
                else:
                    token.delete()
                    messages.error(request, detail)
            else:
                otp_form = LoginOtpVerifyForm(request.POST)
                if otp_form.is_valid():
                    token = (
                        AuthOtpToken.objects.filter(
                            purpose=OtpPurpose.REGISTER,
                            channel=OtpChannel.SMS,
                            role=pending_registration['account_type'],
                            phone=normalize_phone(pending_registration['phone']),
                            code=otp_form.cleaned_data['code'],
                            is_used=False,
                        )
                        .order_by('-created_at')
                        .first()
                    )
                    if token and token.is_valid:
                        token.is_used = True
                        token.save(update_fields=['is_used'])
                        normalized_data = pending_registration.copy()
                        if normalized_data.get('latitude'):
                            normalized_data['latitude'] = Decimal(normalized_data['latitude'])
                        if normalized_data.get('longitude'):
                            normalized_data['longitude'] = Decimal(normalized_data['longitude'])
                        if normalized_data.get('age') not in [None, '']:
                            normalized_data['age'] = int(normalized_data['age'])
                        user, _ = create_account_from_registration(normalized_data)
                        request.session.pop(PENDING_REGISTRATION_SESSION_KEY, None)
                        login(request, user)
                        messages.success(request, 'Your account is ready and your mobile number is verified.')
                        return redirect(get_dashboard_url_for_user(user))
                    otp_form.add_error('code', 'That OTP is invalid or expired.')

    pending_registration = request.session.get(PENDING_REGISTRATION_SESSION_KEY, {})
    return render(
        request,
        'core/register.html',
        {
            'form': form,
            'otp_form': otp_form,
            'pending_registration': pending_registration,
            'pending_registration_phone': pending_registration.get('phone', ''),
            'google_client_id': getattr(settings, 'GOOGLE_CLIENT_ID', ''),
        },
    )


def email_otp_view(request: HttpRequest) -> HttpResponse:
    messages.info(request, 'Email OTP is now built into the main sign-in screen. Enter your email there to continue.')
    return redirect('core:login')


def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    request.session.pop(CART_SESSION_KEY, None)
    request.session.pop(PENDING_LOGIN_SESSION_KEY, None)
    request.session.pop(PENDING_REGISTRATION_SESSION_KEY, None)
    messages.success(request, 'Signed out successfully.')
    return redirect('core:login')


@login_required
def notifications_view(request: HttpRequest) -> HttpResponse:
    notifications = list(notification_queryset_for_user(request.user))
    grouped_notifications = group_notifications(notifications)
    return render(
        request,
        'core/notifications.html',
        {
            'grouped_notifications': grouped_notifications,
        },
    )


@login_required
@require_POST
def notifications_mark_all_read(request: HttpRequest) -> HttpResponse:
    notification_queryset_for_user(request.user).filter(is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('core:notifications')


@login_required
def notification_open(request: HttpRequest, notification_id: int) -> HttpResponse:
    note = get_object_or_404(notification_queryset_for_user(request.user), pk=notification_id)
    if not note.is_read:
        note.is_read = True
        note.save(update_fields=['is_read'])
    return redirect(notification_target_url(note))


@login_required
def order_detail_view(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_order_for_user(request.user, order_id)
    order.subtotal_amount = order.total_amount - order.delivery_fee
    related_notifications = order.notifications.order_by('-created_at')[:6]
    timeline = build_order_timeline(order)
    if order.rider:
        order.rider_route_url = build_google_route_url(
            order.shop.latitude,
            order.shop.longitude,
            order.customer.latitude,
            order.customer.longitude,
        )
    return render(
        request,
        'core/order_detail.html',
        {
            'order': order,
            'timeline': timeline,
            'related_notifications': related_notifications,
            'show_customer_actions': get_role_profile(request.user)[0] == RoleType.CUSTOMER,
        },
    )


@login_required
def order_tracking_view(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_order_for_user(request.user, order_id)
    order.subtotal_amount = order.total_amount - order.delivery_fee
    timeline = build_order_timeline(order)
    eta_label = '40-55 min' if order.status != OrderStatus.DELIVERED else 'Delivered'
    route_url = build_google_route_url(
        order.shop.latitude,
        order.shop.longitude,
        order.customer.latitude,
        order.customer.longitude,
    )
    return render(
        request,
        'core/order_tracking.html',
        {
            'order': order,
            'timeline': timeline,
            'eta_label': eta_label,
            'route_url': route_url,
        },
    )


def customer_start(request: HttpRequest) -> HttpResponse:
    return redirect(f'{reverse("core:register")}?account_type={RoleType.CUSTOMER}')


def shop_start(request: HttpRequest) -> HttpResponse:
    return redirect(f'{reverse("core:register")}?account_type={RoleType.SHOP}')


def rider_start(request: HttpRequest) -> HttpResponse:
    return redirect(f'{reverse("core:register")}?account_type={RoleType.RIDER}')

@role_required(RoleType.CUSTOMER)
def customer_dashboard(request: HttpRequest) -> HttpResponse:
    customer = request.role_profile
    if request.method == 'POST' and request.POST.get('action') == 'update_profile':
        profile_form = CustomerProfileForm(request.POST, instance=customer)
        if profile_form.is_valid():
            updated_customer = profile_form.save()
            if updated_customer.user:
                updated_customer.user.first_name = updated_customer.full_name
                updated_customer.user.email = updated_customer.email
                updated_customer.user.save(update_fields=['first_name', 'email'])
            messages.success(request, 'Your customer profile was updated.')
            return redirect('core:customer_dashboard')
    else:
        profile_form = CustomerProfileForm(instance=customer)

    approved_shops = list(
        Shop.objects.filter(approval_status=ApprovalStatus.APPROVED, is_open=True)
        .select_related('owner')
        .prefetch_related('products')
    )
    nearby_shops = []
    for shop in approved_shops:
        set_distance(shop, customer.latitude, customer.longitude)
        if shop.distance_km <= DEFAULT_DELIVERY_RADIUS_KM:
            nearby_shops.append(shop)
    nearby_shops.sort(key=lambda shop: (shop.distance_km, -float(shop.rating), shop.name))
    shops = nearby_shops or approved_shops

    selected_shop = None
    if request.GET.get('shop'):
        selected_shop = next((shop for shop in shops if shop.slug == request.GET['shop']), None)
    elif shops:
        selected_shop = shops[0]

    cart = build_cart_context(request)
    orders = (
        customer.orders.select_related('shop', 'rider')
        .prefetch_related('items__product')
        .all()
    )
    for order in orders:
        if order.rider:
            order.rider_route_url = build_google_route_url(
                order.shop.latitude,
                order.shop.longitude,
                order.rider.latitude,
                order.rider.longitude,
            )

    context = {
        'customer': customer,
        'shops': shops,
        'selected_shop': selected_shop,
        'orders': orders,
        'profile_form': profile_form,
        'order_form': CustomerOrderMetaForm(initial={'payment_method': PaymentMethod.COD}),
        'rating_form': RatingForm(),
        'cart': cart,
        'notifications': user_notifications(request.user),
        'google_maps_embed_api_key': getattr(settings, 'GOOGLE_MAPS_EMBED_API_KEY', ''),
        'delivery_radius_km': DEFAULT_DELIVERY_RADIUS_KM,
        'active_order_count': sum(
            1 for order in orders if order.status not in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]
        ),
        'delivered_order_count': sum(1 for order in orders if order.status == OrderStatus.DELIVERED),
        'dashboard_role': RoleType.CUSTOMER,
    }
    return render(request, 'core/customer_dashboard.html', context)


@role_required(RoleType.CUSTOMER)
@require_POST
def cart_add(request: HttpRequest, product_id: int) -> HttpResponse:
    product = get_object_or_404(Product.objects.select_related('shop'), pk=product_id, shop__approval_status=ApprovalStatus.APPROVED)
    if not product.shop.is_open:
        messages.error(request, f'{product.shop.name} is currently closed for checkout.')
        return redirect(f"{reverse('core:customer_dashboard')}?shop={product.shop.slug}")
    if product.stock <= 0:
        messages.error(request, f'{product.name} is currently out of stock.')
        return redirect(f"{reverse('core:customer_dashboard')}?shop={product.shop.slug}")
    quantity = max(1, int(request.POST.get('quantity', 1)))
    cart = cart_from_session(request)
    cart[str(product.id)] = min(product.stock, cart.get(str(product.id), 0) + quantity)
    save_cart(request, cart)
    if quantity > product.stock:
        messages.info(request, f'{product.name} was capped to the available stock of {product.stock}.')
    else:
        messages.success(request, f'{product.name} added to your cart.')
    return redirect(f"{reverse('core:customer_dashboard')}?shop={product.shop.slug}")


@role_required(RoleType.CUSTOMER)
@require_POST
def cart_update(request: HttpRequest, product_id: int) -> HttpResponse:
    cart = cart_from_session(request)
    quantity = max(0, int(request.POST.get('quantity', 0)))
    key = str(product_id)
    if quantity == 0:
        cart.pop(key, None)
    else:
        product = Product.objects.filter(pk=product_id).first()
        if not product:
            cart.pop(key, None)
            messages.error(request, 'That product is no longer available.')
        else:
            cart[key] = min(quantity, product.stock)
            if quantity > product.stock:
                messages.info(request, f'{product.name} was reduced to the available stock of {product.stock}.')
    save_cart(request, cart)
    messages.success(request, 'Cart updated.')
    return redirect('core:customer_dashboard')


@role_required(RoleType.CUSTOMER)
@require_POST
def cart_clear(request: HttpRequest) -> HttpResponse:
    save_cart(request, {})
    messages.success(request, 'Cart cleared.')
    return redirect('core:customer_dashboard')


@role_required(RoleType.CUSTOMER)
def customer_checkout(request: HttpRequest) -> HttpResponse:
    customer = request.role_profile
    cart = build_cart_context(request)
    try:
        validate_checkout_cart(cart)
    except CheckoutValidationError as error:
        messages.error(request, str(error))
        return redirect('core:customer_dashboard')
    if request.method == 'POST':
        action = request.POST.get('action', 'review')
        if action == 'review':
            form = CustomerOrderMetaForm(request.POST)
            if form.is_valid():
                save_pending_checkout(
                    request,
                    payment_method=form.cleaned_data['payment_method'],
                    customer_notes=form.cleaned_data['customer_notes'],
                )
            else:
                messages.error(request, 'Choose a valid payment method before checkout.')
                return redirect('core:customer_dashboard')
        elif action == 'confirm':
            checkout_data = pending_checkout_data(request)
            if not checkout_data:
                messages.error(request, 'Your checkout session expired. Please review the cart again.')
                return redirect('core:customer_dashboard')

            created_orders = []
            try:
                with transaction.atomic():
                    for group in cart['groups']:
                        locked_items = []
                        for item in group['items']:
                            locked_product = Product.objects.select_for_update().select_related('shop').get(pk=item['product'].pk)
                            if locked_product.shop.approval_status != ApprovalStatus.APPROVED or not locked_product.shop.is_open:
                                raise CheckoutValidationError(f'{locked_product.name} is no longer available because the store is offline.')
                            if locked_product.stock < item['quantity']:
                                raise CheckoutValidationError(
                                    f'{locked_product.name} only has {locked_product.stock} unit(s) left. Update your cart and try again.'
                                )
                            locked_items.append((locked_product, item['quantity']))

                        rider = nearest_available_rider(group['shop'])
                        payment_method = checkout_data['payment_method']
                        order = Order.objects.create(
                            customer=customer,
                            shop=group['shop'],
                            rider=rider,
                            status=OrderStatus.CONFIRMED,
                            payment_method=payment_method,
                            payment_status=PaymentStatus.PAID if payment_method == PaymentMethod.RAZORPAY else PaymentStatus.PENDING,
                            delivery_address=build_delivery_address(customer),
                            customer_notes=checkout_data.get('customer_notes', ''),
                            total_amount=group['subtotal'] + Decimal('20.00'),
                        )
                        for locked_product, quantity in locked_items:
                            OrderItem.objects.create(
                                order=order,
                                product=locked_product,
                                quantity=quantity,
                                unit_price=locked_product.price,
                            )
                            locked_product.stock -= quantity
                            locked_product.save(update_fields=['stock', 'updated_at'])
                        created_orders.append(order)
                        create_notification(
                            shop_owner=group['shop'].owner,
                            order=order,
                            title='New order placed',
                            body=f'Order #{order.id} is waiting for packaging at {group["shop"].name}.',
                        )
                        create_notification(
                            customer=customer,
                            order=order,
                            title='Order confirmed',
                            body=f'Order #{order.id} from {group["shop"].name} was created successfully.',
                        )
                        if rider:
                            rider.is_available = False
                            rider.save(update_fields=['is_available', 'updated_at'])
                            create_notification(
                                rider=rider,
                                order=order,
                                title='New delivery request',
                                body=f'Order #{order.id} is ready around {group["shop"].area}.',
                            )
            except CheckoutValidationError as error:
                messages.error(request, str(error))
                refreshed_cart = build_cart_context(request)
                context = build_checkout_context(customer=customer, cart=refreshed_cart, checkout_data=checkout_data)
                context['order_form'] = CustomerOrderMetaForm(initial=checkout_data)
                return render(request, 'core/checkout_review.html', context)

            save_cart(request, {})
            request.session[LAST_CHECKOUT_SESSION_KEY] = {
                'order_ids': [order.id for order in created_orders],
                'payment_method': checkout_data['payment_method'],
                'estimated_total': format(sum(order.total_amount for order in created_orders), 'f'),
            }
            clear_pending_checkout(request)
            messages.success(request, f'{len(created_orders)} order(s) placed across your selected stores.')
            return redirect('core:customer_checkout_success')
    checkout_data = pending_checkout_data(request)
    if not checkout_data:
        checkout_data = {
            'payment_method': PaymentMethod.COD,
            'customer_notes': '',
        }

    context = build_checkout_context(customer=customer, cart=cart, checkout_data=checkout_data)
    context['order_form'] = CustomerOrderMetaForm(initial=checkout_data)
    return render(request, 'core/checkout_review.html', context)


@role_required(RoleType.CUSTOMER)
def customer_checkout_success(request: HttpRequest) -> HttpResponse:
    payload = request.session.get(LAST_CHECKOUT_SESSION_KEY)
    if not payload:
        messages.info(request, 'Place an order first to view the checkout success screen.')
        return redirect('core:customer_dashboard')

    orders = list(
        request.role_profile.orders.filter(pk__in=payload.get('order_ids', []))
        .select_related('shop', 'rider')
        .order_by('-created_at')
    )
    return render(
        request,
        'core/checkout_success.html',
        {
            'orders': orders,
            'payment_method': payload.get('payment_method', PaymentMethod.COD),
            'payment_method_label': dict(PaymentMethod.choices).get(
                payload.get('payment_method', PaymentMethod.COD),
                payload.get('payment_method', PaymentMethod.COD),
            ),
            'estimated_total': Decimal(payload.get('estimated_total', '0.00')),
            'primary_order': orders[0] if orders else None,
            'estimated_eta': '40-55 min',
        },
    )


@role_required(RoleType.CUSTOMER)
@require_POST
def customer_rate_order(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(Order, pk=order_id, customer=request.role_profile)
    form = RatingForm(request.POST, instance=order)
    if form.is_valid() and order.can_be_rated_by_customer:
        form.save()
        refresh_ratings()
        create_notification(
            shop_owner=order.shop.owner,
            order=order,
            title='New customer rating',
            body=f'Order #{order.id} received a {order.customer_rating}/5 rating.',
        )
        if order.rider:
            create_notification(
                rider=order.rider,
                order=order,
                title='Delivery completed and rated',
                body=f'Customer rated order #{order.id} with {order.customer_rating}/5.',
            )
        messages.success(request, 'Thanks for rating your order.')
    else:
        messages.error(request, 'This order cannot be rated right now.')
    return redirect('core:customer_dashboard')


@role_required(RoleType.CUSTOMER)
@require_POST
def customer_cancel_order(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(Order.objects.select_related('shop__owner', 'rider'), pk=order_id, customer=request.role_profile)
    if not order.can_be_cancelled_by_customer:
        messages.error(request, 'This order can no longer be cancelled from the customer side.')
        return redirect('core:order_detail', order_id=order.id)

    cancellation_reason = request.POST.get('cancellation_reason', '').strip() or 'Cancelled by the customer before dispatch.'
    with transaction.atomic():
        locked_order = Order.objects.select_for_update().select_related('rider', 'shop__owner').get(pk=order.pk)
        if not locked_order.can_be_cancelled_by_customer:
            messages.error(request, 'This order changed status and can no longer be cancelled.')
            return redirect('core:order_detail', order_id=locked_order.id)
        locked_order.status = OrderStatus.CANCELLED
        locked_order.cancellation_reason = cancellation_reason
        locked_order.cancelled_by_role = RoleType.CUSTOMER
        locked_order.save(update_fields=['status', 'cancellation_reason', 'cancelled_by_role', 'updated_at'])
        for item in locked_order.items.select_related('product'):
            product = Product.objects.select_for_update().get(pk=item.product_id)
            product.stock += item.quantity
            product.save(update_fields=['stock', 'updated_at'])
        if locked_order.rider:
            locked_order.rider.is_available = True
            locked_order.rider.save(update_fields=['is_available', 'updated_at'])
            create_notification(
                rider=locked_order.rider,
                order=locked_order,
                title='Order cancelled',
                body=f'{locked_order.display_id} was cancelled by the customer.',
            )
        create_notification(
            shop_owner=locked_order.shop.owner,
            order=locked_order,
            title='Customer cancelled order',
            body=f'{locked_order.display_id} was cancelled. Reason: {cancellation_reason}',
        )
        create_notification(
            customer=request.role_profile,
            order=locked_order,
            title='Order cancelled',
            body=f'{locked_order.display_id} was cancelled successfully.',
        )

    messages.success(request, 'Your order was cancelled successfully.')
    return redirect('core:order_detail', order_id=order.id)


@role_required(RoleType.CUSTOMER)
@require_POST
def customer_reorder(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(
        Order.objects.select_related('shop').prefetch_related('items__product'),
        pk=order_id,
        customer=request.role_profile,
    )
    cart = cart_from_session(request)
    added_count = 0
    skipped = []
    for item in order.items.all():
        product = item.product
        if product.shop.approval_status != ApprovalStatus.APPROVED or not product.shop.is_open:
            skipped.append(f'{product.name} is unavailable because the store is offline.')
            continue
        if product.stock <= 0:
            skipped.append(f'{product.name} is out of stock.')
            continue
        quantity_to_add = min(item.quantity, product.stock)
        cart[str(product.id)] = min(product.stock, cart.get(str(product.id), 0) + quantity_to_add)
        added_count += quantity_to_add
        if quantity_to_add < item.quantity:
            skipped.append(f'{product.name} was added with reduced quantity because stock is limited.')
    save_cart(request, cart)
    if added_count:
        messages.success(request, f'{added_count} item(s) were added back to your cart.')
    if skipped:
        messages.info(request, ' '.join(skipped))
    return redirect('core:customer_dashboard')


@role_required(RoleType.SHOP)
def shop_dashboard(request: HttpRequest) -> HttpResponse:
    owner = request.role_profile
    shop = get_object_or_404(
        Shop.objects.select_related('owner').prefetch_related('products', 'orders__customer', 'orders__rider', 'orders__items__product'),
        owner=owner,
    )
    editing_product = None
    if request.GET.get('edit_product'):
        editing_product = get_object_or_404(Product, pk=request.GET['edit_product'], shop=shop)

    if request.method == 'POST':
        if request.POST.get('action') == 'update_shop':
            shop_form = ShopUpdateForm(request.POST, request.FILES, instance=shop)
            product_form = ProductForm(instance=editing_product)
            if shop_form.is_valid():
                updated_shop = shop_form.save(commit=False)
                if updated_shop.approval_status != ApprovalStatus.APPROVED:
                    updated_shop.approval_status = ApprovalStatus.PENDING
                    updated_shop.is_open = False
                updated_shop.save()
                create_notification(
                    shop_owner=owner,
                    title='Store profile updated',
                    body='Your store details changed and may need a fresh approval review.',
                )
                messages.success(request, 'Shop details updated.')
                return redirect('core:shop_dashboard')
        else:
            target_product = editing_product if request.POST.get('product_id') else None
            product_form = ProductForm(request.POST, instance=target_product)
            shop_form = ShopUpdateForm(instance=shop)
            if product_form.is_valid():
                product = product_form.save(commit=False)
                product.shop = shop
                product.save()
                messages.success(request, 'Product saved successfully.')
                return redirect('core:shop_dashboard')
    else:
        shop_form = ShopUpdateForm(instance=shop)
        product_form = ProductForm(instance=editing_product)

    orders = shop.orders.all()
    for order in orders:
        if order.rider:
            order.rider_tracking_url = order.rider.google_maps_url
    context = {
        'shop': shop,
        'shop_form': shop_form,
        'product_form': product_form,
        'orders': orders,
        'editing_product': editing_product,
        'store_rating_form': StoreRatingForm(),
        'notifications': user_notifications(request.user),
        'live_product_count': shop.products.count(),
        'active_order_count': sum(
            1 for order in orders if order.status not in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]
        ),
        'delivered_order_count': sum(1 for order in orders if order.status == OrderStatus.DELIVERED),
        'dashboard_role': RoleType.SHOP,
    }
    return render(request, 'core/shop_dashboard.html', context)


@role_required(RoleType.SHOP)
@require_POST
def shop_delete_product(request: HttpRequest, product_id: int) -> HttpResponse:
    product = get_object_or_404(Product, pk=product_id, shop__owner=request.role_profile)
    product.delete()
    messages.success(request, 'Product deleted.')
    return redirect('core:shop_dashboard')


@role_required(RoleType.SHOP)
@require_POST
def shop_update_order_status(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(Order, pk=order_id, shop__owner=request.role_profile)
    next_status = request.POST.get('status')
    cancellation_reason = request.POST.get('cancellation_reason', '').strip()
    allowed = {OrderStatus.CONFIRMED, OrderStatus.PACKED, OrderStatus.CANCELLED}
    if next_status in allowed:
        with transaction.atomic():
            locked_order = Order.objects.select_for_update().select_related('rider', 'customer', 'shop__owner').get(pk=order.pk)
            locked_order.status = next_status
            update_fields = ['status', 'updated_at']
            if next_status == OrderStatus.CANCELLED:
                locked_order.cancellation_reason = cancellation_reason or 'Cancelled by the store before dispatch.'
                locked_order.cancelled_by_role = RoleType.SHOP
                update_fields.extend(['cancellation_reason', 'cancelled_by_role'])
                for item in locked_order.items.select_related('product'):
                    product = Product.objects.select_for_update().get(pk=item.product_id)
                    product.stock += item.quantity
                    product.save(update_fields=['stock', 'updated_at'])
                if locked_order.rider:
                    locked_order.rider.is_available = True
                    locked_order.rider.save(update_fields=['is_available', 'updated_at'])
            locked_order.save(update_fields=update_fields)
        create_notification(
            customer=locked_order.customer,
            order=locked_order,
            title='Store updated your order',
            body=(
                f'{locked_order.display_id} is now {locked_order.get_status_display().lower()}.'
                if next_status != OrderStatus.CANCELLED
                else f'{locked_order.display_id} was cancelled by the store. Reason: {locked_order.cancellation_reason}'
            ),
        )
        if locked_order.rider:
            create_notification(
                rider=locked_order.rider,
                order=locked_order,
                title='Store status changed',
                body=(
                    f'{locked_order.display_id} is now {locked_order.get_status_display().lower()}.'
                    if next_status != OrderStatus.CANCELLED
                    else f'{locked_order.display_id} was cancelled by the store.'
                ),
            )
        messages.success(request, f'Order #{locked_order.id} moved to {locked_order.get_status_display()}.')
    else:
        messages.error(request, 'Invalid order status transition.')
    return redirect('core:shop_dashboard')


@role_required(RoleType.SHOP)
@require_POST
def shop_rate_order(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(Order, pk=order_id, shop__owner=request.role_profile)
    form = StoreRatingForm(request.POST, instance=order)
    if form.is_valid() and order.can_be_rated_by_store:
        form.save()
        refresh_ratings()
        create_notification(
            rider=order.rider,
            order=order,
            title='Store rated your delivery',
            body=f'The store rated order #{order.id} with {order.store_rating}/5.',
        )
        messages.success(request, 'Rider rating saved.')
    else:
        messages.error(request, 'This delivery cannot be rated right now.')
    return redirect('core:shop_dashboard')

@role_required(RoleType.RIDER)
def rider_dashboard(request: HttpRequest) -> HttpResponse:
    rider = request.role_profile
    if request.method == 'POST' and request.POST.get('action') == 'toggle_availability':
        if rider.approval_status != ApprovalStatus.APPROVED:
            messages.error(request, 'Admin approval is required before you can go live for dispatch.')
            return redirect('core:rider_dashboard')
        rider.is_available = request.POST.get('is_available') == 'on'
        rider.save(update_fields=['is_available', 'updated_at'])
        messages.success(request, 'Rider availability updated.')
        return redirect('core:rider_dashboard')

    active_riders = RiderProfile.objects.filter(approval_status=ApprovalStatus.APPROVED, is_available=True).count()
    dispatch_radius = rider.max_service_radius_km if active_riders < 3 else rider.service_radius_km
    order_candidates = (
        Order.objects.filter(
            status__in=[OrderStatus.CONFIRMED, OrderStatus.PACKED, OrderStatus.OUT_FOR_DELIVERY],
        )
        .select_related('customer', 'shop', 'rider')
        .prefetch_related('items__product')
    )
    available_orders = []
    active_orders = []
    if rider.approval_status == ApprovalStatus.APPROVED:
        for order in order_candidates:
            order.pickup_distance_km = kilometers_between(rider.latitude, rider.longitude, order.shop.latitude, order.shop.longitude)
            order.delivery_distance_km = kilometers_between(order.shop.latitude, order.shop.longitude, order.customer.latitude, order.customer.longitude)
            if order.rider_id == rider.id:
                active_orders.append(order)
            elif order.rider_id is None and order.pickup_distance_km <= dispatch_radius:
                available_orders.append(order)
    available_orders.sort(key=lambda order: (order.pickup_distance_km, order.id))
    active_orders.sort(key=lambda order: (order.status, order.id))

    context = {
        'rider': rider,
        'available_orders': available_orders,
        'active_orders': active_orders,
        'location_form': RiderLocationForm(initial={'latitude': rider.latitude, 'longitude': rider.longitude}),
        'notifications': user_notifications(request.user),
        'dispatch_radius': dispatch_radius,
        'completed_delivery_count': sum(1 for order in rider.orders.all() if order.status == OrderStatus.DELIVERED),
        'dashboard_role': RoleType.RIDER,
    }
    return render(request, 'core/rider_dashboard.html', context)


@role_required(RoleType.RIDER)
@require_POST
def rider_update_location(request: HttpRequest) -> HttpResponse:
    rider = request.role_profile
    form = RiderLocationForm(request.POST)
    if form.is_valid():
        rider.latitude = form.cleaned_data['latitude']
        rider.longitude = form.cleaned_data['longitude']
        rider.save(update_fields=['latitude', 'longitude', 'updated_at'])
        messages.success(request, 'Live location updated for the active demo.')
    else:
        messages.error(request, 'Could not update location.')
    return redirect('core:rider_dashboard')


@role_required(RoleType.RIDER)
@require_POST
def rider_accept_order(request: HttpRequest, order_id: int) -> HttpResponse:
    rider = request.role_profile
    if rider.approval_status != ApprovalStatus.APPROVED or not rider.is_available:
        messages.error(request, 'Only approved and available riders can accept new orders.')
        return redirect('core:rider_dashboard')
    order = get_object_or_404(Order, pk=order_id, rider__isnull=True)
    order.rider = rider
    if order.status == OrderStatus.CONFIRMED:
        order.status = OrderStatus.PACKED
    order.save(update_fields=['rider', 'status', 'updated_at'])
    rider.is_available = False
    rider.save(update_fields=['is_available', 'updated_at'])
    create_notification(
        customer=order.customer,
        order=order,
        title='Rider assigned',
        body=f'{rider.full_name} accepted order #{order.id}.',
    )
    create_notification(
        shop_owner=order.shop.owner,
        order=order,
        title='Rider assigned',
        body=f'{rider.full_name} accepted order #{order.id}.',
    )
    messages.success(request, f'Order #{order.id} assigned to {rider.full_name}.')
    return redirect('core:rider_dashboard')


@role_required(RoleType.RIDER)
@require_POST
def rider_update_order_status(request: HttpRequest, order_id: int) -> HttpResponse:
    rider = request.role_profile
    if rider.approval_status != ApprovalStatus.APPROVED:
        messages.error(request, 'Admin approval is required before completing deliveries.')
        return redirect('core:rider_dashboard')
    order = get_object_or_404(Order, pk=order_id, rider=rider)
    next_status = request.POST.get('status')
    otp = request.POST.get('customer_otp', '')

    if next_status == OrderStatus.DELIVERED and otp != order.customer_otp:
        messages.error(request, 'Customer OTP did not match.')
        return redirect('core:rider_dashboard')

    allowed = {OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED}
    if next_status in allowed:
        order.status = next_status
        if next_status == OrderStatus.DELIVERED:
            order.delivered_at = timezone.now()
            rider.is_available = True
            rider.save(update_fields=['is_available', 'updated_at'])
        order.save(update_fields=['status', 'updated_at', 'delivered_at'])
        create_notification(
            customer=order.customer,
            order=order,
            title='Delivery status updated',
            body=f'Order #{order.id} is now {order.get_status_display().lower()}.',
        )
        create_notification(
            shop_owner=order.shop.owner,
            order=order,
            title='Delivery status updated',
            body=f'Order #{order.id} is now {order.get_status_display().lower()}.',
        )
        messages.success(request, f'Order #{order.id} moved to {order.get_status_display()}.')
    else:
        messages.error(request, 'Invalid rider status transition.')
    return redirect('core:rider_dashboard')

@require_GET
def manifest(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            'name': 'GramExpress',
            'short_name': 'GramExpress',
            'start_url': '/auth/login/',
            'display': 'standalone',
            'orientation': 'portrait',
            'background_color': '#f3f6f1',
            'theme_color': '#eff7ee',
            'description': 'Mobile-first GramExpress workspace with OTP auth and local delivery dashboards.',
            'icons': [
                {
                    'src': '/static/core/icon.svg',
                    'sizes': '128x128',
                    'type': 'image/svg+xml',
                    'purpose': 'any',
                },
                {
                    'src': '/static/core/icon-maskable.svg',
                    'sizes': '512x512',
                    'type': 'image/svg+xml',
                    'purpose': 'maskable',
                },
            ],
        }
    )


@require_GET
def service_worker(_: HttpRequest) -> HttpResponse:
    cache_name = 'gramexpress-shell-v2'
    assets = [
        '/',
        '/auth/login/',
        '/auth/register/',
        '/manifest.json',
        '/static/core/styles.css',
        '/static/core/icon.svg',
        '/static/core/icon-maskable.svg',
    ]
    response = HttpResponse(
        f"""
const CACHE_NAME = '{cache_name}';
const ASSETS = {json.dumps(assets)};

self.addEventListener('install', (event) => {{
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting())
  );
}});

self.addEventListener('activate', (event) => {{
  event.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.map((key) => key !== CACHE_NAME ? caches.delete(key) : Promise.resolve()))).then(() => self.clients.claim())
  );
}});

self.addEventListener('fetch', (event) => {{
  if (event.request.method !== 'GET') {{
    return;
  }}
  event.respondWith(
    caches.match(event.request).then((cached) => cached || fetch(event.request).then((response) => {{
      if (!response || response.status !== 200 || response.type !== 'basic') {{
        return response;
      }}
      const clone = response.clone();
      caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
      return response;
    }}).catch(() => caches.match('/auth/login/')))
  );
}});
        """.strip(),
        content_type='application/javascript',
    )
    response['Service-Worker-Allowed'] = '/'
    return response
