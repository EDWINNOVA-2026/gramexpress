import base64
import hashlib
import hmac
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
from django.db.models import Avg, Count
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .forms import (
    CustomerOnboardingForm,
    CustomerLocationForm,
    CustomerOrderMetaForm,
    CustomerProfileForm,
    EmailOtpRequestForm,
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
    CheckoutSession,
    CustomerProfile,
    EmailOtpToken,
    Notification,
    NotificationType,
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
PENDING_EMAIL_OTP_SESSION_KEY = 'pending_passwordless_email_otp'
PENDING_CHECKOUT_SESSION_KEY = 'pending_checkout'
ACTIVE_CHECKOUT_SESSION_KEY = 'active_checkout_session_id'
LAST_CHECKOUT_SESSION_KEY = 'last_checkout'
CUSTOMER_LOCATION_SESSION_KEY = 'customer_live_location_confirmed'
CUSTOMER_LOCATION_LABEL_SESSION_KEY = 'customer_live_location_label'
CUSTOMER_LOCATION_HEADING_SESSION_KEY = 'customer_live_location_heading'
CUSTOMER_LOCATION_SUBTITLE_SESSION_KEY = 'customer_live_location_subtitle'
DEFAULT_LATITUDE = Decimal('12.915300')
DEFAULT_LONGITUDE = Decimal('76.643800')
DEFAULT_DELIVERY_RADIUS_KM = 20
PICKUP_GEOFENCE_KM = 0.2
ACCOUNT_ROLE_CHOICES = [RoleType.CUSTOMER, RoleType.SHOP, RoleType.RIDER]
TWILIO_API_BASE = 'https://api.twilio.com/2010-04-01/Accounts'
RAZORPAY_API_BASE = 'https://api.razorpay.com/v1'
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


def role_label(role: str) -> str:
    return dict(RoleType.choices).get(role, role.title() if role else 'Account')


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
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@gramexpress.local'),
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
            notification_type=NotificationType.SYSTEM,
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
            notification_type=NotificationType.STORE,
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
        notification_type=NotificationType.RIDER,
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


def reverse_geocode_location(latitude: Decimal, longitude: Decimal) -> dict[str, str]:
    api_key = getattr(settings, 'GOOGLE_MAPS_BROWSER_API_KEY', '')
    language = 'en'
    if api_key:
        query = urllib_parse.urlencode(
            {
                'latlng': f'{latitude},{longitude}',
                'key': api_key,
            }
        )
        try:
            with urllib_request.urlopen(f'https://maps.googleapis.com/maps/api/geocode/json?{query}', timeout=12) as response:
                payload = json.loads(response.read().decode('utf-8'))
        except (urllib_error.URLError, json.JSONDecodeError):
            payload = {}

        results = payload.get('results', [])
        if results:
            first_result = results[0]
            components = first_result.get('address_components', [])
            component_map = {}
            for component in components:
                for component_type in component.get('types', []):
                    component_map.setdefault(component_type, component.get('long_name', ''))

            street_parts = [
                component_map.get('street_number', ''),
                component_map.get('route', ''),
            ]
            address_line_1 = ' '.join(part for part in street_parts if part).strip() or first_result.get('formatted_address', '')[:160]
            district = (
                component_map.get('sublocality_level_1')
                or component_map.get('locality')
                or component_map.get('administrative_area_level_2')
                or component_map.get('administrative_area_level_1')
                or ''
            )
            return {
                'formatted_address': first_result.get('formatted_address', '')[:200],
                'address_line_1': address_line_1[:160],
                'locality': (
                    component_map.get('sublocality_level_1')
                    or component_map.get('neighborhood')
                    or component_map.get('locality')
                    or ''
                )[:80],
                'city': (
                    component_map.get('locality')
                    or component_map.get('administrative_area_level_2')
                    or component_map.get('administrative_area_level_1')
                    or ''
                )[:80],
                'district': district[:80],
                'pincode': component_map.get('postal_code', '')[:12],
            }

    query = urllib_parse.urlencode(
        {
            'format': 'jsonv2',
            'lat': latitude,
            'lon': longitude,
            'addressdetails': 1,
            'accept-language': language,
        }
    )
    headers = {
        'User-Agent': f'{getattr(settings, "GRAMEXPRESS_APP_NAME", "GramExpress")}/1.0 ({getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@gramexpress.local")})',
    }
    try:
        request = urllib_request.Request(f'https://nominatim.openstreetmap.org/reverse?{query}', headers=headers)
        with urllib_request.urlopen(request, timeout=12) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (urllib_error.URLError, json.JSONDecodeError):
        return {}

    address = payload.get('address', {})
    display_name = (payload.get('display_name') or '').strip()
    if not address and not display_name:
        return {}

    street_parts = [
        address.get('house_number', ''),
        address.get('road', '') or address.get('pedestrian', '') or address.get('footway', ''),
    ]
    address_line_1 = ' '.join(part for part in street_parts if part).strip() or address.get('neighbourhood', '') or address.get('suburb', '') or display_name[:160]
    district = (
        address.get('suburb')
        or address.get('neighbourhood')
        or address.get('city')
        or address.get('town')
        or address.get('village')
        or address.get('county')
        or address.get('state_district')
        or address.get('state')
        or ''
    )
    return {
        'formatted_address': display_name[:200],
        'address_line_1': address_line_1[:160],
        'locality': (
            address.get('suburb')
            or address.get('neighbourhood')
            or address.get('city_district')
            or address.get('quarter')
            or ''
        )[:80],
        'city': (
            address.get('city')
            or address.get('town')
            or address.get('village')
            or address.get('county')
            or address.get('state_district')
            or address.get('state')
            or ''
        )[:80],
        'district': district[:80],
        'pincode': address.get('postcode', '')[:12],
    }


def customer_address_summary(customer: CustomerProfile) -> str:
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


def customer_location_summary(customer: CustomerProfile) -> str:
    address = customer_address_summary(customer)
    if address:
        return address
    return f'Latitude {customer.latitude}, Longitude {customer.longitude}'


def customer_has_live_location(request: HttpRequest, customer: CustomerProfile) -> bool:
    if request.session.get(CUSTOMER_LOCATION_SESSION_KEY):
        return True
    return not (customer.latitude == DEFAULT_LATITUDE and customer.longitude == DEFAULT_LONGITUDE)


def live_location_label(request: HttpRequest, customer: CustomerProfile) -> str:
    label = (request.session.get(CUSTOMER_LOCATION_LABEL_SESSION_KEY) or '').strip()
    if label:
        return label
    return customer_location_summary(customer)


def live_location_heading_and_subtitle(request: HttpRequest, customer: CustomerProfile, label: str) -> tuple[str, str]:
    heading = (request.session.get(CUSTOMER_LOCATION_HEADING_SESSION_KEY) or '').strip()
    subtitle = (request.session.get(CUSTOMER_LOCATION_SUBTITLE_SESSION_KEY) or '').strip()
    if heading:
        return heading, subtitle
    return split_location_label(label)


def split_location_label(label: str) -> tuple[str, str]:
    parts = [part.strip() for part in label.split(',') if part.strip()]
    if not parts:
        return 'Current location', ''
    if len(parts) == 1:
        return parts[0], ''
    return parts[0], ', '.join(parts[1:])


def disable_html_cache(response: HttpResponse) -> HttpResponse:
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


def discover_customer_shops(customer: CustomerProfile, *, query: str = '') -> list[Shop]:
    approved_shops = list(
        Shop.objects.filter(approval_status=ApprovalStatus.APPROVED, is_open=True)
        .select_related('owner')
        .prefetch_related('products')
    )
    filtered_shops = []
    normalized_query = query.strip().lower()
    for shop in approved_shops:
        set_distance(shop, customer.latitude, customer.longitude)
        if shop.distance_km > DEFAULT_DELIVERY_RADIUS_KM:
            continue
        if normalized_query:
            haystack = ' '.join(
                [
                    shop.name,
                    shop.area,
                    shop.district,
                    shop.shop_type,
                    shop.get_shop_type_display(),
                ]
            ).lower()
            if normalized_query not in haystack:
                continue
        filtered_shops.append(shop)
    filtered_shops.sort(key=lambda shop: (shop.distance_km, -float(shop.rating), shop.name))
    return filtered_shops


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


def is_razorpay_ready() -> bool:
    return bool(getattr(settings, 'RAZORPAY_KEY_ID', '') and getattr(settings, 'RAZORPAY_KEY_SECRET', ''))


def landing_context() -> dict[str, Any]:
    return {}


def customer_page_nav() -> list[dict[str, str]]:
    return [
        {'label': 'Home', 'url': reverse('core:customer_dashboard')},
        {'label': 'Cart', 'url': reverse('core:customer_cart')},
        {'label': 'Orders', 'url': reverse('core:customer_orders')},
        {'label': 'Profile', 'url': reverse('core:customer_profile')},
    ]


def shop_page_nav() -> list[dict[str, str]]:
    return [
        {'label': 'Overview', 'url': reverse('core:shop_dashboard')},
        {'label': 'Orders', 'url': reverse('core:shop_orders')},
        {'label': 'Catalog', 'url': reverse('core:shop_products')},
        {'label': 'Settings', 'url': reverse('core:shop_settings')},
    ]


def rider_page_nav() -> list[dict[str, str]]:
    return [
        {'label': 'Overview', 'url': reverse('core:rider_dashboard')},
        {'label': 'Deliveries', 'url': reverse('core:rider_deliveries')},
        {'label': 'Profile', 'url': reverse('core:rider_profile')},
    ]


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
        availability_label = 'Ready'
        availability_class = 'success'
        if product.shop.approval_status != ApprovalStatus.APPROVED or not product.shop.is_open:
            issues.append('This store is currently unavailable for checkout.')
            availability_label = 'Store offline'
            availability_class = 'warn'
        if product.stock <= 0:
            issues.append('This item is out of stock.')
            availability_label = 'Out of stock'
            availability_class = 'warn'
        elif quantity > product.stock:
            issues.append(f'Only {product.stock} unit(s) are available right now.')
            availability_label = 'Qty exceeds stock'
            availability_class = 'warn'
        line_total = product.price * quantity
        item = {
            'product': product,
            'quantity': quantity,
            'line_total': line_total,
            'issues': issues,
            'has_blocking_issue': bool(issues),
            'max_quantity': max(product.stock, 1),
            'availability_label': availability_label,
            'availability_class': availability_class,
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
                'item_count': sum(item['quantity'] for item in shop_items),
            }
        )
    groups.sort(key=lambda group: group['shop'].name)
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


def decimal_to_str(value: Decimal) -> str:
    return format(value.quantize(Decimal('0.01')), 'f')


def build_cart_snapshot(cart: dict[str, Any]) -> dict[str, Any]:
    groups = []
    for group in cart['groups']:
        delivery_fee = Decimal('20.00')
        groups.append(
            {
                'shop_id': group['shop'].id,
                'delivery_fee': decimal_to_str(delivery_fee),
                'subtotal': decimal_to_str(group['subtotal']),
                'total': decimal_to_str(group['subtotal'] + delivery_fee),
                'items': [
                    {
                        'product_id': item['product'].id,
                        'product_name': item['product'].name,
                        'quantity': item['quantity'],
                        'unit_price': decimal_to_str(item['product'].price),
                    }
                    for item in group['items']
                ],
            }
        )
    return {
        'item_count': cart['item_count'],
        'subtotal': decimal_to_str(cart['subtotal']),
        'groups': groups,
    }


def build_checkout_signature(*, snapshot: dict[str, Any], payment_method: str, customer_notes: str, delivery_address: str) -> str:
    signature_source = json.dumps(
        {
            'snapshot': snapshot,
            'payment_method': payment_method,
            'customer_notes': customer_notes,
            'delivery_address': delivery_address,
        },
        sort_keys=True,
        separators=(',', ':'),
    )
    return hashlib.sha256(signature_source.encode('utf-8')).hexdigest()


def build_checkout_session_payload(*, customer: CustomerProfile, cart: dict[str, Any], checkout_data: dict[str, str]) -> dict[str, Any]:
    snapshot = build_cart_snapshot(cart)
    delivery_address = build_delivery_address(customer)
    payment_method = checkout_data.get('payment_method', PaymentMethod.COD)
    customer_notes = checkout_data.get('customer_notes', '')
    amount = sum(Decimal(group['total']) for group in snapshot['groups']) if snapshot['groups'] else Decimal('0.00')
    return {
        'payment_method': payment_method,
        'customer_notes': customer_notes,
        'delivery_address': delivery_address,
        'cart_snapshot': snapshot,
        'cart_signature': build_checkout_signature(
            snapshot=snapshot,
            payment_method=payment_method,
            customer_notes=customer_notes,
            delivery_address=delivery_address,
        ),
        'amount': amount,
        'currency': 'INR',
    }


def save_pending_checkout(request: HttpRequest, *, payment_method: str, customer_notes: str) -> None:
    request.session[PENDING_CHECKOUT_SESSION_KEY] = {
        'payment_method': payment_method,
        'customer_notes': customer_notes,
    }
    request.session.modified = True


def save_active_checkout_session(request: HttpRequest, checkout_session_id: int | None) -> None:
    if checkout_session_id is None:
        request.session.pop(ACTIVE_CHECKOUT_SESSION_KEY, None)
    else:
        request.session[ACTIVE_CHECKOUT_SESSION_KEY] = checkout_session_id
    request.session.modified = True


def pending_checkout_data(request: HttpRequest) -> dict[str, str]:
    return request.session.get(PENDING_CHECKOUT_SESSION_KEY, {})


def active_checkout_session_id(request: HttpRequest) -> int | None:
    checkout_session_id = request.session.get(ACTIVE_CHECKOUT_SESSION_KEY)
    if not checkout_session_id:
        return None
    try:
        return int(checkout_session_id)
    except (TypeError, ValueError):
        return None


def clear_pending_checkout(request: HttpRequest) -> None:
    request.session.pop(PENDING_CHECKOUT_SESSION_KEY, None)
    request.session.pop(ACTIVE_CHECKOUT_SESSION_KEY, None)
    request.session.modified = True


def set_last_checkout_payload(request: HttpRequest, *, orders: list[Order], payment_method: str, checkout_session: CheckoutSession | None = None) -> None:
    request.session[LAST_CHECKOUT_SESSION_KEY] = {
        'order_ids': [order.id for order in orders],
        'payment_method': payment_method,
        'estimated_total': decimal_to_str(sum(order.total_amount for order in orders)) if orders else '0.00',
        'checkout_session_id': checkout_session.id if checkout_session else None,
    }
    request.session.modified = True


def razorpay_basic_auth_header() -> str:
    raw = f'{getattr(settings, "RAZORPAY_KEY_ID", "")}:{getattr(settings, "RAZORPAY_KEY_SECRET", "")}'
    return base64.b64encode(raw.encode('utf-8')).decode('ascii')


def razorpay_api_request(*, path: str, method: str = 'GET', payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {
        'Authorization': f'Basic {razorpay_basic_auth_header()}',
        'Accept': 'application/json',
    }
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    request_obj = urllib_request.Request(
        f'{RAZORPAY_API_BASE}{path}',
        data=data,
        headers=headers,
        method=method.upper(),
    )
    try:
        with urllib_request.urlopen(request_obj, timeout=15) as response:
            return json.loads(response.read().decode('utf-8'))
    except urllib_error.HTTPError as error:
        detail = error.read().decode('utf-8', errors='ignore')
        raise CheckoutValidationError(detail or 'Razorpay request failed.') from error
    except urllib_error.URLError as error:
        raise CheckoutValidationError('Could not reach Razorpay right now. Please try again in a moment.') from error


def create_razorpay_order_for_checkout(checkout_session: CheckoutSession) -> dict[str, Any]:
    payload = {
        'amount': int((checkout_session.amount * 100).quantize(Decimal('1'))),
        'currency': checkout_session.currency,
        'receipt': checkout_session.receipt or f'grx-{checkout_session.id}',
        'notes': {
            'checkout_session_id': str(checkout_session.id),
            'customer_phone': checkout_session.customer.phone,
        },
    }
    razorpay_order = razorpay_api_request(path='/orders', method='POST', payload=payload)
    checkout_session.receipt = payload['receipt']
    checkout_session.razorpay_order_id = razorpay_order.get('id', '')
    checkout_session.failure_reason = ''
    checkout_session.save(update_fields=['receipt', 'razorpay_order_id', 'failure_reason', 'updated_at'])
    return razorpay_order


def fetch_razorpay_payment(payment_id: str) -> dict[str, Any]:
    return razorpay_api_request(path=f'/payments/{payment_id}')


def fetch_razorpay_order(order_id: str) -> dict[str, Any]:
    return razorpay_api_request(path=f'/orders/{order_id}')


def verify_razorpay_payment_signature(*, razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
    generated_signature = hmac.new(
        getattr(settings, 'RAZORPAY_KEY_SECRET', '').encode('utf-8'),
        f'{razorpay_order_id}|{razorpay_payment_id}'.encode('utf-8'),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(generated_signature, razorpay_signature)


def verify_razorpay_webhook_signature(*, payload: bytes, signature: str) -> bool:
    webhook_secret = getattr(settings, 'RAZORPAY_WEBHOOK_SECRET', '')
    if not webhook_secret or not signature:
        return False
    generated_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(generated_signature, signature)


def build_razorpay_checkout_context(checkout_session: CheckoutSession, customer: CustomerProfile) -> dict[str, Any]:
    return {
        'key': getattr(settings, 'RAZORPAY_KEY_ID', ''),
        'amount': int((checkout_session.amount * 100).quantize(Decimal('1'))),
        'currency': checkout_session.currency,
        'name': getattr(settings, 'GRAMEXPRESS_APP_NAME', 'GramExpress'),
        'description': f'{len(checkout_session.cart_snapshot.get("groups", []))} store checkout',
        'order_id': checkout_session.razorpay_order_id,
        'prefill': {
            'name': customer.full_name,
            'email': customer.email,
            'contact': customer.phone,
        },
        'notes': {
            'checkout_session_id': str(checkout_session.id),
            'delivery_address': checkout_session.delivery_address,
        },
        'theme': {
            'color': '#1f6f43',
        },
        'checkout_session_id': checkout_session.id,
    }


def get_or_create_online_checkout_session(*, request: HttpRequest, customer: CustomerProfile, cart: dict[str, Any], checkout_data: dict[str, str]) -> CheckoutSession:
    payload = build_checkout_session_payload(customer=customer, cart=cart, checkout_data=checkout_data)
    existing_session = None
    existing_session_id = active_checkout_session_id(request)
    if existing_session_id:
        existing_session = CheckoutSession.objects.filter(pk=existing_session_id, customer=customer).first()

    if (
        existing_session
        and not existing_session.is_completed
        and existing_session.payment_method == PaymentMethod.RAZORPAY
        and existing_session.cart_signature == payload['cart_signature']
    ):
        if not existing_session.razorpay_order_id:
            create_razorpay_order_for_checkout(existing_session)
        return existing_session

    checkout_session = CheckoutSession.objects.create(
        customer=customer,
        payment_method=PaymentMethod.RAZORPAY,
        payment_status=PaymentStatus.PENDING,
        amount=payload['amount'],
        currency=payload['currency'],
        customer_notes=payload['customer_notes'],
        delivery_address=payload['delivery_address'],
        cart_snapshot=payload['cart_snapshot'],
        cart_signature=payload['cart_signature'],
        receipt=f'grx-{customer.id}-{int(timezone.now().timestamp())}',
    )
    create_razorpay_order_for_checkout(checkout_session)
    save_active_checkout_session(request, checkout_session.id)
    return checkout_session


def create_cod_checkout_session(*, customer: CustomerProfile, cart: dict[str, Any], checkout_data: dict[str, str]) -> CheckoutSession:
    payload = build_checkout_session_payload(customer=customer, cart=cart, checkout_data=checkout_data)
    return CheckoutSession.objects.create(
        customer=customer,
        payment_method=PaymentMethod.COD,
        payment_status=PaymentStatus.PENDING,
        amount=payload['amount'],
        currency=payload['currency'],
        customer_notes=payload['customer_notes'],
        delivery_address=payload['delivery_address'],
        cart_snapshot=payload['cart_snapshot'],
        cart_signature=payload['cart_signature'],
        receipt=f'grx-cod-{customer.id}-{int(timezone.now().timestamp())}',
    )


def build_checkout_context(
    *,
    customer: CustomerProfile,
    cart: dict[str, Any],
    checkout_data: dict[str, str],
    checkout_session: CheckoutSession | None = None,
) -> dict[str, Any]:
    payment_method = checkout_data.get('payment_method', PaymentMethod.COD)
    customer_notes = checkout_data.get('customer_notes', '')
    razorpay_enabled = is_razorpay_ready()
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
        'razorpay_enabled': razorpay_enabled,
        'razorpay_key_id': getattr(settings, 'RAZORPAY_KEY_ID', ''),
        'checkout_session': checkout_session,
        'razorpay_checkout': (
            build_razorpay_checkout_context(checkout_session, customer)
            if checkout_session and payment_method == PaymentMethod.RAZORPAY and checkout_session.razorpay_order_id
            else None
        ),
    }


def validate_checkout_cart(cart: dict[str, Any]) -> None:
    if not cart['items']:
        raise CheckoutValidationError('Your cart is empty. Add items before checkout.')
    if cart['has_blocking_issues']:
        raise CheckoutValidationError('Please fix the cart issues before continuing to checkout.')


def notify_checkout_orders(*, checkout_session: CheckoutSession, created_orders: list[Order]) -> None:
    payment_method = checkout_session.payment_method
    for order in created_orders:
        create_notification(
            shop_owner=order.shop.owner,
            order=order,
            title='New order placed',
            body=f'Order #{order.id} is waiting for packaging at {order.shop.name}.',
            notification_type=NotificationType.ORDER,
        )
        create_notification(
            customer=order.customer,
            order=order,
            title='Order confirmed',
            body=f'Order #{order.id} from {order.shop.name} was created successfully.',
            notification_type=(
                NotificationType.PAYMENT
                if payment_method == PaymentMethod.RAZORPAY
                else NotificationType.ORDER
            ),
        )
        if order.rider:
            create_notification(
                rider=order.rider,
                order=order,
                title='New delivery request',
                body=f'Order #{order.id} is ready around {order.shop.area}.',
                notification_type=NotificationType.RIDER,
            )


def finalize_checkout_session(checkout_session: CheckoutSession) -> list[Order]:
    if checkout_session.is_completed:
        return list(checkout_session.orders.select_related('shop', 'rider', 'customer').all())

    created_orders = []
    cart_snapshot = checkout_session.cart_snapshot or {}
    group_snapshots = cart_snapshot.get('groups', [])
    if not group_snapshots:
        raise CheckoutValidationError('This checkout session has no cart items.')

    with transaction.atomic():
        locked_session = CheckoutSession.objects.select_for_update().get(pk=checkout_session.pk)
        if locked_session.is_completed:
            return list(locked_session.orders.select_related('shop', 'rider', 'customer').all())

        for group_snapshot in group_snapshots:
            shop = Shop.objects.select_related('owner').get(pk=group_snapshot['shop_id'])
            if shop.approval_status != ApprovalStatus.APPROVED or not shop.is_open:
                raise CheckoutValidationError(f'{shop.name} is no longer available for checkout.')

            locked_items = []
            subtotal = Decimal('0.00')
            for item_snapshot in group_snapshot['items']:
                locked_product = Product.objects.select_for_update().select_related('shop').get(pk=item_snapshot['product_id'])
                if locked_product.shop_id != shop.id:
                    raise CheckoutValidationError(f'{locked_product.name} is no longer available from the selected store.')
                if locked_product.stock < item_snapshot['quantity']:
                    raise CheckoutValidationError(
                        f'{locked_product.name} only has {locked_product.stock} unit(s) left. Update your cart and try again.'
                    )
                unit_price = Decimal(item_snapshot['unit_price'])
                quantity = int(item_snapshot['quantity'])
                subtotal += unit_price * quantity
                locked_items.append((locked_product, quantity, unit_price))

            rider = nearest_available_rider(shop)
            order = Order.objects.create(
                customer=locked_session.customer,
                shop=shop,
                rider=rider,
                checkout_session=locked_session,
                status=OrderStatus.CONFIRMED,
                payment_method=locked_session.payment_method,
                payment_status=locked_session.payment_status,
                delivery_address=locked_session.delivery_address,
                customer_notes=locked_session.customer_notes,
                customer_otp=f'{random.randint(0, 999999):06d}',
                total_amount=subtotal + Decimal(group_snapshot['delivery_fee']),
            )
            for locked_product, quantity, unit_price in locked_items:
                OrderItem.objects.create(
                    order=order,
                    product=locked_product,
                    quantity=quantity,
                    unit_price=unit_price,
                )
                locked_product.stock -= quantity
                locked_product.save(update_fields=['stock', 'updated_at'])
            if rider:
                rider.is_available = False
                rider.save(update_fields=['is_available', 'updated_at'])
            created_orders.append(order)

        locked_session.completed_at = timezone.now()
        locked_session.save(update_fields=['completed_at', 'updated_at'])

    notify_checkout_orders(checkout_session=checkout_session, created_orders=created_orders)
    return created_orders


def create_notification(
    *,
    customer=None,
    shop_owner=None,
    rider=None,
    order=None,
    title: str,
    body: str,
    notification_type: str = NotificationType.SYSTEM,
) -> None:
    Notification.objects.create(
        customer=customer,
        shop_owner=shop_owner,
        rider=rider,
        order=order,
        notification_type=notification_type,
        title=title,
        body=body,
    )


def user_notifications(user):
    queryset = notification_queryset_for_user(user)
    return queryset[:6]


def customer_workspace_context(request: HttpRequest) -> dict[str, Any]:
    customer = request.role_profile
    shop_query = request.GET.get('q', '').strip()
    has_live_location = customer_has_live_location(request, customer)
    shops = discover_customer_shops(customer, query=shop_query) if has_live_location else []
    location_label = live_location_label(request, customer)
    location_heading, location_subtitle = live_location_heading_and_subtitle(request, customer, location_label)
    category_map = {}
    recommended_shops = []
    for shop in shops:
        products = list(shop.products.all())
        shop_rating = shop.orders.filter(customer_rating__isnull=False).aggregate(
            avg=Avg('customer_rating'),
            count=Count('customer_rating'),
        )
        rating_average = shop_rating['avg']
        shop.display_rating = round(float(rating_average), 1) if rating_average is not None else float(shop.rating)
        shop.rating_count = shop_rating['count'] or 0
        if not shop.image_source:
            fallback_image = next((product.image_url for product in products if product.image_url), '')
            shop.card_image_source = fallback_image
        else:
            shop.card_image_source = shop.image_source
        shop.product_count = len(products)
        shop.delivery_eta_label = '10-15 mins' if shop.distance_km <= 3 else '20-30 mins' if shop.distance_km <= 8 else '30-40 mins'
        shop.speed_badge = 'Near & Fast' if shop.distance_km <= 6 else 'Worth the ride'
        shop.offer_badge = shop.offer or 'Fresh delivery'
        recommended_shops.append(shop)
        category_key = (shop.get_shop_type_display() or shop.shop_type).strip()
        if category_key and category_key not in category_map:
            category_map[category_key] = {
                'label': category_key,
                'slug': shop.shop_type,
                'icon': products[0].name[:1].upper() if products else shop.name[:1].upper(),
            }
        for product in products:
            category_key = (product.category or '').strip()
            if category_key and category_key not in category_map:
                category_map[category_key] = {
                    'label': category_key,
                    'slug': category_key.lower().replace(' ', '-'),
                    'icon': product.name[:1].upper(),
                }
            if len(category_map) >= 6:
                break
        if len(category_map) >= 6:
            continue

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

    razorpay_enabled = is_razorpay_ready()
    return {
        'customer': customer,
        'shops': shops,
        'orders': orders,
        'cart': cart,
        'notifications': user_notifications(request.user),
        'google_maps_embed_api_key': getattr(settings, 'GOOGLE_MAPS_EMBED_API_KEY', ''),
        'delivery_radius_km': DEFAULT_DELIVERY_RADIUS_KM,
        'address_summary': customer_address_summary(customer),
        'location_summary': location_label,
        'location_heading': location_heading,
        'location_subtitle': location_subtitle,
        'location_coordinates': customer.short_coordinates,
        'shop_query': shop_query,
        'location_required': not has_live_location,
        'has_live_location': has_live_location,
        'category_tiles': list(category_map.values())[:6],
        'recommended_shops': recommended_shops[:8],
        'feature_shop': recommended_shops[0] if recommended_shops else None,
        'active_order_count': sum(
            1 for order in orders if order.status not in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]
        ),
        'delivered_order_count': sum(1 for order in orders if order.status == OrderStatus.DELIVERED),
        'dashboard_role': RoleType.CUSTOMER,
        'page_nav': customer_page_nav(),
        'razorpay_enabled': razorpay_enabled,
        'razorpay_key_id': getattr(settings, 'RAZORPAY_KEY_ID', ''),
    }


def shop_workspace_context(request: HttpRequest, *, editing_product_id: str | None = None) -> dict[str, Any]:
    owner = request.role_profile
    shop = get_object_or_404(
        Shop.objects.select_related('owner').prefetch_related('products', 'orders__customer', 'orders__rider', 'orders__items__product'),
        owner=owner,
    )
    editing_product = get_object_or_404(Product, pk=editing_product_id, shop=shop) if editing_product_id else None
    orders = shop.orders.all()
    for order in orders:
        order.item_count = sum(item.quantity for item in order.items.all())
        order.can_mark_confirmed = order.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED]
        order.can_mark_packed = order.status in [OrderStatus.CONFIRMED, OrderStatus.PACKED]
        order.can_cancel_from_store = order.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PACKED]
        if order.status == OrderStatus.CONFIRMED:
            order.fulfillment_title = 'Prepare and pack this order'
            order.fulfillment_hint = 'Items are confirmed. Finish packing so rider dispatch can move faster.'
            order.fulfillment_chip = 'info'
        elif order.status == OrderStatus.PACKED and order.rider:
            order.fulfillment_title = 'Packed and waiting on rider pickup'
            order.fulfillment_hint = f'{order.rider.full_name} is assigned. Keep the order ready for handoff.'
            order.fulfillment_chip = 'success'
        elif order.status == OrderStatus.PACKED:
            order.fulfillment_title = 'Packed and waiting for rider assignment'
            order.fulfillment_hint = 'Packaging is done. Dispatch will move as soon as an available rider accepts.'
            order.fulfillment_chip = 'info'
        elif order.status == OrderStatus.OUT_FOR_DELIVERY:
            order.fulfillment_title = 'With rider for last-mile delivery'
            order.fulfillment_hint = 'Store-side cancellation is locked once the rider has taken the order.'
            order.fulfillment_chip = 'success'
        elif order.status == OrderStatus.DELIVERED:
            order.fulfillment_title = 'Delivered and closed'
            order.fulfillment_hint = 'This order is complete. Ratings and history stay available below.'
            order.fulfillment_chip = 'success'
        elif order.status == OrderStatus.CANCELLED:
            order.fulfillment_title = 'Order cancelled'
            order.fulfillment_hint = order.cancellation_reason or 'This order was cancelled before delivery.'
            order.fulfillment_chip = 'warn'
        else:
            order.fulfillment_title = 'Awaiting store confirmation'
            order.fulfillment_hint = 'Confirm the order before you begin packing.'
            order.fulfillment_chip = 'info'
        if order.rider:
            order.rider_tracking_url = order.rider.google_maps_url

    return {
        'shop': shop,
        'orders': orders,
        'editing_product': editing_product,
        'notifications': user_notifications(request.user),
        'live_product_count': shop.products.count(),
        'active_order_count': sum(
            1 for order in orders if order.status not in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]
        ),
        'delivered_order_count': sum(1 for order in orders if order.status == OrderStatus.DELIVERED),
        'dashboard_role': RoleType.SHOP,
        'page_nav': shop_page_nav(),
    }


def rider_workspace_context(request: HttpRequest) -> dict[str, Any]:
    rider = request.role_profile
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
            order.item_count = sum(item.quantity for item in order.items.all())
            order.pickup_route_url = build_google_route_url(rider.latitude, rider.longitude, order.shop.latitude, order.shop.longitude)
            order.delivery_route_url = build_google_route_url(order.shop.latitude, order.shop.longitude, order.customer.latitude, order.customer.longitude)
            order.customer_route_url = build_google_route_url(rider.latitude, rider.longitude, order.customer.latitude, order.customer.longitude)
            order.pickup_gate_open = order.pickup_distance_km <= PICKUP_GEOFENCE_KM
            if order.status == OrderStatus.OUT_FOR_DELIVERY:
                order.dispatch_title = 'Complete the last-mile drop'
                order.dispatch_hint = 'Ask the customer for the OTP before you mark the order as delivered.'
            else:
                order.dispatch_title = 'Reach the store and confirm pickup'
                order.dispatch_hint = (
                    'You are close enough to mark pickup.'
                    if order.pickup_gate_open
                    else f'Get closer to the store to mark pickup. You are {order.pickup_distance_km} km away.'
                )
            if order.rider_id == rider.id:
                active_orders.append(order)
            elif order.rider_id is None and order.pickup_distance_km <= dispatch_radius:
                available_orders.append(order)
    available_orders.sort(key=lambda order: (order.pickup_distance_km, order.id))
    active_orders.sort(key=lambda order: (order.status, order.id))
    return {
        'rider': rider,
        'available_orders': available_orders,
        'active_orders': active_orders,
        'location_form': RiderLocationForm(initial={'latitude': rider.latitude, 'longitude': rider.longitude}),
        'notifications': user_notifications(request.user),
        'dispatch_radius': dispatch_radius,
        'completed_delivery_count': sum(1 for order in rider.orders.all() if order.status == OrderStatus.DELIVERED),
        'dashboard_role': RoleType.RIDER,
        'page_nav': rider_page_nav(),
    }


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
    queryset = Order.objects.select_related('customer', 'shop__owner', 'rider', 'checkout_session').prefetch_related('items__product')
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


def build_order_eta_label(order: Order) -> str:
    return {
        OrderStatus.PENDING: '35-45 min',
        OrderStatus.CONFIRMED: '25-35 min',
        OrderStatus.PACKED: '15-25 min',
        OrderStatus.OUT_FOR_DELIVERY: '8-15 min',
        OrderStatus.DELIVERED: 'Delivered',
        OrderStatus.CANCELLED: 'Cancelled',
    }.get(order.status, '40-55 min')


def build_order_status_summary(order: Order) -> dict[str, str]:
    if order.status == OrderStatus.CANCELLED:
        cancelled_by = dict(RoleType.choices).get(order.cancelled_by_role, 'System')
        return {
            'title': 'Order cancelled',
            'caption': f'Cancelled by {cancelled_by.lower()}.',
            'detail': order.cancellation_reason or 'This order was cancelled before delivery.',
            'chip_class': 'warn',
        }
    if order.status == OrderStatus.DELIVERED:
        return {
            'title': 'Delivered successfully',
            'caption': 'Handoff completed and this order is closed.',
            'detail': 'You can now review the order or reorder the same items later.',
            'chip_class': 'success',
        }
    if order.status == OrderStatus.OUT_FOR_DELIVERY:
        return {
            'title': 'Rider is approaching',
            'caption': 'Keep your phone nearby and share the OTP only during handoff.',
            'detail': 'Tracking, rider location, and final OTP verification are active now.',
            'chip_class': 'info',
        }
    if order.status == OrderStatus.PACKED:
        return {
            'title': 'Packed and leaving soon',
            'caption': 'The store has packed everything and dispatch is the next step.',
            'detail': 'A rider can pick this up as soon as dispatch is available.',
            'chip_class': 'info',
        }
    if order.status == OrderStatus.CONFIRMED:
        return {
            'title': 'Store has confirmed your order',
            'caption': 'Preparation is in progress.',
            'detail': 'You can still cancel from the customer side until dispatch advances.',
            'chip_class': 'info',
        }
    return {
        'title': 'Order received',
        'caption': 'The order is recorded and waiting for store action.',
        'detail': 'The next update will appear once the store confirms preparation.',
        'chip_class': 'info',
    }


def build_payment_summary(order: Order) -> dict[str, str]:
    if order.payment_method == PaymentMethod.COD:
        return {
            'label': 'Cash on delivery',
            'detail': 'Pay the rider after checking the order at handoff.',
            'chip_class': 'warn' if order.payment_status != PaymentStatus.PAID else 'success',
        }
    if order.payment_status == PaymentStatus.PAID:
        return {
            'label': 'Paid online',
            'detail': 'Online payment was captured successfully for this order.',
            'chip_class': 'success',
        }
    if order.payment_status == PaymentStatus.FAILED:
        return {
            'label': 'Payment failed',
            'detail': 'This online payment did not complete successfully.',
            'chip_class': 'warn',
        }
    return {
        'label': 'Online payment pending',
        'detail': 'Payment is still waiting for a confirmed result.',
        'chip_class': 'info',
    }


def build_google_embed_route_url(origin_lat: Decimal, origin_lng: Decimal, dest_lat: Decimal, dest_lng: Decimal) -> str:
    api_key = getattr(settings, 'GOOGLE_MAPS_EMBED_API_KEY', '')
    if not api_key:
        return ''
    return (
        'https://www.google.com/maps/embed/v1/directions'
        f'?key={urllib_parse.quote(api_key)}'
        f'&origin={origin_lat},{origin_lng}'
        f'&destination={dest_lat},{dest_lng}'
        '&mode=driving'
    )


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
    return render(request, 'core/home.html', landing_context())


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
    pending_login_role_label = ''
    if pending_login:
        pending_user = get_user_model().objects.filter(pk=pending_login.get('user_id')).first()
        if pending_user:
            pending_login_role_label = role_label(get_role_profile(pending_user)[0] or '')
    return render(
        request,
        'core/login.html',
        {
            'form': login_form,
            'otp_form': otp_form,
            'pending_login': pending_login,
            'pending_login_masked_email': mask_email(pending_login['email']) if pending_login else '',
            'otp_expiry_minutes': getattr(settings, 'OTP_EXPIRY_MINUTES', 10),
            'pending_login_role_label': pending_login_role_label,
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
            'pending_registration_role_label': role_label(pending_registration.get('account_type', '')) if pending_registration else '',
            'otp_expiry_minutes': getattr(settings, 'OTP_EXPIRY_MINUTES', 10),
            'google_client_id': getattr(settings, 'GOOGLE_CLIENT_ID', ''),
        },
    )


def email_otp_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_for_user(request.user))

    pending_email_otp = request.session.get(PENDING_EMAIL_OTP_SESSION_KEY, {})
    request_form = EmailOtpRequestForm(initial={'email': pending_email_otp.get('email', request.GET.get('email', ''))})
    verify_form = EmailOtpVerifyForm(initial={'email': pending_email_otp.get('email', request.GET.get('email', ''))})

    if request.method == 'POST':
        action = request.POST.get('action', 'request')
        if action == 'request':
            request_form = EmailOtpRequestForm(request.POST)
            verify_form = EmailOtpVerifyForm(initial={'email': request.POST.get('email', '').strip()})
            if request_form.is_valid():
                email = request_form.cleaned_data['email'].strip().lower()
                user, role, error = find_user_by_identity(email)
                if error or not user:
                    request_form.add_error('email', error or 'No account matched that email address.')
                else:
                    token = create_auth_otp(
                        purpose=OtpPurpose.LOGIN_EMAIL,
                        channel=OtpChannel.EMAIL,
                        user=user,
                        role=role or '',
                        email=email,
                    )
                    delivered, detail = send_email_otp(
                        email=email,
                        code=token.code,
                        subject='Your GramExpress email OTP',
                        intro='Use this OTP to continue into GramExpress without entering your password.',
                    )
                    if delivered:
                        request.session[PENDING_EMAIL_OTP_SESSION_KEY] = {
                            'user_id': user.id,
                            'email': email,
                            'role': role or '',
                        }
                        request.session.modified = True
                        verify_form = EmailOtpVerifyForm(initial={'email': email})
                        messages.success(request, 'We sent a 6 digit OTP to your email address.')
                    else:
                        token.delete()
                        request_form.add_error('email', detail)
        elif action in ['verify', 'resend']:
            pending_email_otp = request.session.get(PENDING_EMAIL_OTP_SESSION_KEY)
            if not pending_email_otp:
                messages.error(request, 'Your email OTP session expired. Request a new code.')
                return redirect('core:email_otp')

            email = pending_email_otp.get('email', '')
            user = get_user_model().objects.filter(pk=pending_email_otp.get('user_id')).first()
            if not user or not email:
                request.session.pop(PENDING_EMAIL_OTP_SESSION_KEY, None)
                messages.error(request, 'That email OTP session is no longer valid.')
                return redirect('core:email_otp')

            request_form = EmailOtpRequestForm(initial={'email': email})
            if action == 'resend':
                token = create_auth_otp(
                    purpose=OtpPurpose.LOGIN_EMAIL,
                    channel=OtpChannel.EMAIL,
                    user=user,
                    role=pending_email_otp.get('role', ''),
                    email=email,
                )
                delivered, detail = send_email_otp(
                    email=email,
                    code=token.code,
                    subject='Your GramExpress email OTP',
                    intro='Use this OTP to continue into GramExpress without entering your password.',
                )
                if delivered:
                    messages.success(request, 'A fresh OTP was sent to your email.')
                else:
                    token.delete()
                    messages.error(request, detail)
                verify_form = EmailOtpVerifyForm(initial={'email': email})
            else:
                verify_form = EmailOtpVerifyForm(request.POST)
                if verify_form.is_valid():
                    submitted_email = verify_form.cleaned_data['email'].strip().lower()
                    token = (
                        AuthOtpToken.objects.filter(
                            user=user,
                            purpose=OtpPurpose.LOGIN_EMAIL,
                            channel=OtpChannel.EMAIL,
                            email__iexact=submitted_email,
                            code=verify_form.cleaned_data['code'],
                            is_used=False,
                        )
                        .order_by('-created_at')
                        .first()
                    )
                    if submitted_email != email:
                        verify_form.add_error('email', 'Enter the same email address that received the OTP.')
                    elif token and token.is_valid:
                        token.is_used = True
                        token.save(update_fields=['is_used'])
                        request.session.pop(PENDING_EMAIL_OTP_SESSION_KEY, None)
                        login(request, user)
                        messages.success(request, 'Email OTP verified. Welcome back.')
                        return redirect(get_dashboard_url_for_user(user))
                    else:
                        verify_form.add_error('code', 'That OTP is invalid or expired.')

    pending_email_otp = request.session.get(PENDING_EMAIL_OTP_SESSION_KEY, {})
    return render(
        request,
        'core/email_otp.html',
        {
            'request_form': request_form,
            'verify_form': verify_form,
            'pending_email_otp': pending_email_otp,
            'pending_email_otp_masked_email': mask_email(pending_email_otp.get('email', '')) if pending_email_otp else '',
            'pending_email_otp_role_label': role_label(pending_email_otp.get('role', '')) if pending_email_otp else '',
            'otp_expiry_minutes': getattr(settings, 'OTP_EXPIRY_MINUTES', 10),
        },
    )


def logout_view(request: HttpRequest) -> HttpResponse:
    logout(request)
    request.session.pop(CART_SESSION_KEY, None)
    request.session.pop(PENDING_LOGIN_SESSION_KEY, None)
    request.session.pop(PENDING_REGISTRATION_SESSION_KEY, None)
    request.session.pop(PENDING_EMAIL_OTP_SESSION_KEY, None)
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
            'unread_count': sum(1 for note in notifications if not note.is_read),
            'total_count': len(notifications),
        },
    )


@login_required
def support_view(request: HttpRequest) -> HttpResponse:
    role, profile = get_role_profile(request.user)
    support_title = 'Customer Support'
    support_copy = 'Reach the GramExpress team for order help, payment questions, account issues, and delivery assistance.'
    if role == RoleType.SHOP:
        support_title = 'Store Support'
        support_copy = 'Get help with catalog issues, order operations, rider coordination, and store account updates.'
    elif role == RoleType.RIDER:
        support_title = 'Rider Support'
        support_copy = 'Use support for dispatch issues, payout questions, route problems, and profile assistance.'
    elif role == RoleType.ADMIN:
        support_title = 'Platform Support'
        support_copy = 'Administrative support for platform review, account issues, and operations questions.'

    return render(
        request,
        'core/support.html',
        {
            'support_title': support_title,
            'support_copy': support_copy,
            'support_name': getattr(profile, 'full_name', request.user.get_username()),
            'support_email': getattr(profile, 'email', request.user.email) or 'support@gramexpress.local',
            'support_phone': getattr(profile, 'phone', '+91 90000 00000'),
        },
    )


@login_required
@require_POST
def notifications_mark_all_read(request: HttpRequest) -> HttpResponse:
    notification_queryset_for_user(request.user).filter(is_read=False).update(is_read=True)
    messages.success(request, 'All notifications marked as read.')
    return redirect('core:notifications')


@login_required
@require_POST
def notification_mark_read(request: HttpRequest, notification_id: int) -> HttpResponse:
    note = get_object_or_404(notification_queryset_for_user(request.user), pk=notification_id)
    if not note.is_read:
        note.is_read = True
        note.save(update_fields=['is_read'])
        messages.success(request, 'Notification marked as read.')
    return redirect('core:notifications')


@login_required
@require_POST
def notification_delete(request: HttpRequest, notification_id: int) -> HttpResponse:
    note = get_object_or_404(notification_queryset_for_user(request.user), pk=notification_id)
    note.delete()
    messages.success(request, 'Notification deleted.')
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
    status_summary = build_order_status_summary(order)
    payment_summary = build_payment_summary(order)
    route_url = build_google_route_url(
        order.shop.latitude,
        order.shop.longitude,
        order.customer.latitude,
        order.customer.longitude,
    )
    maps_embed_url = build_google_embed_route_url(
        order.shop.latitude,
        order.shop.longitude,
        order.customer.latitude,
        order.customer.longitude,
    )
    if order.rider:
        order.rider_route_url = route_url
    return render(
        request,
        'core/order_detail.html',
        {
            'order': order,
            'timeline': timeline,
            'related_notifications': related_notifications,
            'show_customer_actions': get_role_profile(request.user)[0] == RoleType.CUSTOMER,
            'status_summary': status_summary,
            'payment_summary': payment_summary,
            'eta_label': build_order_eta_label(order),
            'route_url': route_url,
            'maps_embed_url': maps_embed_url,
        },
    )


@login_required
def order_tracking_view(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_order_for_user(request.user, order_id)
    order.subtotal_amount = order.total_amount - order.delivery_fee
    timeline = build_order_timeline(order)
    eta_label = build_order_eta_label(order)
    route_url = build_google_route_url(
        order.shop.latitude,
        order.shop.longitude,
        order.customer.latitude,
        order.customer.longitude,
    )
    maps_embed_url = build_google_embed_route_url(
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
            'maps_embed_url': maps_embed_url,
            'status_summary': build_order_status_summary(order),
            'payment_summary': build_payment_summary(order),
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
    context = customer_workspace_context(request)
    return disable_html_cache(render(request, 'core/customer_dashboard.html', context))


@role_required(RoleType.CUSTOMER)
def customer_store_detail_view(request: HttpRequest, shop_slug: str) -> HttpResponse:
    context = customer_workspace_context(request)
    if context['location_required']:
        messages.info(request, 'Fetch your current location to browse nearby stores.')
        return redirect('core:customer_dashboard')
    shop = next((candidate for candidate in context['shops'] if candidate.slug == shop_slug), None)
    if not shop:
        shop = get_object_or_404(
            Shop.objects.filter(
                approval_status=ApprovalStatus.APPROVED,
                is_open=True,
                slug=shop_slug,
            ).select_related('owner').prefetch_related('products')
        )
        set_distance(shop, request.role_profile.latitude, request.role_profile.longitude)
        if shop.distance_km > DEFAULT_DELIVERY_RADIUS_KM:
            raise Http404('Store not available in your delivery radius')

    product_query = request.GET.get('q', '').strip().lower()
    products = list(shop.products.all())
    if product_query:
        products = [
            product for product in products
            if product_query in f'{product.name} {product.subtitle} {product.category} {product.tag}'.lower()
        ]

    context.update(
        {
            'shop': shop,
            'products': products,
            'product_query': request.GET.get('q', '').strip(),
        }
    )
    return disable_html_cache(render(request, 'core/customer_store_detail.html', context))


@role_required(RoleType.CUSTOMER)
def customer_cart_view(request: HttpRequest) -> HttpResponse:
    context = customer_workspace_context(request)
    checkout_data = pending_checkout_data(request) or {'payment_method': PaymentMethod.COD, 'customer_notes': ''}
    context['order_form'] = CustomerOrderMetaForm(
        initial=checkout_data,
        enable_razorpay=context['razorpay_enabled'],
    )
    return render(request, 'core/customer_cart.html', context)


@role_required(RoleType.CUSTOMER)
def customer_orders_view(request: HttpRequest) -> HttpResponse:
    context = customer_workspace_context(request)
    context['rating_form'] = RatingForm()
    context['active_orders'] = [
        order for order in context['orders']
        if order.status not in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]
    ]
    context['previous_orders'] = [
        order for order in context['orders']
        if order.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]
    ]
    return render(request, 'core/customer_orders.html', context)


@role_required(RoleType.CUSTOMER)
def customer_profile_view(request: HttpRequest) -> HttpResponse:
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
            return redirect('core:customer_profile')
    else:
        profile_form = CustomerProfileForm(instance=customer)

    context = customer_workspace_context(request)
    context['profile_form'] = profile_form
    return render(request, 'core/customer_profile.html', context)


@role_required(RoleType.CUSTOMER)
@require_POST
def customer_update_location(request: HttpRequest) -> HttpResponse:
    customer = request.role_profile
    form = CustomerLocationForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Could not read your current location. Please try again.')
        return redirect('core:customer_dashboard')

    customer.latitude = form.cleaned_data['latitude']
    customer.longitude = form.cleaned_data['longitude']
    location_details = reverse_geocode_location(customer.latitude, customer.longitude)
    formatted_address = location_details.get('formatted_address', '').strip()
    if location_details.get('address_line_1'):
        customer.address_line_1 = location_details['address_line_1']
    if location_details.get('district'):
        customer.district = location_details['district']
    if location_details.get('pincode'):
        customer.pincode = location_details['pincode']
    customer.save(update_fields=['latitude', 'longitude', 'address_line_1', 'district', 'pincode', 'updated_at'])
    request.session[CUSTOMER_LOCATION_SESSION_KEY] = True
    request.session[CUSTOMER_LOCATION_LABEL_SESSION_KEY] = formatted_address or f'Latitude {customer.latitude}, Longitude {customer.longitude}'
    heading = location_details.get('locality') or location_details.get('city') or location_details.get('district') or customer.district or customer.address_line_1 or 'Current location'
    subtitle_parts = []
    city_or_district = location_details.get('city') or location_details.get('district') or customer.district
    if city_or_district and city_or_district != heading:
        subtitle_parts.append(city_or_district)
    if customer.pincode:
        subtitle_parts.append(customer.pincode)
    request.session[CUSTOMER_LOCATION_HEADING_SESSION_KEY] = heading
    request.session[CUSTOMER_LOCATION_SUBTITLE_SESSION_KEY] = ', '.join(part for part in subtitle_parts if part)
    request.session.modified = True
    if location_details:
        messages.success(request, 'Location fetched successfully. Stores near you are now updated.')
    else:
        messages.success(request, 'Location coordinates updated successfully.')
    return redirect('core:customer_dashboard')


@role_required(RoleType.CUSTOMER)
@require_POST
def cart_add(request: HttpRequest, product_id: int) -> HttpResponse:
    product = get_object_or_404(Product.objects.select_related('shop'), pk=product_id, shop__approval_status=ApprovalStatus.APPROVED)
    if not product.shop.is_open:
        messages.error(request, f'{product.shop.name} is currently closed for checkout.')
        return redirect(request.POST.get('next') or reverse('core:customer_store_detail', args=[product.shop.slug]))
    if product.stock <= 0:
        messages.error(request, f'{product.name} is currently out of stock.')
        return redirect(request.POST.get('next') or reverse('core:customer_store_detail', args=[product.shop.slug]))
    quantity = max(1, int(request.POST.get('quantity', 1)))
    cart = cart_from_session(request)
    cart[str(product.id)] = min(product.stock, cart.get(str(product.id), 0) + quantity)
    save_cart(request, cart)
    if quantity > product.stock:
        messages.info(request, f'{product.name} was capped to the available stock of {product.stock}.')
    else:
        messages.success(request, f'{product.name} added to your cart.')
    return redirect(request.POST.get('next') or reverse('core:customer_store_detail', args=[product.shop.slug]))


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
    return redirect(request.POST.get('next') or reverse('core:customer_cart'))


@role_required(RoleType.CUSTOMER)
@require_POST
def cart_clear(request: HttpRequest) -> HttpResponse:
    save_cart(request, {})
    messages.success(request, 'Cart cleared.')
    return redirect(request.POST.get('next') or reverse('core:customer_cart'))


@role_required(RoleType.CUSTOMER)
def customer_checkout(request: HttpRequest) -> HttpResponse:
    customer = request.role_profile
    cart = build_cart_context(request)
    razorpay_enabled = is_razorpay_ready()
    try:
        validate_checkout_cart(cart)
    except CheckoutValidationError as error:
        messages.error(request, str(error))
        return redirect('core:customer_cart')
    if request.method == 'POST':
        action = request.POST.get('action', 'review')
        if action == 'review':
            form = CustomerOrderMetaForm(request.POST, enable_razorpay=razorpay_enabled)
            if form.is_valid():
                checkout_data = {
                    'payment_method': form.cleaned_data['payment_method'],
                    'customer_notes': form.cleaned_data['customer_notes'],
                }
                save_pending_checkout(request, **checkout_data)
                if checkout_data['payment_method'] != PaymentMethod.RAZORPAY:
                    save_active_checkout_session(request, None)
            else:
                messages.error(request, 'Choose a valid payment method before checkout.')
                return redirect('core:customer_cart')
        elif action == 'confirm':
            checkout_data = pending_checkout_data(request)
            if not checkout_data:
                messages.error(request, 'Your checkout session expired. Please review the cart again.')
                return redirect('core:customer_cart')
            if checkout_data['payment_method'] != PaymentMethod.COD:
                messages.info(request, 'Use the Razorpay payment button to complete your online order.')
                return redirect('core:customer_checkout')

            checkout_session = create_cod_checkout_session(customer=customer, cart=cart, checkout_data=checkout_data)
            try:
                created_orders = finalize_checkout_session(checkout_session)
            except CheckoutValidationError as error:
                checkout_session.failure_reason = str(error)
                checkout_session.save(update_fields=['failure_reason', 'updated_at'])
                messages.error(request, str(error))
                refreshed_cart = build_cart_context(request)
                context = build_checkout_context(
                    customer=customer,
                    cart=refreshed_cart,
                    checkout_data=checkout_data,
                    checkout_session=checkout_session,
                )
                context['order_form'] = CustomerOrderMetaForm(initial=checkout_data, enable_razorpay=razorpay_enabled)
                return render(request, 'core/checkout_review.html', context)

            save_cart(request, {})
            set_last_checkout_payload(
                request,
                orders=created_orders,
                payment_method=checkout_data['payment_method'],
                checkout_session=checkout_session,
            )
            clear_pending_checkout(request)
            messages.success(request, f'{len(created_orders)} order(s) placed across your selected stores.')
            return redirect('core:customer_checkout_success')
    checkout_data = pending_checkout_data(request)
    if not checkout_data:
        checkout_data = {
            'payment_method': PaymentMethod.COD,
            'customer_notes': '',
        }

    checkout_session = None
    if checkout_data.get('payment_method') == PaymentMethod.RAZORPAY and razorpay_enabled:
        try:
            checkout_session = get_or_create_online_checkout_session(
                request=request,
                customer=customer,
                cart=cart,
                checkout_data=checkout_data,
            )
        except CheckoutValidationError as error:
            messages.error(request, str(error))

    context = build_checkout_context(
        customer=customer,
        cart=cart,
        checkout_data=checkout_data,
        checkout_session=checkout_session,
    )
    context['order_form'] = CustomerOrderMetaForm(initial=checkout_data, enable_razorpay=razorpay_enabled)
    return render(request, 'core/checkout_review.html', context)


@role_required(RoleType.CUSTOMER)
@require_POST
def customer_razorpay_complete(request: HttpRequest) -> HttpResponse:
    customer = request.role_profile
    checkout_session = get_object_or_404(
        CheckoutSession.objects.select_related('customer'),
        pk=request.POST.get('checkout_session_id'),
        customer=customer,
        payment_method=PaymentMethod.RAZORPAY,
    )
    if checkout_session.is_completed:
        set_last_checkout_payload(
            request,
            orders=list(checkout_session.orders.all()),
            payment_method=checkout_session.payment_method,
            checkout_session=checkout_session,
        )
        save_cart(request, {})
        clear_pending_checkout(request)
        return redirect('core:customer_checkout_success')

    razorpay_payment_id = request.POST.get('razorpay_payment_id', '').strip()
    razorpay_order_id = request.POST.get('razorpay_order_id', '').strip()
    razorpay_signature = request.POST.get('razorpay_signature', '').strip()
    if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
        messages.error(request, 'Razorpay did not return the payment confirmation details.')
        return redirect('core:customer_checkout')
    if razorpay_order_id != checkout_session.razorpay_order_id:
        messages.error(request, 'The payment order did not match this checkout session.')
        return redirect('core:customer_checkout')
    if not verify_razorpay_payment_signature(
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        razorpay_signature=razorpay_signature,
    ):
        checkout_session.payment_status = PaymentStatus.FAILED
        checkout_session.failure_reason = 'Payment signature verification failed.'
        checkout_session.save(update_fields=['payment_status', 'failure_reason', 'updated_at'])
        messages.error(request, 'We could not verify the payment signature. Please try again.')
        return redirect('core:customer_checkout')

    try:
        razorpay_payment = fetch_razorpay_payment(razorpay_payment_id)
        razorpay_order = fetch_razorpay_order(razorpay_order_id)
    except CheckoutValidationError as error:
        messages.error(request, str(error))
        return redirect('core:customer_checkout')

    expected_amount = int((checkout_session.amount * 100).quantize(Decimal('1')))
    payment_status = razorpay_payment.get('status', '')
    if (
        razorpay_payment.get('order_id') != razorpay_order_id
        or razorpay_order.get('id') != razorpay_order_id
        or int(razorpay_order.get('amount', 0)) != expected_amount
        or int(razorpay_payment.get('amount', 0)) != expected_amount
        or payment_status not in ['authorized', 'captured']
    ):
        checkout_session.payment_status = PaymentStatus.FAILED
        checkout_session.failure_reason = 'Razorpay payment verification did not pass all checks.'
        checkout_session.save(update_fields=['payment_status', 'failure_reason', 'updated_at'])
        messages.error(request, 'Payment verification failed. No order was created.')
        return redirect('core:customer_checkout')

    checkout_session.razorpay_payment_id = razorpay_payment_id
    checkout_session.razorpay_signature = razorpay_signature
    checkout_session.payment_status = PaymentStatus.PAID
    checkout_session.failure_reason = ''
    checkout_session.save(
        update_fields=['razorpay_payment_id', 'razorpay_signature', 'payment_status', 'failure_reason', 'updated_at']
    )

    try:
        created_orders = finalize_checkout_session(checkout_session)
    except CheckoutValidationError as error:
        checkout_session.failure_reason = str(error)
        checkout_session.save(update_fields=['failure_reason', 'updated_at'])
        messages.error(request, f'Payment was verified, but order creation needs manual review: {error}')
        return redirect('core:customer_cart')

    save_cart(request, {})
    set_last_checkout_payload(
        request,
        orders=created_orders,
        payment_method=checkout_session.payment_method,
        checkout_session=checkout_session,
    )
    clear_pending_checkout(request)
    messages.success(request, f'Payment confirmed and {len(created_orders)} order(s) were placed successfully.')
    return redirect('core:customer_checkout_success')


@role_required(RoleType.CUSTOMER)
@require_POST
def customer_razorpay_failed(request: HttpRequest) -> HttpResponse:
    checkout_session = get_object_or_404(
        CheckoutSession,
        pk=request.POST.get('checkout_session_id'),
        customer=request.role_profile,
        payment_method=PaymentMethod.RAZORPAY,
    )
    error_message = (
        request.POST.get('error_description')
        or request.POST.get('error_reason')
        or 'The online payment was not completed.'
    )
    checkout_session.payment_status = PaymentStatus.FAILED
    checkout_session.failure_reason = error_message[:240]
    checkout_session.save(update_fields=['payment_status', 'failure_reason', 'updated_at'])
    messages.error(request, checkout_session.failure_reason)
    return redirect('core:customer_checkout')


@csrf_exempt
@require_POST
def razorpay_webhook(request: HttpRequest) -> HttpResponse:
    payload = request.body
    signature = request.headers.get('X-Razorpay-Signature', '')
    if not verify_razorpay_webhook_signature(payload=payload, signature=signature):
        return JsonResponse({'status': 'invalid signature'}, status=400)

    event_payload = json.loads(payload.decode('utf-8'))
    event_name = event_payload.get('event', '')
    payment_entity = event_payload.get('payload', {}).get('payment', {}).get('entity', {})
    order_entity = event_payload.get('payload', {}).get('order', {}).get('entity', {})
    razorpay_order_id = payment_entity.get('order_id') or order_entity.get('id')
    if not razorpay_order_id:
        return JsonResponse({'status': 'ignored'})

    checkout_session = CheckoutSession.objects.filter(razorpay_order_id=razorpay_order_id).first()
    if not checkout_session:
        return JsonResponse({'status': 'ignored'})

    if event_name in ['payment.captured', 'order.paid']:
        checkout_session.razorpay_payment_id = payment_entity.get('id', checkout_session.razorpay_payment_id)
        checkout_session.payment_status = PaymentStatus.PAID
        checkout_session.failure_reason = ''
        checkout_session.save(update_fields=['razorpay_payment_id', 'payment_status', 'failure_reason', 'updated_at'])
        try:
            finalize_checkout_session(checkout_session)
        except CheckoutValidationError as error:
            checkout_session.failure_reason = str(error)
            checkout_session.save(update_fields=['failure_reason', 'updated_at'])
            return JsonResponse({'status': 'manual_review'}, status=202)
    elif event_name == 'payment.failed':
        error_message = (
            payment_entity.get('error_description')
            or payment_entity.get('error_reason')
            or 'The online payment failed.'
        )
        checkout_session.payment_status = PaymentStatus.FAILED
        checkout_session.failure_reason = error_message[:240]
        checkout_session.save(update_fields=['payment_status', 'failure_reason', 'updated_at'])

    return JsonResponse({'status': 'ok'})


@role_required(RoleType.CUSTOMER)
def customer_checkout_success(request: HttpRequest) -> HttpResponse:
    payload = request.session.get(LAST_CHECKOUT_SESSION_KEY)
    if not payload:
        messages.info(request, 'Place an order first to view the checkout success screen.')
        return redirect('core:customer_dashboard')

    orders = list(
        request.role_profile.orders.filter(pk__in=payload.get('order_ids', []))
        .select_related('shop', 'rider', 'checkout_session')
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
            'checkout_session': (
                CheckoutSession.objects.filter(pk=payload.get('checkout_session_id')).first()
                if payload.get('checkout_session_id')
                else None
            ),
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
            notification_type=NotificationType.ORDER,
        )
        if order.rider:
            create_notification(
                rider=order.rider,
                order=order,
                title='Delivery completed and rated',
                body=f'Customer rated order #{order.id} with {order.customer_rating}/5.',
                notification_type=NotificationType.RIDER,
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
                notification_type=NotificationType.ORDER,
            )
        create_notification(
            shop_owner=locked_order.shop.owner,
            order=locked_order,
            title='Customer cancelled order',
            body=f'{locked_order.display_id} was cancelled. Reason: {cancellation_reason}',
            notification_type=NotificationType.ORDER,
        )
        create_notification(
            customer=request.role_profile,
            order=locked_order,
            title='Order cancelled',
            body=f'{locked_order.display_id} was cancelled successfully.',
            notification_type=NotificationType.ORDER,
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
    context = shop_workspace_context(request)
    return render(request, 'core/shop_dashboard.html', context)


@role_required(RoleType.SHOP)
def shop_orders_view(request: HttpRequest) -> HttpResponse:
    context = shop_workspace_context(request)
    context['store_rating_form'] = StoreRatingForm()
    return render(request, 'core/shop_orders.html', context)


@role_required(RoleType.SHOP)
def shop_products_view(request: HttpRequest) -> HttpResponse:
    context = shop_workspace_context(request, editing_product_id=request.GET.get('edit_product'))
    shop = context['shop']
    editing_product = context['editing_product']
    if request.method == 'POST':
        target_product = editing_product if request.POST.get('product_id') else None
        product_form = ProductForm(request.POST, instance=target_product)
        if product_form.is_valid():
            product = product_form.save(commit=False)
            product.shop = shop
            product.save()
            messages.success(request, 'Product saved successfully.')
            return redirect('core:shop_products')
    else:
        product_form = ProductForm(instance=editing_product)
    context['product_form'] = product_form
    return render(request, 'core/shop_products.html', context)


@role_required(RoleType.SHOP)
def shop_settings_view(request: HttpRequest) -> HttpResponse:
    context = shop_workspace_context(request)
    shop = context['shop']
    if request.method == 'POST' and request.POST.get('action') == 'update_shop':
        shop_form = ShopUpdateForm(request.POST, request.FILES, instance=shop)
        if shop_form.is_valid():
            updated_shop = shop_form.save(commit=False)
            if updated_shop.approval_status != ApprovalStatus.APPROVED:
                updated_shop.approval_status = ApprovalStatus.PENDING
                updated_shop.is_open = False
            updated_shop.save()
            create_notification(
                shop_owner=request.role_profile,
                title='Store profile updated',
                body='Your store details changed and may need a fresh approval review.',
                notification_type=NotificationType.STORE,
            )
            messages.success(request, 'Shop details updated.')
            return redirect('core:shop_settings')
    else:
        shop_form = ShopUpdateForm(instance=shop)
    context['shop_form'] = shop_form
    return render(request, 'core/shop_settings.html', context)


@role_required(RoleType.SHOP)
@require_POST
def shop_delete_product(request: HttpRequest, product_id: int) -> HttpResponse:
    product = get_object_or_404(Product, pk=product_id, shop__owner=request.role_profile)
    product.delete()
    messages.success(request, 'Product deleted.')
    return redirect('core:shop_products')


@role_required(RoleType.SHOP)
@require_POST
def shop_update_order_status(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(Order, pk=order_id, shop__owner=request.role_profile)
    next_status = request.POST.get('status')
    cancellation_reason = request.POST.get('cancellation_reason', '').strip()
    if next_status not in {OrderStatus.CONFIRMED, OrderStatus.PACKED, OrderStatus.CANCELLED}:
        messages.error(request, 'Invalid order status transition.')
        return redirect('core:shop_orders')

    with transaction.atomic():
        locked_order = Order.objects.select_for_update().select_related('rider', 'customer', 'shop__owner').get(pk=order.pk)
        current_status = locked_order.status

        valid_transitions = {
            OrderStatus.CONFIRMED: {OrderStatus.PENDING, OrderStatus.CONFIRMED},
            OrderStatus.PACKED: {OrderStatus.CONFIRMED, OrderStatus.PACKED},
            OrderStatus.CANCELLED: {OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PACKED},
        }
        if current_status not in valid_transitions[next_status]:
            messages.error(
                request,
                f'Cannot move an order from {locked_order.get_status_display()} to {dict(OrderStatus.choices).get(next_status, next_status)}.',
            )
            return redirect('core:shop_orders')

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
        notification_type=NotificationType.ORDER,
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
            notification_type=NotificationType.RIDER,
        )
    messages.success(request, f'Order #{locked_order.id} moved to {locked_order.get_status_display()}.')
    return redirect('core:shop_orders')


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
            notification_type=NotificationType.RIDER,
        )
        messages.success(request, 'Rider rating saved.')
    else:
        messages.error(request, 'This delivery cannot be rated right now.')
    return redirect('core:shop_orders')

@role_required(RoleType.RIDER)
def rider_dashboard(request: HttpRequest) -> HttpResponse:
    context = rider_workspace_context(request)
    return render(request, 'core/rider_dashboard.html', context)


@role_required(RoleType.RIDER)
def rider_deliveries_view(request: HttpRequest) -> HttpResponse:
    context = rider_workspace_context(request)
    return render(request, 'core/rider_deliveries.html', context)


@role_required(RoleType.RIDER)
def rider_profile_view(request: HttpRequest) -> HttpResponse:
    rider = request.role_profile
    if request.method == 'POST' and request.POST.get('action') == 'toggle_availability':
        if rider.approval_status != ApprovalStatus.APPROVED:
            messages.error(request, 'Admin approval is required before you can go live for dispatch.')
            return redirect('core:rider_profile')
        rider.is_available = request.POST.get('is_available') == 'on'
        rider.save(update_fields=['is_available', 'updated_at'])
        messages.success(request, 'Rider availability updated.')
        return redirect('core:rider_profile')

    context = rider_workspace_context(request)
    return render(request, 'core/rider_profile.html', context)


@role_required(RoleType.RIDER)
@require_POST
def rider_update_location(request: HttpRequest) -> HttpResponse:
    rider = request.role_profile
    form = RiderLocationForm(request.POST)
    if form.is_valid():
        rider.latitude = form.cleaned_data['latitude']
        rider.longitude = form.cleaned_data['longitude']
        rider.save(update_fields=['latitude', 'longitude', 'updated_at'])
        messages.success(request, 'Live location updated for your active delivery workspace.')
    else:
        messages.error(request, 'Could not update location.')
    return redirect('core:rider_profile')


@role_required(RoleType.RIDER)
@require_POST
def rider_accept_order(request: HttpRequest, order_id: int) -> HttpResponse:
    rider = request.role_profile
    if rider.approval_status != ApprovalStatus.APPROVED or not rider.is_available:
        messages.error(request, 'Only approved and available riders can accept new orders.')
        return redirect('core:rider_deliveries')

    with transaction.atomic():
        locked_rider = RiderProfile.objects.select_for_update().get(pk=rider.pk)
        if locked_rider.approval_status != ApprovalStatus.APPROVED or not locked_rider.is_available:
            messages.error(request, 'This rider account is no longer available for dispatch.')
            return redirect('core:rider_deliveries')

        locked_order = Order.objects.select_for_update().select_related('shop__owner', 'customer').filter(pk=order_id).first()
        if not locked_order or locked_order.rider_id is not None:
            messages.error(request, 'That order was already claimed by another rider.')
            return redirect('core:rider_deliveries')
        if locked_order.status not in [OrderStatus.CONFIRMED, OrderStatus.PACKED]:
            messages.error(request, 'This order is no longer ready for rider acceptance.')
            return redirect('core:rider_deliveries')

        locked_order.rider = locked_rider
        if locked_order.status == OrderStatus.CONFIRMED:
            locked_order.status = OrderStatus.PACKED
        locked_order.save(update_fields=['rider', 'status', 'updated_at'])
        locked_rider.is_available = False
        locked_rider.save(update_fields=['is_available', 'updated_at'])

    create_notification(
        customer=locked_order.customer,
        order=locked_order,
        title='Rider assigned',
        body=f'{locked_rider.full_name} accepted order #{locked_order.id}.',
        notification_type=NotificationType.RIDER,
    )
    create_notification(
        shop_owner=locked_order.shop.owner,
        order=locked_order,
        title='Rider assigned',
        body=f'{locked_rider.full_name} accepted order #{locked_order.id}.',
        notification_type=NotificationType.RIDER,
    )
    messages.success(request, f'Order #{locked_order.id} assigned to {locked_rider.full_name}.')
    return redirect('core:rider_deliveries')


@role_required(RoleType.RIDER)
@require_POST
def rider_update_order_status(request: HttpRequest, order_id: int) -> HttpResponse:
    rider = request.role_profile
    if rider.approval_status != ApprovalStatus.APPROVED:
        messages.error(request, 'Admin approval is required before completing deliveries.')
        return redirect('core:rider_deliveries')
    next_status = request.POST.get('status')
    otp = request.POST.get('customer_otp', '').strip()

    if next_status not in {OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED}:
        messages.error(request, 'Invalid rider status transition.')
        return redirect('core:rider_deliveries')

    with transaction.atomic():
        locked_rider = RiderProfile.objects.select_for_update().get(pk=rider.pk)
        locked_order = get_object_or_404(
            Order.objects.select_for_update().select_related('customer', 'shop__owner', 'shop'),
            pk=order_id,
            rider=locked_rider,
        )

        if next_status == OrderStatus.OUT_FOR_DELIVERY:
            if locked_order.status not in [OrderStatus.CONFIRMED, OrderStatus.PACKED]:
                messages.error(request, 'This order is not ready for pickup confirmation.')
                return redirect('core:rider_deliveries')

            pickup_distance_km = kilometers_between(
                locked_rider.latitude,
                locked_rider.longitude,
                locked_order.shop.latitude,
                locked_order.shop.longitude,
            )
            if pickup_distance_km > PICKUP_GEOFENCE_KM:
                messages.error(
                    request,
                    f'Get closer to the store to mark pickup. You are {pickup_distance_km} km away.',
                )
                return redirect('core:rider_deliveries')

            locked_order.status = OrderStatus.OUT_FOR_DELIVERY
            locked_order.save(update_fields=['status', 'updated_at'])
            status_message = 'picked up and is now out for delivery'
            success_message = f'Order #{locked_order.id} marked as Out For Delivery.'
        else:
            if locked_order.status != OrderStatus.OUT_FOR_DELIVERY:
                messages.error(request, 'This order must be out for delivery before completion.')
                return redirect('core:rider_deliveries')
            if otp != locked_order.customer_otp:
                messages.error(request, 'Customer OTP did not match.')
                return redirect('core:rider_deliveries')

            locked_order.status = OrderStatus.DELIVERED
            locked_order.delivered_at = timezone.now()
            locked_order.save(update_fields=['status', 'updated_at', 'delivered_at'])
            locked_rider.is_available = True
            locked_rider.save(update_fields=['is_available', 'updated_at'])
            status_message = 'was delivered successfully'
            success_message = f'Order #{locked_order.id} moved to Delivered.'

    create_notification(
        customer=locked_order.customer,
        order=locked_order,
        title='Delivery status updated',
        body=f'Order #{locked_order.id} {status_message}.',
        notification_type=NotificationType.RIDER,
    )
    create_notification(
        shop_owner=locked_order.shop.owner,
        order=locked_order,
        title='Delivery status updated',
        body=f'Order #{locked_order.id} {status_message}.',
        notification_type=NotificationType.RIDER,
    )
    messages.success(request, success_message)
    return redirect('core:rider_deliveries')

@require_GET
def manifest(request: HttpRequest) -> JsonResponse:
    response = JsonResponse(
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
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response


@require_GET
def service_worker(_: HttpRequest) -> HttpResponse:
    asset_version = getattr(settings, 'APP_ASSET_VERSION', '1')
    cache_name = f'gramexpress-shell-v{asset_version}'
    assets = [
        f'/manifest.json?v={asset_version}',
        f'/static/core/styles.css?v={asset_version}',
        f'/static/core/icon.svg?v={asset_version}',
        f'/static/core/icon-maskable.svg?v={asset_version}',
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

  const requestUrl = new URL(event.request.url);
  if (event.request.mode === 'navigate' || requestUrl.pathname.startsWith('/customer/') || requestUrl.pathname.startsWith('/shop/') || requestUrl.pathname.startsWith('/rider/')) {{
    event.respondWith(fetch(event.request).catch(() => caches.match('/auth/login/')));
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
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response
