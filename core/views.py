import base64
import hashlib
import hmac
import json
import math
import random
import re
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from functools import wraps
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from uuid import uuid4

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Avg, Count
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

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
    CodCollectionMode,
    CheckoutSession,
    CustomerProfile,
    DEFAULT_DELIVERY_SLOT,
    DEFAULT_DELIVERY_FEE,
    DELIVERY_SLOT_RULES,
    DeliverySlot,
    EmailOtpToken,
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
    OtpChannel,
    OtpPurpose,
    PaymentMethod,
    PaymentStatus,
    Product,
    RiderProfile,
    RoleType,
    SettlementStatus,
    Shop,
    ShopOwnerProfile,
    delivery_slot_deadline_from,
    delivery_slot_fee,
    delivery_slot_rule,
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
RIDER_COMMISSION_PER_DELIVERY = Decimal('15.00')
RIDER_LONG_DISTANCE_INCENTIVE = Decimal('5.00')
RIDER_PEAK_HOUR_INCENTIVE = Decimal('5.00')
RIDER_KHATABOOK_COLLECTION_INCENTIVE = Decimal('25.00')
RIDER_HIGH_COMPLETION_BONUS_TIERS = (
    (120, Decimal('2000.00')),
    (90, Decimal('1500.00')),
    (60, Decimal('900.00')),
    (30, Decimal('400.00')),
)
KHATABOOK_COLLECTION_GEOFENCE_KM = 0.3
SHOPKEEPER_COMMISSION_FEE = Decimal('5.00')
GRAMEXPRESS_PLATFORM_FEE = Decimal('5.00')
ACCOUNT_ROLE_CHOICES = [RoleType.CUSTOMER, RoleType.SHOP, RoleType.RIDER]
REGISTRATION_ROLE_DESCRIPTIONS = {
    RoleType.CUSTOMER: 'Browse local stores, save your address, and place deliveries quickly.',
    RoleType.SHOP: 'Launch your store workspace with catalogue, order queue, and shop profile details.',
    RoleType.RIDER: 'Set up your rider workspace with vehicle details and delivery-ready location access.',
}
REGISTRATION_ROLE_ONBOARDING_COPY = {
    RoleType.CUSTOMER: 'Add the delivery details we need to match you with nearby stores and route your orders accurately.',
    RoleType.SHOP: 'Add your store and service area details so the shop dashboard opens with the right onboarding data.',
    RoleType.RIDER: 'Share only the rider essentials for now. You can complete the rest inside your dashboard later.',
}
TWILIO_API_BASE = 'https://api.twilio.com/2010-04-01/Accounts'
RAZORPAY_API_BASE = 'https://api.razorpay.com/v1'
PHONE_SANITIZER = re.compile(r'\D')
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
    'state',
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
    'photo_url',
]


class CheckoutValidationError(Exception):
    pass


def normalize_phone(phone: str) -> str:
    phone = PHONE_SANITIZER.sub('', (phone or '').strip())
    if phone.startswith('91') and len(phone) == 12:
        phone = phone[2:]
    if phone.startswith('0') and len(phone) == 11:
        phone = phone[1:]
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


def registration_role_links(*, full_name: str = '', email: str = '', selected_role: str = '') -> list[dict[str, str]]:
    links = []
    for role in ACCOUNT_ROLE_CHOICES:
        query = {'account_type': role}
        if full_name:
            query['full_name'] = full_name
        if email:
            query['email'] = email
        links.append(
            {
                'value': role,
                'label': role_label(role),
                'description': REGISTRATION_ROLE_DESCRIPTIONS.get(role, ''),
                'url': f'{reverse("core:register_details")}?{urllib_parse.urlencode(query)}',
                'selected': role == selected_role,
            }
        )
    return links


def registration_details_template(selected_role: str) -> str:
    return {
        RoleType.CUSTOMER: 'core/register_details_customer.html',
        RoleType.SHOP: 'core/register_details_shop.html',
        RoleType.RIDER: 'core/register_details_rider.html',
    }.get(selected_role, 'core/register_details.html')


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


def contact_conflicts(*, phone: str, email: str) -> dict[str, bool]:
    phone = normalize_phone(phone)
    email = (email or '').strip().lower()
    phone_conflict = any(
        [
            CustomerProfile.objects.filter(phone=phone, user__isnull=False).exists(),
            ShopOwnerProfile.objects.filter(phone=phone, user__isnull=False).exists(),
            RiderProfile.objects.filter(phone=phone, user__isnull=False).exists(),
        ]
    )
    email_conflict = bool(email) and any(
        [
            CustomerProfile.objects.filter(email__iexact=email, user__isnull=False).exists(),
            ShopOwnerProfile.objects.filter(email__iexact=email, user__isnull=False).exists(),
            RiderProfile.objects.filter(email__iexact=email, user__isnull=False).exists(),
        ]
    )
    return {
        'phone': phone_conflict,
        'email': email_conflict,
    }


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
    backend = getattr(settings, 'EMAIL_BACKEND', '').lower()
    message = f'{intro}\n\nOTP: {code}\nThis code expires in {getattr(settings, "OTP_EXPIRY_MINUTES", 10)} minutes.'
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@gramexpress.local'),
            recipient_list=[email],
            fail_silently=False,
        )
        if backend == 'django.core.mail.backends.console.emailbackend':
            print(f'[GramExpress EMAIL OTP] {email}: OTP {code} (valid {getattr(settings, "OTP_EXPIRY_MINUTES", 10)} min)')
            return True, 'Email OTP generated with console email backend.'
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


def generate_delivery_otp() -> str:
    return f'{random.randint(0, 999999):06d}'


def delivery_otp_expiry_minutes() -> int:
    return int(getattr(settings, 'DELIVERY_OTP_EXPIRY_MINUTES', 15))


def delivery_otp_resend_cooldown_seconds() -> int:
    return int(getattr(settings, 'DELIVERY_OTP_RESEND_COOLDOWN_SECONDS', 45))


def delivery_otp_reference_notification(order: Order):
    return (
        order.notifications.filter(
            notification_type=NotificationType.RIDER,
            title__in=['Delivery status updated', 'Delivery OTP resent'],
        )
        .order_by('-created_at')
        .first()
    )


def delivery_otp_valid_until(order: Order):
    reference = delivery_otp_reference_notification(order)
    anchor = reference.created_at if reference else order.updated_at
    return anchor + timezone.timedelta(minutes=delivery_otp_expiry_minutes())


def delivery_otp_is_expired(order: Order) -> bool:
    return order.status == OrderStatus.OUT_FOR_DELIVERY and timezone.now() > delivery_otp_valid_until(order)


def send_customer_delivery_otp_sms(*, order: Order, intro: str) -> tuple[bool, str]:
    return send_sms_otp(phone=order.customer.phone, code=order.customer_otp, intro=intro)


def send_customer_khatabook_collection_otp_sms(
    *,
    collection_request: KhataBookCollectionRequest,
    intro: str,
) -> tuple[bool, str]:
    return send_sms_otp(phone=collection_request.customer.phone, code=collection_request.collection_otp, intro=intro)


def send_customer_khatabook_collection_otp_email(
    *,
    collection_request: KhataBookCollectionRequest,
    rider: RiderProfile,
) -> tuple[bool, str]:
    recipient = (collection_request.customer.email or '').strip()
    if not recipient:
        return False, 'No customer email is available for this KhataBook collection.'

    message = '\n'.join(
        [
            'Your GramExpress KhataBook repayment rider is on the way.',
            '',
            f'Collection request: {collection_request.display_id}',
            f'Rider: {rider.full_name}',
            f'Amount: Rs. {collection_request.amount}',
            f'Repayment OTP: {collection_request.collection_otp}',
            '',
            'Share this OTP only when the rider arrives to collect the KhataBook repayment.',
        ]
    )
    try:
        send_mail(
            subject=f'KhataBook repayment OTP for {collection_request.display_id}',
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@gramexpress.local'),
            recipient_list=[recipient],
            fail_silently=False,
        )
        return True, 'KhataBook collection OTP email sent successfully.'
    except Exception:
        return False, 'KhataBook collection OTP email could not be sent with the current mail settings.'


def ensure_khatabook_collection_otp_ready(
    *,
    collection_request: KhataBookCollectionRequest,
    rider: RiderProfile,
    force_new: bool = False,
) -> tuple[bool, bool]:
    updates = []
    if force_new or not collection_request.collection_otp:
        collection_request.collection_otp = generate_delivery_otp()
        updates.append('collection_otp')
    if updates:
        collection_request.save(update_fields=[*updates, 'updated_at'])

    customer_email = (collection_request.customer.email or '').strip() or 'Unavailable'
    print(
        '[GramExpress KhataBook OTP] '
        f'{collection_request.display_id}: '
        f'Rider {rider.full_name} | '
        f'Customer email {customer_email} | '
        f'Repayment OTP {collection_request.collection_otp}'
    )

    otp_email_sent, _ = send_customer_khatabook_collection_otp_email(
        collection_request=collection_request,
        rider=rider,
    )
    otp_sms_sent, _ = send_customer_khatabook_collection_otp_sms(
        collection_request=collection_request,
        intro='Your GramExpress rider is ready for KhataBook repayment collection.',
    )
    create_notification(
        customer=collection_request.customer,
        title='KhataBook repayment OTP sent',
        body=(
            f'A 6-digit repayment OTP was sent for {collection_request.display_id}. '
            'Share it only when the rider arrives to collect the KhataBook due.'
        ),
        notification_type=NotificationType.PAYMENT,
    )
    create_notification(
        rider=rider,
        title='KhataBook OTP ready',
        body=f'Ask the customer for the repayment OTP sent for {collection_request.display_id} before closing the collection.',
        notification_type=NotificationType.PAYMENT,
    )
    return otp_email_sent, otp_sms_sent


def first_order_notification(
    order: Order,
    *,
    title: str | None = None,
    title_in: list[str] | tuple[str, ...] | None = None,
    notification_type: str | None = None,
    body_contains: str | None = None,
    body_contains_any: list[str] | tuple[str, ...] | None = None,
):
    queryset = order.notifications.all()
    if notification_type:
        queryset = queryset.filter(notification_type=notification_type)
    if title:
        queryset = queryset.filter(title=title)
    elif title_in:
        queryset = queryset.filter(title__in=title_in)

    for note in queryset.order_by('created_at'):
        body = (note.body or '').lower()
        if body_contains and body_contains.lower() not in body:
            continue
        if body_contains_any and not any(snippet.lower() in body for snippet in body_contains_any):
            continue
        return note
    return None


def short_relative_time(moment):
    if not moment:
        return ''

    delta = timezone.now() - moment
    total_minutes = max(int(delta.total_seconds() // 60), 0)
    if total_minutes < 1:
        return 'just now'
    if total_minutes < 60:
        return f'{total_minutes} min ago'

    total_hours = total_minutes // 60
    if total_hours < 24:
        return f'{total_hours} hr ago' if total_hours == 1 else f'{total_hours} hrs ago'

    total_days = total_hours // 24
    return f'{total_days} day ago' if total_days == 1 else f'{total_days} days ago'


def elapsed_time_label(moment):
    if not moment:
        return 'Just now'

    delta = timezone.now() - moment
    total_minutes = max(int(delta.total_seconds() // 60), 0)
    if total_minutes < 1:
        return 'Under 1 min'
    if total_minutes < 60:
        return f'{total_minutes} min'

    total_hours, minutes = divmod(total_minutes, 60)
    if total_hours < 24:
        return f'{total_hours} hr {minutes} min' if minutes else f'{total_hours} hr'

    total_days, hours = divmod(total_hours, 24)
    return f'{total_days} day {hours} hr' if hours else f'{total_days} day'


def build_order_milestone_timestamps(order: Order) -> dict[str, Any]:
    rider_assigned_note = first_order_notification(
        order,
        title='Rider assigned',
        notification_type=NotificationType.RIDER,
    )
    pickup_note = first_order_notification(
        order,
        title='Delivery status updated',
        notification_type=NotificationType.RIDER,
        body_contains_any=['pickup was confirmed', 'picked up by', 'picked up and is now on the way'],
    )
    delivered_note = first_order_notification(
        order,
        title='Delivery status updated',
        notification_type=NotificationType.RIDER,
        body_contains_any=['delivered successfully'],
    )
    cancelled_note = first_order_notification(
        order,
        title_in=['Order cancelled', 'Customer cancelled order', 'Store updated your order'],
        body_contains='cancel',
    )
    return {
        'placed': order.created_at,
        'accepted': rider_assigned_note.created_at if rider_assigned_note else None,
        'pickup': pickup_note.created_at if pickup_note else None,
        'delivered': delivered_note.created_at if delivered_note else order.delivered_at,
        'cancelled': cancelled_note.created_at if cancelled_note else (order.updated_at if order.status == OrderStatus.CANCELLED else None),
    }


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
                'state': cleaned_data.get('state', ''),
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
            'photo_url': cleaned_data.get('photo_url', ''),
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


def build_google_embed_place_url(latitude: Decimal, longitude: Decimal) -> str:
    api_key = getattr(settings, 'GOOGLE_MAPS_EMBED_API_KEY', '')
    if not api_key:
        return ''
    return (
        'https://www.google.com/maps/embed/v1/place'
        f'?key={urllib_parse.quote(api_key)}'
        f'&q={latitude},{longitude}'
        '&zoom=18'
    )


RIDER_PHOTO_MAX_BYTES = 2 * 1024 * 1024
RIDER_PHOTO_EXTENSIONS = {
    'image/jpeg': 'jpg',
    'image/jpg': 'jpg',
    'image/png': 'png',
    'image/webp': 'webp',
}
RIDER_LIVE_CAPTURE_SOURCE = 'front_selfie_live'


def rider_profile_payload(rider: RiderProfile) -> dict[str, Any]:
    return {
        'id': rider.id,
        'name': rider.full_name,
        'phone': rider.phone,
        'email': rider.email,
        'vehicle_type': rider.vehicle_type,
        'vehicle_type_label': rider.get_vehicle_type_display(),
        'photo_url': rider.photo_source,
        'is_verified': rider.approval_status == ApprovalStatus.APPROVED,
        'approval_status': rider.approval_status,
        'updated_at': rider.updated_at.isoformat(),
    }


def rider_photo_extension_for_content_type(content_type: str) -> str | None:
    return RIDER_PHOTO_EXTENSIONS.get((content_type or '').lower())


def extract_rider_capture_context(request: HttpRequest) -> tuple[str, str]:
    if request.content_type and request.content_type.startswith('application/json') and request.body:
        try:
            payload = json.loads(request.body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return '', ''
        return (
            str(payload.get('capture_source', '')).strip(),
            str(payload.get('camera_facing', '')).strip().lower(),
        )

    return (
        (request.POST.get('capture_source') or request.GET.get('capture_source') or '').strip(),
        (request.POST.get('camera_facing') or request.GET.get('camera_facing') or '').strip().lower(),
    )


def validate_live_rider_capture(request: HttpRequest) -> str | None:
    capture_source, camera_facing = extract_rider_capture_context(request)
    if capture_source != RIDER_LIVE_CAPTURE_SOURCE:
        return 'Take a live selfie with the front camera to continue.'
    if camera_facing and camera_facing != 'user':
        return 'Only front-camera selfies are allowed.'
    return None


def save_temporary_rider_photo(content: bytes, extension: str) -> str:
    storage_name = default_storage.save(
        f'riders/live/{uuid4().hex}.{extension}',
        ContentFile(content),
    )
    return default_storage.url(storage_name)


def save_rider_photo_to_profile(rider: RiderProfile, content: bytes, extension: str) -> str:
    if rider.photo:
        rider.photo.delete(save=False)
    rider.photo.save(f'{uuid4().hex}.{extension}', ContentFile(content), save=False)
    rider.photo_url = rider.photo.storage.url(rider.photo.name)
    rider.save(update_fields=['photo', 'photo_url', 'updated_at'])
    return rider.photo_source


def extract_rider_photo_upload(request: HttpRequest) -> tuple[bytes | None, str | None, str | None]:
    uploaded_file = request.FILES.get('photo')
    if uploaded_file:
        if uploaded_file.size > RIDER_PHOTO_MAX_BYTES:
            return None, None, 'Photo must be 2MB or smaller.'
        extension = rider_photo_extension_for_content_type(uploaded_file.content_type)
        if not extension:
            return None, None, 'Upload a JPG, PNG, or WEBP image.'
        return uploaded_file.read(), extension, None

    if not request.body:
        return None, None, 'Upload a rider photo before continuing.'

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, None, 'Could not read the uploaded photo payload.'

    image_data = payload.get('image_data', '')
    if not image_data.startswith('data:image/'):
        return None, None, 'Upload a JPG, PNG, or WEBP image.'

    header, _, encoded = image_data.partition(',')
    content_type = header.split(';', 1)[0][5:]
    extension = rider_photo_extension_for_content_type(content_type)
    if not extension:
        return None, None, 'Upload a JPG, PNG, or WEBP image.'

    try:
        content = base64.b64decode(encoded)
    except (ValueError, TypeError):
        return None, None, 'Could not decode the captured rider photo.'

    if len(content) > RIDER_PHOTO_MAX_BYTES:
        return None, None, 'Photo must be 2MB or smaller.'
    return content, extension, None


def shop_location_is_configured(shop: Shop) -> bool:
    return bool(
        (shop.address_line_1 or '').strip()
        and (shop.district or '').strip()
        and (shop.pincode or '').strip()
        and shop.latitude is not None
        and shop.longitude is not None
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
                'state': component_map.get('administrative_area_level_1', '')[:80],
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
        'state': (address.get('state') or address.get('region') or '')[:80],
        'pincode': address.get('postcode', '')[:12],
    }


@require_GET
def reverse_geocode_location_api(request: HttpRequest) -> JsonResponse:
    latitude = request.GET.get('latitude', '').strip()
    longitude = request.GET.get('longitude', '').strip()
    try:
        lat_value = Decimal(latitude)
        lng_value = Decimal(longitude)
    except Exception:
        return JsonResponse({'error': 'Invalid coordinates.'}, status=400)

    details = reverse_geocode_location(lat_value, lng_value)
    if not details:
        return JsonResponse({'error': 'Address lookup unavailable.'}, status=502)
    return JsonResponse(details)


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
        owner = getattr(user, 'shop_owner_profile', None)
        if owner and owner.shops.exists():
            return reverse('core:shop_dashboard')
        return reverse('core:shop_start')
    if role == RoleType.RIDER:
        return reverse('core:rider_dashboard')
    if role == RoleType.ADMIN:
        return reverse('admin:index')
    return reverse('core:login')


def is_razorpay_ready() -> bool:
    return bool(getattr(settings, 'RAZORPAY_KEY_ID', '') and getattr(settings, 'RAZORPAY_KEY_SECRET', ''))


def settlement_qr_fallback_ready() -> bool:
    return bool(
        getattr(settings, 'RAZORPAY_SETTLEMENT_QR_IMAGE_URL', '')
        or getattr(settings, 'RAZORPAY_SETTLEMENT_UPI_ID', '')
    )


def can_create_settlement_qr() -> bool:
    return is_razorpay_ready() or settlement_qr_fallback_ready()


def build_order_detail_absolute_url(request: HttpRequest, order: Order) -> str:
    return request.build_absolute_uri(reverse('core:order_detail', args=[order.id]))


def order_payment_reference(order: Order) -> str:
    if order.payment_reference:
        return order.payment_reference
    if order.checkout_session and order.checkout_session.razorpay_payment_id:
        return order.checkout_session.razorpay_payment_id
    return ''


def order_customer_payment_complete(order: Order) -> bool:
    return order.payment_status == PaymentStatus.PAID


def order_has_open_cod_payment_link(order: Order) -> bool:
    return bool(
        order.cod_payment_link_url
        and order.cod_payment_link_status in ['', 'created', 'partially_paid']
        and not order_customer_payment_complete(order)
    )


def order_needs_rider_settlement(order: Order) -> bool:
    return (
        order.payment_method == PaymentMethod.COD
        and order.cod_collection_mode == CodCollectionMode.CASH
        and order.settlement_status != SettlementStatus.PAID
    )


def order_can_request_cod_online_payment(order: Order) -> bool:
    return (
        order.payment_method == PaymentMethod.COD
        and order.status == OrderStatus.OUT_FOR_DELIVERY
        and not order_customer_payment_complete(order)
        and bool((order.customer.email or '').strip())
        and is_razorpay_ready()
    )


def landing_context() -> dict[str, Any]:
    return {}


def customer_page_nav() -> list[dict[str, str]]:
    return [
        {'label': 'Home', 'url': reverse('core:customer_dashboard'), 'icon': 'house'},
        {'label': 'Cart', 'url': reverse('core:customer_cart'), 'icon': 'shopping-cart'},
        {'label': 'KhataBook', 'url': reverse('core:customer_khatabook'), 'icon': 'wallet'},
        {'label': 'Orders', 'url': reverse('core:customer_orders'), 'icon': 'package'},
        {'label': 'Profile', 'url': reverse('core:customer_profile'), 'icon': 'user'},
    ]


def shop_page_nav() -> list[dict[str, str]]:
    return [
        {'label': 'Overview', 'url': reverse('core:shop_dashboard'), 'icon': 'layout-dashboard'},
        {'label': 'Orders', 'url': reverse('core:shop_orders'), 'icon': 'clipboard-list'},
        {'label': 'KhataBook', 'url': reverse('core:shop_khatabook'), 'icon': 'wallet'},
        {'label': 'Catalog', 'url': reverse('core:shop_products'), 'icon': 'boxes'},
        {'label': 'Settings', 'url': reverse('core:shop_settings'), 'icon': 'settings'},
    ]


def rider_page_nav() -> list[dict[str, str]]:
    return [
        {'label': 'New', 'url': reverse('core:rider_dashboard'), 'icon': 'package'},
        {'label': 'Active', 'url': reverse('core:rider_deliveries'), 'icon': 'bike'},
        {'label': 'Done', 'url': reverse('core:rider_completed_orders'), 'icon': 'badge-check'},
        {'label': 'Earn', 'url': reverse('core:rider_earnings'), 'icon': 'wallet'},
        {'label': 'Profile', 'url': reverse('core:rider_profile'), 'icon': 'user'},
    ]


def normalize_shop_owner_approval(owner: ShopOwnerProfile, shop: Shop) -> str:
    owner_status = owner.approval_status
    shop_status = shop.approval_status
    if owner_status == shop_status:
        return shop_status
    if ApprovalStatus.PENDING in {owner_status, shop_status}:
        if ApprovalStatus.REJECTED in {owner_status, shop_status}:
            return ApprovalStatus.REJECTED
        if ApprovalStatus.APPROVED in {owner_status, shop_status}:
            return ApprovalStatus.APPROVED
    return shop_status


def sync_shop_owner_approval(owner: ShopOwnerProfile, shop: Shop) -> None:
    target_status = normalize_shop_owner_approval(owner, shop)
    if owner.approval_status != target_status:
        owner.approval_status = target_status
        owner.save(update_fields=['approval_status', 'updated_at'])
    if shop.approval_status != target_status or (target_status != ApprovalStatus.APPROVED and shop.is_open):
        shop.approval_status = target_status
        if target_status != ApprovalStatus.APPROVED:
            shop.is_open = False
            shop.save(update_fields=['approval_status', 'is_open', 'updated_at'])
        else:
            shop.save(update_fields=['approval_status', 'updated_at'])


def handle_rider_availability_toggle(request: HttpRequest, rider: RiderProfile) -> HttpResponse | None:
    if request.method == 'POST' and request.POST.get('action') == 'toggle_availability':
        if rider.approval_status != ApprovalStatus.APPROVED:
            messages.error(request, 'Admin approval is required before you can go live for dispatch.')
            return redirect(request.path)
        rider.is_available = request.POST.get('is_available') == 'on'
        rider.save(update_fields=['is_available', 'updated_at'])
        messages.success(request, 'Rider availability updated.')
        return redirect(request.path)
    return None


def rider_availability_redirect_target(request: HttpRequest) -> str:
    next_url = (request.POST.get('next') or '').strip()
    if next_url:
        parsed_url = urllib_parse.urlparse(next_url)
        if not parsed_url.scheme and not parsed_url.netloc and next_url.startswith('/'):
            return next_url
    return reverse('core:rider_dashboard')


def rider_order_redirect_target(request: HttpRequest, order_id: int) -> str:
    next_url = (request.POST.get('next') or '').strip()
    if next_url:
        parsed_url = urllib_parse.urlparse(next_url)
        if not parsed_url.scheme and not parsed_url.netloc and next_url.startswith('/'):
            return next_url
    return reverse('core:order_detail', args=[order_id])


def format_shop_address(shop: Shop) -> str:
    address_parts = [
        shop.address_line_1,
        shop.address_line_2,
        shop.area,
        shop.district,
        shop.pincode,
    ]
    return ', '.join(part for part in address_parts if part)


def build_map_pin_url(latitude: Decimal, longitude: Decimal) -> str:
    return f'https://www.google.com/maps/search/?api=1&query={latitude},{longitude}'


def build_order_item_summary(order: Order) -> tuple[list[str], Decimal]:
    item_lines = []
    subtotal = Decimal('0.00')
    for item in order.items.select_related('product'):
        line_total = item.line_total
        subtotal += line_total
        item_lines.append(
            f'- {item.product.name}: {item.quantity} x Rs. {item.unit_price} = Rs. {line_total}'
        )
    return item_lines, subtotal


def send_order_status_email(
    *,
    order: Order,
    subject: str,
    headline: str,
    detail: str,
) -> tuple[bool, str]:
    recipient = (order.customer.email or '').strip()
    if not recipient:
        return False, 'No customer email is available for this order.'

    item_lines, _ = build_order_item_summary(order)
    bill_breakup = build_order_bill_breakup(order)
    rider_name = order.rider.full_name if order.rider else 'Pending rider assignment'
    rider_phone = order.rider.phone if order.rider else 'Unavailable'
    rider_email = order.rider.email if order.rider and order.rider.email else 'Unavailable'
    payment_reference = order_payment_reference(order)

    otp_lines = []
    if order.status == OrderStatus.OUT_FOR_DELIVERY:
        otp_lines = [
            '',
            'Delivery OTP',
            f'Share this OTP only at handoff: {order.customer_otp}',
        ]

    message = '\n'.join(
        [
            headline,
            '',
            detail,
            *otp_lines,
            '',
            'Invoice',
            f'Order: {order.display_id}',
            f'Store: {order.shop.name}',
            f'Status: {order.get_status_display()}',
            f'Payment: {order.get_payment_method_display()} ({order.get_payment_status_display()})',
            f'Item total: Rs. {bill_breakup["subtotal"]}',
            f'Delivery fee: Rs. {bill_breakup["delivery_fee"]}',
            f'Shopkeeper commission fee: Rs. {bill_breakup["shopkeeper_commission_fee"]}',
            f'GramExpress platform fee: Rs. {bill_breakup["platform_fee"]}',
            f'Total: Rs. {bill_breakup["total"]}',
            *( [f'Payment reference: {payment_reference}'] if payment_reference else [] ),
            '',
            'Order Summary',
            *item_lines,
            '',
            'Rider Contact',
            f'Name: {rider_name}',
            f'Phone: {rider_phone}',
            f'Email: {rider_email}',
            '',
            'Delivery Details',
            f'Pickup: {order.shop.name}, {format_shop_address(order.shop)}',
            f'Drop-off: {order.delivery_address}',
            f'Customer note: {order.customer_notes or "None"}',
        ]
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@gramexpress.local'),
            recipient_list=[recipient],
            fail_silently=False,
        )
        return True, 'Customer email update sent successfully.'
    except Exception:
        return False, 'Customer email update could not be sent with the current mail settings.'


def send_store_order_status_email(
    *,
    order: Order,
    subject: str,
    headline: str,
    detail: str,
) -> tuple[bool, str]:
    recipient = (order.shop.owner.email or '').strip()
    if not recipient:
        return False, 'No store email is available for this order.'

    item_lines, _ = build_order_item_summary(order)
    bill_breakup = build_order_bill_breakup(order)
    rider_name = order.rider.full_name if order.rider else 'Pending rider assignment'
    rider_phone = order.rider.phone if order.rider else 'Unavailable'
    customer_phone = order.customer.phone or 'Unavailable'
    otp_lines = []
    if order.status == OrderStatus.OUT_FOR_DELIVERY:
        otp_lines = [
            '',
            'Handoff OTP',
            f'Customer delivery OTP: {order.customer_otp}',
        ]

    message = '\n'.join(
        [
            headline,
            '',
            detail,
            *otp_lines,
            '',
            'Dispatch Summary',
            f'Order: {order.display_id}',
            f'Status: {order.get_status_display()}',
            f'Customer: {order.customer.full_name}',
            f'Customer phone: {customer_phone}',
            f'Rider: {rider_name}',
            f'Rider phone: {rider_phone}',
            f'Item total: Rs. {bill_breakup["subtotal"]}',
            f'Delivery fee: Rs. {bill_breakup["delivery_fee"]}',
            f'Shopkeeper commission fee: Rs. {bill_breakup["shopkeeper_commission_fee"]}',
            f'GramExpress platform fee: Rs. {bill_breakup["platform_fee"]}',
            f'Total: Rs. {bill_breakup["total"]}',
            '',
            'Order Summary',
            *item_lines,
            '',
            'Route',
            f'Pickup: {order.shop.name}, {format_shop_address(order.shop)}',
            f'Drop-off: {order.delivery_address}',
        ]
    )
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@gramexpress.local'),
            recipient_list=[recipient],
            fail_silently=False,
        )
        return True, 'Store email update sent successfully.'
    except Exception:
        return False, 'Store email update could not be sent with the current mail settings.'


def send_cod_payment_link_email(*, order: Order) -> tuple[bool, str]:
    recipient = (order.customer.email or '').strip()
    if not recipient or not order.cod_payment_link_url:
        return False, 'Customer email or COD payment link is unavailable.'

    message = '\n'.join(
        [
            f'Pay securely online for {order.display_id}',
            '',
            'Your rider shared a Razorpay payment link for this cash-on-delivery order.',
            'Open the link below, complete the payment, and then continue the handoff with the rider.',
            '',
            f'Payment link: {order.cod_payment_link_url}',
            '',
            f'Order: {order.display_id}',
            f'Store: {order.shop.name}',
            f'Amount: Rs. {order.total_amount}',
            f'Delivery address: {order.delivery_address}',
            '',
            'This payment updates both the customer and rider dashboards automatically after it succeeds.',
        ]
    )
    try:
        send_mail(
            subject=f'Pay online for COD order {order.display_id}',
            message=message,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@gramexpress.local'),
            recipient_list=[recipient],
            fail_silently=False,
        )
        return True, 'COD payment link email sent successfully.'
    except Exception:
        return False, 'COD payment link email could not be sent with the current mail settings.'


def build_order_flow_steps(order: Order) -> list[dict[str, Any]]:
    steps = [
        {'label': 'Accepted', 'completed': bool(order.rider_id), 'current': False},
        {
            'label': 'Pickup',
            'completed': order.status in [OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED],
            'current': False,
        },
        {'label': 'Delivered', 'completed': order.status == OrderStatus.DELIVERED, 'current': False},
    ]
    if order.status == OrderStatus.DELIVERED:
        steps[2]['current'] = True
    elif order.status == OrderStatus.OUT_FOR_DELIVERY:
        steps[1]['current'] = True
    elif order.rider_id:
        steps[0]['current'] = True
    else:
        steps[0]['current'] = True
    return steps


def enrich_order_progress(order: Order) -> Order:
    order.flow_steps = build_order_flow_steps(order)
    order.milestone_timestamps = build_order_milestone_timestamps(order)
    slot_meta = order.delivery_slot_config
    order.delivery_slot_name = slot_meta['name']
    order.delivery_slot_time_label = slot_meta['time_label']
    order.delivery_slot_tag = slot_meta['tag']
    order.delivery_slot_chip = delivery_slot_chip_class(order.delivery_slot)
    deadline_state = delivery_deadline_state(
        order.delivery_deadline,
        reference_time=timezone.now(),
        window_start=order.created_at,
    )
    order.time_remaining = deadline_state['time_remaining']
    order.time_remaining_label = deadline_state['time_remaining_label']
    order.deadline_chip = deadline_state['deadline_chip']
    order.is_deadline_overdue = deadline_state['is_overdue']
    order.deadline_label = timezone.localtime(order.delivery_deadline).strftime('%b %d, %H:%M') if order.delivery_deadline else 'Pending'
    order.customer_otp_masked = f'••••{order.customer_otp[-2:]}' if order.customer_otp else 'Unavailable'
    order.customer_otp_valid_until = delivery_otp_valid_until(order) if order.status == OrderStatus.OUT_FOR_DELIVERY else None
    order.customer_otp_expired = delivery_otp_is_expired(order) if order.status == OrderStatus.OUT_FOR_DELIVERY else False
    order.latest_rider_notification = (
        order.notifications.filter(notification_type=NotificationType.RIDER).order_by('-created_at').first()
    )
    order.latest_rider_update = (
        order.latest_rider_notification.body
        if order.latest_rider_notification
        else (
            f'{order.rider.full_name} accepted this order and is heading to the store.'
            if order.rider_id and order.status in [OrderStatus.CONFIRMED, OrderStatus.PACKED]
            else 'Waiting for the next rider update.'
        )
    )
    order.last_update_at = (
        order.latest_rider_notification.created_at
        if order.latest_rider_notification
        else order.milestone_timestamps.get('delivered')
        or order.milestone_timestamps.get('pickup')
        or order.milestone_timestamps.get('accepted')
        or order.created_at
    )
    order.last_update_label = short_relative_time(order.last_update_at)
    order.last_update_timestamp_label = timezone.localtime(order.last_update_at).strftime('%b %d, %H:%M')
    if order.status == OrderStatus.DELIVERED:
        order.flow_headline = 'Delivered to customer'
        order.flow_detail = f'The final handoff is complete and the {order.delivery_slot_name.lower()} order is closed.'
        order.support_prompt = 'Need help after delivery?'
        order.support_copy = 'Use support for billing issues, missing items, or post-delivery help.'
    elif order.status == OrderStatus.OUT_FOR_DELIVERY:
        order.flow_headline = 'Picked up and on the way'
        order.flow_detail = f'The rider confirmed pickup and is working toward the {order.delivery_slot_name.lower()} deadline.'
        order.support_prompt = 'Need delivery help?'
        order.support_copy = 'Use support if the rider cannot reach you, the OTP expired, or delivery feels delayed.'
    elif order.rider_id:
        order.flow_headline = 'Rider accepted and heading to pickup'
        order.flow_detail = f'The next app action is confirming arrival at the store before the {order.delivery_slot_name.lower()} window closes.'
        order.support_prompt = 'Need dispatch help?'
        order.support_copy = 'Use support if the order should be reassigned or the rider cannot reach the store.'
    else:
        order.flow_headline = 'Waiting for rider acceptance'
        order.flow_detail = f'A nearby rider still needs to claim this {order.delivery_slot_name.lower()} delivery.'
        order.support_prompt = 'Need order help?'
        order.support_copy = 'Use support for address issues, store delays, or payment questions.'
    order.payment_reference_display = order_payment_reference(order)
    order.cod_online_link_ready = order_has_open_cod_payment_link(order)
    order.cod_online_paid = order.cod_collection_mode == CodCollectionMode.ONLINE and order_customer_payment_complete(order)
    order.cod_cash_confirmed = order.cod_collection_mode == CodCollectionMode.CASH and bool(order.cash_confirmed_at)
    order.settlement_upi_url = build_settlement_upi_url(order)
    order.settlement_qr_ready = order.settlement_status == SettlementStatus.QR_READY and (
        bool(order.settlement_qr_id) or bool(order.settlement_qr_image_url) or bool(order.settlement_upi_url)
    )
    order.payment_summary = build_payment_summary(order)
    return order


def rider_status_chip(order: Order) -> str:
    if order.status == OrderStatus.OUT_FOR_DELIVERY:
        return 'success'
    if order.status == OrderStatus.DELIVERED:
        return 'success'
    if order.status == OrderStatus.CANCELLED:
        return 'warn'
    return 'info'


def rider_status_hint(order: Order, *, pickup_gate_open: bool) -> str:
    if order.status == OrderStatus.OUT_FOR_DELIVERY:
        if order.payment_method == PaymentMethod.KHATABOOK:
            return 'This is a KhataBook credit order. Complete the handoff with OTP only and do not collect money from the customer.'
        if order.cod_collection_mode == CodCollectionMode.ONLINE and not order_customer_payment_complete(order):
            return 'The Razorpay payment link was sent. Wait for the customer payment, then finish handoff with the OTP.'
        return 'Pickup confirmed. Head to the customer and complete handoff with the OTP.'
    if order.status == OrderStatus.DELIVERED:
        if order_needs_rider_settlement(order):
            return 'Delivery is done, but the collected cash still needs settlement to GramExpress from your dashboard QR.'
        return 'Delivered successfully. This order is now part of your completed history.'
    if pickup_gate_open:
        return 'You are at the store. Mark the order as picked up so customer and store are both updated immediately.'
    return 'Go to the store first. You can only mark the order as picked up when you are close to the pickup point.'


def enrich_rider_order(order: Order, rider: RiderProfile) -> Order:
    enrich_order_progress(order)
    order.pickup_distance_km = kilometers_between(rider.latitude, rider.longitude, order.shop.latitude, order.shop.longitude)
    order.delivery_distance_km = kilometers_between(order.shop.latitude, order.shop.longitude, order.customer.latitude, order.customer.longitude)
    order.item_count = sum(item.quantity for item in order.items.all())
    order.pickup_map_url = order.shop.google_maps_url
    order.dropoff_map_url = order.customer.google_maps_url
    order.pickup_address = format_shop_address(order.shop)
    order.dropoff_address = order.delivery_address
    order.pickup_gate_open = order.pickup_distance_km <= PICKUP_GEOFENCE_KM
    order.status_chip = rider_status_chip(order)
    order.status_hint = rider_status_hint(order, pickup_gate_open=order.pickup_gate_open)
    order.rider_commission = RIDER_COMMISSION_PER_DELIVERY
    order.rider_distance_incentive = (
        RIDER_LONG_DISTANCE_INCENTIVE
        if Decimal(str(order.delivery_distance_km)) >= Decimal('6.0')
        else Decimal('0.00')
    )
    order.rider_peak_time_bonus = (
        RIDER_PEAK_HOUR_INCENTIVE
        if rider_peak_hour_bonus_eligible(order.delivered_at or order.updated_at)
        else Decimal('0.00')
    )
    order.rider_payout_total = quantize_money(
        order.rider_commission + order.rider_distance_incentive + order.rider_peak_time_bonus
    )
    order.is_khatabook_order = order.payment_method == PaymentMethod.KHATABOOK
    order.is_direct_payment_order = order.payment_method in [PaymentMethod.COD, PaymentMethod.RAZORPAY]
    order.payment_mode_badge = 'KhataBook credit' if order.is_khatabook_order else 'Direct payment'
    if order.payment_method == PaymentMethod.KHATABOOK:
        order.dashboard_payment_label = 'KhataBook'
        order.dashboard_payment_chip = 'rider-payment-chip-khata'
    elif order.payment_status == PaymentStatus.PAID:
        order.dashboard_payment_label = 'Paid'
        order.dashboard_payment_chip = 'success'
    elif order.payment_method == PaymentMethod.COD:
        order.dashboard_payment_label = 'COD'
        order.dashboard_payment_chip = 'warn'
    else:
        order.dashboard_payment_label = 'Online'
        order.dashboard_payment_chip = 'info'
    order.accepted_at = order.milestone_timestamps.get('accepted')
    order.pickup_confirmed_at = order.milestone_timestamps.get('pickup')
    order.delivered_confirmed_at = order.milestone_timestamps.get('delivered')
    if order.status == OrderStatus.DELIVERED and order_needs_rider_settlement(order):
        order.current_mission_title = 'Settle collected cash'
        order.current_mission_detail = 'The customer confirmed cash payment. Use the rider settlement QR to pay GramExpress from your account.'
        order.current_mission_map_url = order.dropoff_map_url
        order.current_mission_map_label = 'Open Drop-off Pin'
        order.current_mission_meta = f'Rs. {order.total_amount} settlement pending'
    elif order.status == OrderStatus.OUT_FOR_DELIVERY and order.cod_collection_mode == CodCollectionMode.ONLINE and not order_customer_payment_complete(order):
        order.current_mission_title = 'Collect money online first'
        order.current_mission_detail = 'The customer has a Razorpay payment link by email. Finish delivery only after that payment is recorded.'
        order.current_mission_map_url = order.dropoff_map_url
        order.current_mission_map_label = 'Open Drop-off Pin'
        order.current_mission_meta = f'Rs. {order.total_amount} waiting online payment'
    elif order.status == OrderStatus.OUT_FOR_DELIVERY and order.payment_method == PaymentMethod.KHATABOOK:
        order.current_mission_title = 'Complete KhataBook handoff'
        order.current_mission_detail = 'This order is on credit. Deliver normally, verify the OTP, and do not collect money from the customer during handoff.'
        order.current_mission_map_url = order.dropoff_map_url
        order.current_mission_map_label = 'Open Drop-off Pin'
        order.current_mission_meta = f'KhataBook due by {order.credit_due_date.strftime("%b %d") if order.credit_due_date else "next Monday"}'
    elif order.status == OrderStatus.OUT_FOR_DELIVERY:
        order.current_mission_title = 'Finish the customer handoff'
        order.current_mission_detail = 'Navigate to the drop-off pin, verify the OTP, and complete delivery.'
        order.current_mission_map_url = order.dropoff_map_url
        order.current_mission_map_label = 'Open Drop-off Pin'
        order.current_mission_meta = f'{order.delivery_distance_km} km route to customer'
    elif order.pickup_gate_open:
        order.current_mission_title = 'Confirm store pickup'
        order.current_mission_detail = 'You are within range of the store. Mark the order as picked up so both customer and store get updated immediately.'
        order.current_mission_map_url = order.pickup_map_url
        order.current_mission_map_label = 'Open Pickup Pin'
        order.current_mission_meta = f'{order.pickup_distance_km} km from pickup pin'
    else:
        order.current_mission_title = 'Head to the pickup point'
        order.current_mission_detail = 'Use the pinned pickup location and mark the order as picked up once you are close enough to the store.'
        order.current_mission_map_url = order.pickup_map_url
        order.current_mission_map_label = 'Open Pickup Pin'
        order.current_mission_meta = f'{order.pickup_distance_km} km from pickup pin'
    return order


def order_slot_sort_key(order: Order) -> tuple[Any, ...]:
    return (
        getattr(order, 'slot_priority', order.delivery_slot_config.get('priority_level', 99)),
        order.delivery_deadline or timezone.now() + timedelta(days=365),
        Decimal(str(getattr(order, 'delivery_distance_km', order.distance_km or Decimal('0.00')))),
        order.id,
    )


def build_order_slot_sections(orders: list[Order]) -> list[dict[str, Any]]:
    sections = []
    for slot_code, _ in DeliverySlot.choices:
        config = delivery_slot_config(slot_code)
        slot_orders = sorted(
            [order for order in orders if normalize_delivery_slot(order.delivery_slot) == slot_code],
            key=order_slot_sort_key,
        )
        sections.append(
            {
                'code': slot_code,
                'label': config['name'],
                'time_label': config['time_label'],
                'description': config['description'],
                'tag': config['tag'],
                'chip': delivery_slot_chip_class(slot_code),
                'orders': slot_orders,
            }
        )
    return sections


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


def build_cart_context(request: HttpRequest, *, delivery_slot: str | None = None):
    cart = cart_from_session(request)
    selected_slot = normalize_delivery_slot(delivery_slot or DEFAULT_DELIVERY_SLOT)
    selected_delivery_fee = delivery_slot_fee(selected_slot)
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
        if not product.is_visible:
            issues.append('This item is currently hidden by the store.')
            availability_label = 'Hidden item'
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
        fee_breakup = checkout_fee_breakup(
            subtotal=sum(item['line_total'] for item in shop_items),
            delivery_fee=selected_delivery_fee,
        )
        groups.append(
            {
                'shop': shop,
                'items': shop_items,
                'subtotal': fee_breakup['subtotal'],
                'delivery_fee': fee_breakup['delivery_fee'],
                'shopkeeper_commission_fee': fee_breakup['shopkeeper_commission_fee'],
                'platform_fee': fee_breakup['platform_fee'],
                'total': fee_breakup['total'],
                'shop_credit_exposure': fee_breakup['shop_credit_exposure'],
                'has_blocking_issue': any(item['has_blocking_issue'] for item in shop_items),
                'item_count': sum(item['quantity'] for item in shop_items),
                'delivery_slot': selected_slot,
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
        'delivery_slot': selected_slot,
        'delivery_slot_fee': selected_delivery_fee,
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


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'))


def quantize_percent(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.1'))


def normalize_delivery_slot(slot_code: str) -> str:
    if slot_code in DELIVERY_SLOT_RULES:
        return slot_code
    return DEFAULT_DELIVERY_SLOT


def delivery_slot_config(slot_code: str) -> dict[str, Any]:
    return delivery_slot_rule(normalize_delivery_slot(slot_code))


def delivery_slot_options(selected_slot: str | None = None) -> list[dict[str, Any]]:
    current_slot = normalize_delivery_slot(selected_slot or DEFAULT_DELIVERY_SLOT)
    options = []
    for slot_code, _ in DeliverySlot.choices:
        config = delivery_slot_config(slot_code)
        options.append(
            {
                'code': slot_code,
                'name': config['name'],
                'time_label': config['time_label'],
                'description': config['description'],
                'fee': Decimal(str(config['delivery_fee'])).quantize(Decimal('0.01')),
                'fee_label': 'Free' if Decimal(str(config['delivery_fee'])) <= Decimal('0.00') else f'+ Rs. {config["delivery_fee"]}',
                'color': config['color'],
                'chip_class': delivery_slot_chip_class(slot_code),
                'priority_level': config['priority_level'],
                'tag': config['tag'],
                'is_selected': slot_code == current_slot,
                'is_recommended': slot_code == DEFAULT_DELIVERY_SLOT,
            }
        )
    return options


def delivery_slot_chip_class(slot_code: str) -> str:
    color = delivery_slot_config(slot_code)['color']
    return {
        'red': 'warn',
        'green': 'success',
        'blue': 'info',
        'gray': 'info',
    }.get(color, 'info')


def format_countdown(total_seconds: float) -> str:
    remaining_seconds = max(int(total_seconds), 0)
    hours, remainder = divmod(remaining_seconds, 3600)
    minutes = remainder // 60
    return f'{hours:02d}:{minutes:02d}'


def delivery_deadline_state(deadline, *, reference_time=None, window_start=None) -> dict[str, Any]:
    if not deadline:
        return {
            'time_remaining': None,
            'time_remaining_label': 'No deadline',
            'deadline_chip': 'info',
            'is_overdue': False,
        }
    now = reference_time or timezone.now()
    remaining_seconds = (deadline - now).total_seconds()
    if remaining_seconds <= 0:
        return {
            'time_remaining': timedelta(seconds=0),
            'time_remaining_label': 'Overdue',
            'deadline_chip': 'warn',
            'is_overdue': True,
        }
    total_window_seconds = max((deadline - (window_start or now)).total_seconds(), 1)
    ratio = remaining_seconds / total_window_seconds if total_window_seconds else 0
    if ratio > 0.5:
        chip = 'success'
    elif ratio > 0.25:
        chip = 'info'
    else:
        chip = 'warn'
    return {
        'time_remaining': timedelta(seconds=int(remaining_seconds)),
        'time_remaining_label': format_countdown(remaining_seconds),
        'deadline_chip': chip,
        'is_overdue': False,
    }


def rider_peak_hour_bonus_eligible(moment) -> bool:
    if not moment:
        return False
    hour = timezone.localtime(moment).hour
    return hour in {12, 13, 14, 18, 19, 20, 21}


def rider_high_completion_bonus(completed_delivery_count: int) -> Decimal:
    for threshold, amount in RIDER_HIGH_COMPLETION_BONUS_TIERS:
        if completed_delivery_count >= threshold:
            return amount
    return Decimal('0.00')


def checkout_fee_breakup(*, subtotal: Decimal, delivery_fee: Decimal = DEFAULT_DELIVERY_FEE) -> dict[str, Decimal]:
    subtotal = quantize_money(subtotal)
    delivery_fee = quantize_money(delivery_fee)
    shopkeeper_commission_fee = quantize_money(SHOPKEEPER_COMMISSION_FEE)
    platform_fee = quantize_money(GRAMEXPRESS_PLATFORM_FEE)
    total = quantize_money(subtotal + delivery_fee + shopkeeper_commission_fee + platform_fee)
    shop_credit_exposure = quantize_money(subtotal + shopkeeper_commission_fee)
    return {
        'subtotal': subtotal,
        'delivery_fee': delivery_fee,
        'shopkeeper_commission_fee': shopkeeper_commission_fee,
        'platform_fee': platform_fee,
        'total': total,
        'shop_credit_exposure': shop_credit_exposure,
    }


def build_order_bill_breakup(order: Order) -> dict[str, Decimal]:
    _, subtotal = build_order_item_summary(order)
    fee_breakup = checkout_fee_breakup(subtotal=subtotal, delivery_fee=order.delivery_fee)
    legacy_total = quantize_money(subtotal + order.delivery_fee)
    if order.total_amount and order.total_amount <= legacy_total:
        fee_breakup['shopkeeper_commission_fee'] = Decimal('0.00')
        fee_breakup['platform_fee'] = Decimal('0.00')
        fee_breakup['shop_credit_exposure'] = subtotal
        fee_breakup['total'] = quantize_money(order.total_amount)
    elif order.total_amount and order.total_amount != fee_breakup['total']:
        fee_breakup['total'] = quantize_money(order.total_amount)
    return fee_breakup


def build_cart_snapshot(cart: dict[str, Any], *, delivery_slot: str = DEFAULT_DELIVERY_SLOT) -> dict[str, Any]:
    selected_slot = normalize_delivery_slot(delivery_slot)
    selected_delivery_fee = delivery_slot_fee(selected_slot)
    groups = []
    for group in cart['groups']:
        fee_breakup = checkout_fee_breakup(subtotal=group['subtotal'], delivery_fee=selected_delivery_fee)
        groups.append(
            {
                'shop_id': group['shop'].id,
                'delivery_slot': selected_slot,
                'delivery_fee': decimal_to_str(fee_breakup['delivery_fee']),
                'shopkeeper_commission_fee': decimal_to_str(fee_breakup['shopkeeper_commission_fee']),
                'platform_fee': decimal_to_str(fee_breakup['platform_fee']),
                'subtotal': decimal_to_str(fee_breakup['subtotal']),
                'total': decimal_to_str(fee_breakup['total']),
                'shop_credit_exposure': decimal_to_str(fee_breakup['shop_credit_exposure']),
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
        'delivery_slot': selected_slot,
        'groups': groups,
    }


def build_checkout_signature(
    *,
    snapshot: dict[str, Any],
    payment_method: str,
    customer_notes: str,
    delivery_address: str,
    delivery_slot: str,
) -> str:
    signature_source = json.dumps(
        {
            'snapshot': snapshot,
            'payment_method': payment_method,
            'customer_notes': customer_notes,
            'delivery_address': delivery_address,
            'delivery_slot': delivery_slot,
        },
        sort_keys=True,
        separators=(',', ':'),
    )
    return hashlib.sha256(signature_source.encode('utf-8')).hexdigest()


def next_monday(reference_date: date) -> date:
    days_until_next_monday = (7 - reference_date.weekday()) or 7
    return reference_date + timedelta(days=days_until_next_monday)


def khatabook_week_start(reference_date: date) -> date:
    return reference_date - timedelta(days=reference_date.weekday())


def khatabook_cycle_status(cycle: KhataBookCycle) -> str:
    if cycle.outstanding_amount <= Decimal('0.00') or cycle.status == KhataBookCycleStatus.PAID:
        return KhataBookCycleStatus.PAID
    if cycle.status == KhataBookCycleStatus.COLLECTION_REQUESTED:
        return KhataBookCycleStatus.COLLECTION_REQUESTED
    return KhataBookCycleStatus.OPEN


def refresh_khatabook_cycle(cycle: KhataBookCycle) -> KhataBookCycle:
    orders = cycle.orders.exclude(status=OrderStatus.CANCELLED)
    total_amount = sum((order.total_amount for order in orders), Decimal('0.00'))
    if total_amount <= Decimal('0.00'):
        paid_amount = Decimal('0.00')
        status = KhataBookCycleStatus.OPEN
        paid_at = None
    elif cycle.paid_at:
        paid_amount = total_amount
        status = KhataBookCycleStatus.PAID
        paid_at = cycle.paid_at
    else:
        paid_amount = Decimal('0.00')
        status = (
            KhataBookCycleStatus.COLLECTION_REQUESTED
            if cycle.status == KhataBookCycleStatus.COLLECTION_REQUESTED
            else KhataBookCycleStatus.OPEN
        )
        paid_at = None
    updates = []
    if cycle.total_amount != total_amount:
        cycle.total_amount = total_amount
        updates.append('total_amount')
    if cycle.paid_amount != paid_amount:
        cycle.paid_amount = paid_amount
        updates.append('paid_amount')
    if cycle.status != status:
        cycle.status = status
        updates.append('status')
    if cycle.paid_at != paid_at:
        cycle.paid_at = paid_at
        updates.append('paid_at')
    if updates:
        cycle.save(update_fields=[*updates, 'updated_at'])
    return cycle


def get_or_create_khatabook_cycle(*, customer: CustomerProfile, reference_date: date | None = None) -> KhataBookCycle:
    reference_date = reference_date or timezone.localdate()
    week_start = khatabook_week_start(reference_date)
    due_date = next_monday(reference_date)
    cycle, created = KhataBookCycle.objects.get_or_create(
        customer=customer,
        week_start=week_start,
        defaults={
            'due_date': due_date,
            'status': KhataBookCycleStatus.OPEN,
        },
    )
    updates = []
    if cycle.due_date != due_date:
        cycle.due_date = due_date
        updates.append('due_date')
    if created and cycle.status != KhataBookCycleStatus.OPEN:
        cycle.status = KhataBookCycleStatus.OPEN
        updates.append('status')
    if updates:
        cycle.save(update_fields=[*updates, 'updated_at'])
    return refresh_khatabook_cycle(cycle)


def mark_khatabook_cycle_paid(
    cycle: KhataBookCycle,
    *,
    settlement_method: str,
    payment_reference: str = '',
    paid_at=None,
) -> KhataBookCycle:
    paid_at = paid_at or timezone.now()
    orders = list(cycle.orders.exclude(status=OrderStatus.CANCELLED))
    total_amount = sum((order.total_amount for order in orders), Decimal('0.00'))
    cycle.total_amount = total_amount
    cycle.paid_amount = total_amount
    cycle.status = KhataBookCycleStatus.PAID
    cycle.settlement_method = settlement_method
    cycle.paid_at = paid_at
    cycle.failure_reason = ''
    cycle.save(
        update_fields=[
            'total_amount',
            'paid_amount',
            'status',
            'settlement_method',
            'paid_at',
            'failure_reason',
            'updated_at',
        ]
    )
    pending_collection_requests = list(
        cycle.collection_requests.exclude(status=KhataBookCollectionStatus.COMPLETED).select_related('rider')
    )
    for collection_request in pending_collection_requests:
        if collection_request.rider_id:
            collection_request.rider.is_available = True
            collection_request.rider.save(update_fields=['is_available', 'updated_at'])
        collection_request.status = KhataBookCollectionStatus.CANCELLED
        collection_request.save(update_fields=['status', 'updated_at'])
    for order in orders:
        update_fields = []
        if order.payment_status != PaymentStatus.PAID:
            order.payment_status = PaymentStatus.PAID
            update_fields.append('payment_status')
        if payment_reference and order.payment_reference != payment_reference:
            order.payment_reference = payment_reference
            update_fields.append('payment_reference')
        if order.credit_paid_at != paid_at:
            order.credit_paid_at = paid_at
            update_fields.append('credit_paid_at')
        if update_fields:
            order.save(update_fields=[*update_fields, 'updated_at'])
        create_notification(
            shop_owner=order.shop.owner,
            order=order,
            title='KhataBook payment recovered',
            body=(
                f'{order.display_id} was cleared by the customer. '
                'This credit cycle is settled and the storefront payout can now move forward.'
            ),
            notification_type=NotificationType.PAYMENT,
        )
    return cycle


def build_khatabook_cycle_summary(cycle: KhataBookCycle | None) -> dict[str, Any]:
    today = timezone.localdate()
    if cycle is None:
        upcoming_due = next_monday(today)
        return {
            'cycle': None,
            'status': 'empty',
            'status_label': 'No dues yet',
            'badge_class': 'info',
            'outstanding_amount': Decimal('0.00'),
            'total_amount': Decimal('0.00'),
            'paid_amount': Decimal('0.00'),
            'due_date': upcoming_due,
            'days_left': (upcoming_due - today).days,
            'headline': 'Start a KhataBook order to unlock 7-day platform credit.',
            'detail': f'Orders placed this week will stay on credit and become due on {upcoming_due.strftime("%b %d")}.',
            'collection_requested': False,
            'is_paid': False,
            'is_overdue': False,
            'is_defaulted': False,
        }

    cycle = refresh_khatabook_cycle(cycle)
    status = khatabook_cycle_status(cycle)
    days_left = (cycle.due_date - today).days
    if status == KhataBookCycleStatus.PAID:
        return {
            'cycle': cycle,
            'status': status,
            'status_label': 'Paid',
            'badge_class': 'success',
            'outstanding_amount': cycle.outstanding_amount,
            'total_amount': cycle.total_amount,
            'paid_amount': cycle.paid_amount,
            'due_date': cycle.due_date,
            'days_left': days_left,
            'headline': 'This KhataBook cycle is fully settled.',
            'detail': 'You have cleared the weekly credit line for this cycle.',
            'collection_requested': False,
            'is_paid': True,
            'is_overdue': False,
            'is_defaulted': False,
        }
    if cycle.outstanding_amount > Decimal('0.00') and cycle.due_date < today:
        return {
            'cycle': cycle,
            'status': 'overdue',
            'status_label': 'Defaulted',
            'badge_class': 'danger',
            'outstanding_amount': cycle.outstanding_amount,
            'total_amount': cycle.total_amount,
            'paid_amount': cycle.paid_amount,
            'due_date': cycle.due_date,
            'days_left': days_left,
            'headline': f'Rs. {cycle.outstanding_amount} is overdue from {cycle.due_date.strftime("%b %d")}.',
            'detail': (
                'Your 7-day credit window has already closed. Pay now through rider collection or Razorpay UPI '
                'to clear the default and reset the cycle.'
            ),
            'collection_requested': status == KhataBookCycleStatus.COLLECTION_REQUESTED,
            'is_paid': False,
            'is_overdue': True,
            'is_defaulted': True,
        }
    if status == KhataBookCycleStatus.COLLECTION_REQUESTED:
        return {
            'cycle': cycle,
            'status': status,
            'status_label': 'Collection requested',
            'badge_class': 'warn',
            'outstanding_amount': cycle.outstanding_amount,
            'total_amount': cycle.total_amount,
            'paid_amount': cycle.paid_amount,
            'due_date': cycle.due_date,
            'days_left': days_left,
            'headline': 'A COD / UPI collection request is already logged.',
            'detail': 'A delivery agent may take time to arrive for the KhataBook repayment handoff.',
            'collection_requested': True,
            'is_paid': False,
            'is_overdue': False,
            'is_defaulted': False,
        }
    return {
        'cycle': cycle,
        'status': status,
        'status_label': 'Payment due',
        'badge_class': 'warn',
        'outstanding_amount': cycle.outstanding_amount,
        'total_amount': cycle.total_amount,
        'paid_amount': cycle.paid_amount,
        'due_date': cycle.due_date,
        'days_left': days_left,
        'headline': f'Rs. {cycle.outstanding_amount} is due by {cycle.due_date.strftime("%b %d")}.',
        'detail': 'This week’s credit stays open until the next Monday repayment deadline.',
        'collection_requested': False,
        'is_paid': False,
        'is_overdue': False,
        'is_defaulted': False,
    }


def split_khatabook_exposure(amount: Decimal) -> Decimal:
    return (amount / Decimal('2')).quantize(Decimal('0.01'))


def annotate_catalog_product(product: Product) -> Product:
    if product.stock <= 0:
        product.stock_status_chip = 'danger'
    elif product.stock <= 10:
        product.stock_status_chip = 'warn'
    else:
        product.stock_status_chip = 'success'
    product.preview_description = (product.description or product.subtitle or '').strip()
    product.catalog_price_label = f'Rs. {product.price}'
    product.mrp_label = f'Rs. {product.mrp}' if product.mrp else f'Rs. {product.price}'
    product.visibility_label = 'Live' if product.is_visible else 'Hidden'
    product.visibility_chip = 'success' if product.is_visible else 'info'
    return product


def visible_products_queryset():
    return Product.objects.filter(is_visible=True)


def khatabook_risk_band(days_pending: int, *, is_defaulted: bool) -> dict[str, str]:
    if is_defaulted or days_pending > 7:
        return {
            'label': 'High',
            'chip': 'danger',
            'row_class': 'is-high-risk',
            'badge_class': 'shop-khatabook-risk-badge-high',
        }
    if days_pending >= 4:
        return {
            'label': 'Medium',
            'chip': 'warn',
            'row_class': 'is-medium-risk',
            'badge_class': 'shop-khatabook-risk-badge-medium',
        }
    return {
        'label': 'Low',
        'chip': 'success',
        'row_class': 'is-low-risk',
        'badge_class': 'shop-khatabook-risk-badge-low',
    }


def khatabook_collection_status_chip(collection_request: KhataBookCollectionRequest | None) -> str:
    if collection_request is None:
        return 'info'
    if collection_request.status == KhataBookCollectionStatus.ACCEPTED:
        return 'warn'
    if collection_request.status == KhataBookCollectionStatus.COMPLETED:
        return 'success'
    if collection_request.status == KhataBookCollectionStatus.CANCELLED:
        return 'muted'
    return 'info'


def create_notification_once(
    *,
    title: str,
    body: str,
    notification_type: str,
    customer: CustomerProfile | None = None,
    shop_owner: ShopOwnerProfile | None = None,
    rider: RiderProfile | None = None,
    order: Order | None = None,
) -> Notification | None:
    filters: dict[str, Any] = {
        'title': title,
        'body': body,
        'notification_type': notification_type,
        'customer': customer,
        'shop_owner': shop_owner,
        'rider': rider,
        'order': order,
    }
    if Notification.objects.filter(**filters).exists():
        return None
    return create_notification(
        customer=customer,
        shop_owner=shop_owner,
        rider=rider,
        order=order,
        title=title,
        body=body,
        notification_type=notification_type,
    )


def maybe_create_customer_khatabook_default_notification(customer: CustomerProfile) -> None:
    for cycle in customer.khatabook_cycles.all():
        cycle_summary = build_khatabook_cycle_summary(cycle)
        if not cycle_summary['is_defaulted']:
            continue
        create_notification_once(
            customer=customer,
            title='KhataBook due overdue',
            body=(
                f'Your KhataBook due of Rs. {cycle_summary["outstanding_amount"]} for the week starting '
                f'{cycle.week_start.strftime("%b %d")} is overdue. Clear it now to close the default.'
            ),
            notification_type=NotificationType.PAYMENT,
        )


def build_shop_khatabook_context(shop: Shop) -> dict[str, Any]:
    today = timezone.localdate()
    credit_orders = list(
        shop.orders.filter(payment_method=PaymentMethod.KHATABOOK)
        .exclude(status=OrderStatus.CANCELLED)
        .select_related('customer', 'rider', 'khata_cycle')
        .prefetch_related('items__product')
        .all()
    )
    active_orders = []
    defaulted_orders = []
    settled_orders = []
    unpaid_orders = []
    active_collection_ids: set[int] = set()
    total_credit_sales = Decimal('0.00')
    active_credit_exposure = Decimal('0.00')
    defaulted_amount = Decimal('0.00')
    settled_credit_amount = Decimal('0.00')
    total_payment_days = 0
    settled_payment_count = 0
    customer_rollups: dict[int, dict[str, Any]] = {}

    for order in credit_orders:
        enrich_order_progress(order)
        order.item_count = sum(item.quantity for item in order.items.all())
        order.bill_breakup = build_order_bill_breakup(order)
        order.current_due_date = order.credit_due_date or (order.khata_cycle.due_date if order.khata_cycle_id else None)
        order.credit_exposure_amount = order.bill_breakup['shop_credit_exposure']
        order.shop_exposure_share = split_khatabook_exposure(order.credit_exposure_amount)
        order.platform_exposure_share = split_khatabook_exposure(order.credit_exposure_amount)
        if order.status == OrderStatus.OUT_FOR_DELIVERY:
            order.shop_khata_dispatch_label = 'Picked up and moving to customer'
        elif order.status == OrderStatus.PACKED and order.rider_id:
            order.shop_khata_dispatch_label = 'Rider assigned and coming for pickup'
        elif order.status == OrderStatus.PACKED:
            order.shop_khata_dispatch_label = 'Packed and waiting for rider'
        elif order.status == OrderStatus.DELIVERED:
            order.shop_khata_dispatch_label = 'Delivered on credit'
        else:
            order.shop_khata_dispatch_label = 'Waiting for dispatch progress'
        order.credit_cycle_label = (
            f'{order.khata_cycle.week_start.strftime("%b %d")} to {order.khata_cycle.due_date.strftime("%b %d")}'
            if order.khata_cycle_id
            else 'Current cycle'
        )
        order.rider_summary = (
            f'{order.rider.full_name} | {order.shop_khata_dispatch_label}'
            if order.rider_id
            else 'No rider assigned yet'
        )
        order.rider_status_detail = (
            order.latest_rider_update
            if order.rider_id
            else 'Dispatch has not assigned a pickup rider yet.'
        )
        order.customer_name = order.customer.full_name
        order.customer_phone = order.customer.phone
        order.is_credit_settled = bool(order.credit_paid_at) or order.payment_status == PaymentStatus.PAID
        order.is_defaulted = bool(
            not order.is_credit_settled
            and order.current_due_date
            and order.current_due_date < today
        )
        order.is_credit_open = bool(not order.is_credit_settled and not order.is_defaulted)
        order.days_pending = max((today - timezone.localtime(order.created_at).date()).days, 0)
        order.days_overdue = (
            max((today - order.current_due_date).days, 0)
            if order.current_due_date and order.current_due_date < today
            else 0
        )
        risk_band = khatabook_risk_band(order.days_pending, is_defaulted=order.is_defaulted)
        order.risk_level = risk_band['label']
        order.risk_chip = risk_band['chip']
        order.risk_row_class = risk_band['row_class']
        order.risk_badge_class = risk_band['badge_class']
        if order.is_credit_settled:
            order.credit_state_label = 'Recovered'
            order.credit_state_chip = 'success'
            order.credit_state_detail = (
                f'Customer paid on {timezone.localtime(order.credit_paid_at).strftime("%b %d, %H:%M")}. '
                'Platform can move this storefront payout next.'
                if order.credit_paid_at
                else 'This KhataBook order has already been settled.'
            )
        elif order.is_defaulted:
            order.credit_state_label = 'Defaulted'
            order.credit_state_chip = 'danger'
            order.credit_state_detail = (
                f'This credit crossed the 7-day deadline on {order.current_due_date.strftime("%b %d")}. '
                f'Shop risk share is Rs. {order.shop_exposure_share} until recovery closes.'
            )
        else:
            order.credit_state_label = 'Exposure open'
            order.credit_state_chip = 'warn'
            order.credit_state_detail = (
                f'Credit stays open till {order.current_due_date.strftime("%b %d") if order.current_due_date else "next Monday"}. '
                f'Shop risk share is Rs. {order.shop_exposure_share} during this window.'
            )
        order.product_lines = [
            {
                'name': item.product.name,
                'subtitle': item.product.subtitle,
                'quantity': item.quantity,
                'unit_price': item.unit_price,
                'line_total': item.line_total,
                'unit': item.product.unit,
                'stock_left': item.product.stock,
            }
            for item in order.items.all()
        ]
        total_credit_sales += order.credit_exposure_amount
        customer_rollup = customer_rollups.setdefault(
            order.customer_id,
            {
                'customer_name': order.customer.full_name,
                'customer_phone': order.customer.phone,
                'total_credit_orders': 0,
                'on_time_payments': 0,
                'late_payments': 0,
                'open_orders': 0,
                'pending_amount': Decimal('0.00'),
                'total_credit_amount': Decimal('0.00'),
                'max_days_pending': 0,
            },
        )
        customer_rollup['total_credit_orders'] += 1
        customer_rollup['total_credit_amount'] += order.credit_exposure_amount
        customer_rollup['max_days_pending'] = max(customer_rollup['max_days_pending'], order.days_pending)
        if order.is_credit_settled:
            settled_credit_amount += order.credit_exposure_amount
            paid_on_date = timezone.localtime(order.credit_paid_at).date() if order.credit_paid_at else today
            total_payment_days += max((paid_on_date - timezone.localtime(order.created_at).date()).days, 0)
            settled_payment_count += 1
            if order.current_due_date and paid_on_date <= order.current_due_date:
                customer_rollup['on_time_payments'] += 1
            else:
                customer_rollup['late_payments'] += 1
            settled_orders.append(order)
        else:
            active_credit_exposure += order.credit_exposure_amount
            collection_request = active_khatabook_collection_request(order.khata_cycle) if order.khata_cycle_id else None
            order.collection_request = collection_request
            order.recovery_status_label = (
                collection_request.get_status_display() if collection_request is not None else 'Not started'
            )
            order.recovery_status_chip = khatabook_collection_status_chip(collection_request)
            if collection_request is not None:
                active_collection_ids.add(collection_request.id)
            if order.is_defaulted:
                defaulted_amount += order.credit_exposure_amount
                defaulted_orders.append(order)
            else:
                active_orders.append(order)
            customer_rollup['open_orders'] += 1
            customer_rollup['pending_amount'] += order.credit_exposure_amount
            if order.is_defaulted:
                customer_rollup['late_payments'] += 1

    active_orders.sort(key=lambda order: (order.current_due_date or today, order.created_at, order.id))
    defaulted_orders.sort(key=lambda order: (order.current_due_date or today, order.created_at, order.id))
    settled_orders.sort(
        key=lambda order: (order.credit_paid_at or order.updated_at or order.created_at, order.id),
        reverse=True,
    )
    unpaid_orders = sorted(
        [*defaulted_orders, *active_orders],
        key=lambda order: (
            0 if order.risk_level == 'High' else 1 if order.risk_level == 'Medium' else 2,
            -(order.days_overdue or order.days_pending),
            order.current_due_date or today,
            order.id,
        ),
    )

    for order in defaulted_orders:
        create_notification_once(
            shop_owner=shop.owner,
            title='KhataBook default alert',
            body=(
                f'{order.display_id} is overdue under KhataBook. Rs. {order.total_amount} remains unpaid, '
                f'with Rs. {order.credit_exposure_amount} counted as storefront credit exposure, '
                f'and your temporary shop risk share is Rs. {order.shop_exposure_share}.'
            ),
            notification_type=NotificationType.PAYMENT,
        )

    metrics = [
        {
            'label': 'Active exposure',
            'value': f'Rs. {active_credit_exposure}',
            'detail': 'All unpaid KhataBook orders that are still sitting on the store ledger.',
            'chip': 'warn' if active_credit_exposure else 'info',
        },
        {
            'label': 'Shop risk share',
            'value': f'Rs. {split_khatabook_exposure(active_credit_exposure)}',
            'detail': 'Your 50% share of the current live credit exposure.',
            'chip': 'warn' if active_credit_exposure else 'info',
        },
        {
            'label': 'Platform risk share',
            'value': f'Rs. {split_khatabook_exposure(active_credit_exposure)}',
            'detail': 'GramExpress carries the other 50% of the same outstanding exposure.',
            'chip': 'info',
        },
        {
            'label': 'Defaulted amount',
            'value': f'Rs. {defaulted_amount}',
            'detail': 'Credit that has already crossed the 7-day deadline without recovery.',
            'chip': 'danger' if defaulted_amount else 'success',
        },
    ]
    default_rate_percentage = (
        int(round(float((defaulted_amount / total_credit_sales) * Decimal('100'))))
        if total_credit_sales > Decimal('0.00')
        else 0
    )
    average_payment_days = (
        int(round(total_payment_days / settled_payment_count))
        if settled_payment_count
        else 0
    )
    exposure_trend = []
    max_trend_amount = Decimal('0.00')
    for offset in range(6, -1, -1):
        point_date = today - timedelta(days=offset)
        point_amount = Decimal('0.00')
        for order in credit_orders:
            opened_on = timezone.localtime(order.created_at).date()
            paid_on = timezone.localtime(order.credit_paid_at).date() if order.credit_paid_at else None
            if opened_on <= point_date and (paid_on is None or paid_on > point_date):
                point_amount += order.credit_exposure_amount
        max_trend_amount = max(max_trend_amount, point_amount)
        exposure_trend.append(
            {
                'day_label': point_date.strftime('%a'),
                'date_label': point_date.strftime('%b %d'),
                'amount': point_amount,
                'is_today': point_date == today,
            }
        )
    max_trend_amount = max(max_trend_amount, Decimal('1.00'))
    for point in exposure_trend:
        point['bar_height'] = 18 if point['amount'] <= Decimal('0.00') else max(
            18,
            int((float(point['amount']) / float(max_trend_amount)) * 100),
        )
    exposure_delta = (
        exposure_trend[-1]['amount'] - exposure_trend[0]['amount']
        if exposure_trend
        else Decimal('0.00')
    )
    customer_scores = []
    high_risk_customer_count = 0
    for rollup in customer_rollups.values():
        total_orders = rollup['total_credit_orders']
        if not total_orders:
            continue
        late_ratio = rollup['late_payments'] / total_orders
        score = 100
        score -= int(round(late_ratio * 42))
        score -= min(rollup['max_days_pending'] * 3, 24)
        if rollup['pending_amount'] >= Decimal('150.00'):
            score -= 12
        if rollup['open_orders'] >= 3:
            score -= 8
        score = max(0, min(score, 100))
        if score < 50:
            risk_label = 'High'
            risk_chip = 'danger'
            high_risk_customer_count += 1
        elif score < 75:
            risk_label = 'Medium'
            risk_chip = 'warn'
        else:
            risk_label = 'Low'
            risk_chip = 'success'
        customer_scores.append(
            {
                **rollup,
                'credit_score': score,
                'risk_level': risk_label,
                'risk_chip': risk_chip,
            }
        )
    customer_scores.sort(key=lambda item: (item['credit_score'], -float(item['pending_amount']), item['customer_name']))
    if defaulted_amount > Decimal('0.00') or default_rate_percentage >= 25 or high_risk_customer_count:
        risk_level = 'High'
        risk_chip = 'danger'
        recommended_action_message = 'Overdue credit needs immediate recovery. Pause risky customers and close the oldest open cycles first.'
    elif active_credit_exposure > Decimal('0.00') or exposure_delta > Decimal('0.00') or default_rate_percentage >= 10:
        risk_level = 'Medium'
        risk_chip = 'warn'
        recommended_action_message = 'Exposure is manageable, but you should follow up on aging credit and review customer scores this week.'
    else:
        risk_level = 'Low'
        risk_chip = 'success'
        recommended_action_message = 'Risk is under control. Keep limits steady and continue nudging payments before the due date.'
    insights = []
    if exposure_delta > Decimal('0.00'):
        insights.append(
            {
                'title': 'Exposure is increasing',
                'detail': f'Live exposure moved up by Rs. {exposure_delta} over the last 7 days. Review new open credit before it compounds.',
                'chip': 'warn',
                'icon': 'indian-rupee',
            }
        )
    else:
        insights.append(
            {
                'title': 'Exposure trend is stable',
                'detail': 'The 7-day exposure line is flat or down, which means recent recovery is keeping pace with new credit sales.',
                'chip': 'success',
                'icon': 'badge-check',
            }
        )
    if default_rate_percentage >= 15:
        insights.append(
            {
                'title': 'Default rate needs attention',
                'detail': f'Default rate is {default_rate_percentage}%. Reduce open exposure or tighten approvals for risky customers.',
                'chip': 'danger',
                'icon': 'bell',
            }
        )
    else:
        insights.append(
            {
                'title': 'Default rate is within tolerance',
                'detail': f'Current default rate is {default_rate_percentage}%. Keep reminders going before orders cross the 7-day line.',
                'chip': 'info',
                'icon': 'shield',
            }
        )
    if customer_scores and customer_scores[0]['risk_level'] == 'High':
        insights.append(
            {
                'title': 'Stop credit for the riskiest customer',
                'detail': f'{customer_scores[0]["customer_name"]} has the weakest repayment score right now. Consider manual approval before the next KhataBook order.',
                'chip': 'danger',
                'icon': 'user',
            }
        )
    else:
        insights.append(
            {
                'title': 'Credit approvals can stay fast',
                'detail': 'No customer is currently flagged as high risk. Standard approvals are still safe for most orders.',
                'chip': 'success',
                'icon': 'badge-check',
            }
        )
    suggested_credit_limit = Decimal('1500.00')
    if customer_scores:
        average_customer_exposure = sum(
            (item['total_credit_amount'] for item in customer_scores),
            Decimal('0.00'),
        ) / Decimal(str(len(customer_scores)))
        suggested_credit_limit = max(
            Decimal('500.00'),
            average_customer_exposure.quantize(Decimal('0.01')) * Decimal('1.5'),
        ).quantize(Decimal('0.01'))
    analytics_cards = [
        {
            'label': 'Total Credit Sales',
            'value': f'Rs. {total_credit_sales}',
            'detail': 'All KhataBook exposure created by this storefront so far.',
        },
        {
            'label': 'Total Recovered',
            'value': f'Rs. {settled_credit_amount}',
            'detail': 'Credit already repaid and cleared from the live ledger.',
        },
        {
            'label': 'Total Defaulted',
            'value': f'Rs. {defaulted_amount}',
            'detail': 'Credit that has crossed the due date and now sits in recovery.',
        },
        {
            'label': 'Average Payment Days',
            'value': f'{average_payment_days} days',
            'detail': 'Average time it takes customers to close a credit cycle.',
        },
    ]
    return {
        'all_orders': credit_orders,
        'active_orders': active_orders,
        'defaulted_orders': defaulted_orders,
        'settled_orders': settled_orders,
        'unpaid_orders': unpaid_orders,
        'metrics': metrics,
        'total_credit_sales': total_credit_sales,
        'active_credit_exposure': active_credit_exposure,
        'defaulted_amount': defaulted_amount,
        'settled_credit_amount': settled_credit_amount,
        'shop_risk_share': split_khatabook_exposure(active_credit_exposure),
        'platform_risk_share': split_khatabook_exposure(active_credit_exposure),
        'defaulted_shop_risk_share': split_khatabook_exposure(defaulted_amount),
        'defaulted_platform_risk_share': split_khatabook_exposure(defaulted_amount),
        'active_collection_count': len(active_collection_ids),
        'active_order_count': len(active_orders),
        'defaulted_order_count': len(defaulted_orders),
        'settled_order_count': len(settled_orders),
        'default_rate_percentage': default_rate_percentage,
        'average_payment_days': average_payment_days,
        'risk_level': risk_level,
        'risk_chip': risk_chip,
        'recommended_action_message': recommended_action_message,
        'exposure_trend': exposure_trend,
        'exposure_delta': exposure_delta,
        'analytics_cards': analytics_cards,
        'customer_scores': customer_scores[:6],
        'insights': insights,
        'suggested_credit_limit': suggested_credit_limit,
        'has_warning': defaulted_amount > Decimal('0.00'),
        'warning_headline': (
            f'Rs. {defaulted_amount} is already overdue across {len(defaulted_orders)} KhataBook order'
            f'{"s" if len(defaulted_orders) != 1 else ""}.'
            if defaulted_amount > Decimal('0.00')
            else 'No customer default is open right now.'
        ),
        'warning_detail': (
            f'Your currently exposed share inside defaulted credit is Rs. {split_khatabook_exposure(defaulted_amount)}.'
            if defaulted_amount > Decimal('0.00')
            else 'Live exposure is still within the agreed 7-day credit cycle.'
        ),
    }


def active_khatabook_collection_request(cycle: KhataBookCycle | None) -> KhataBookCollectionRequest | None:
    if cycle is None:
        return None
    return (
        cycle.collection_requests.exclude(
            status__in=[KhataBookCollectionStatus.COMPLETED, KhataBookCollectionStatus.CANCELLED]
        )
        .select_related('customer', 'rider')
        .order_by('-created_at')
        .first()
    )


def eligible_available_riders_for_collection_request(collection_request: KhataBookCollectionRequest) -> list[RiderProfile]:
    approved_riders = RiderProfile.objects.filter(
        approval_status=ApprovalStatus.APPROVED,
        is_available=True,
    )
    rider_pool = []
    approved_count = approved_riders.count()
    for rider in approved_riders:
        rider.dispatch_radius_km = rider.max_service_radius_km if approved_count < 3 else rider.service_radius_km
        rider.pickup_distance_km = kilometers_between(
            rider.latitude,
            rider.longitude,
            collection_request.latitude,
            collection_request.longitude,
        )
        if rider.pickup_distance_km <= rider.dispatch_radius_km:
            rider_pool.append(rider)
    rider_pool.sort(key=lambda candidate: (candidate.pickup_distance_km, candidate.full_name))
    return rider_pool


def enrich_khatabook_collection_request(
    collection_request: KhataBookCollectionRequest,
    *,
    rider: RiderProfile | None = None,
) -> KhataBookCollectionRequest:
    reference_rider = rider or collection_request.rider
    if reference_rider:
        collection_request.distance_km = kilometers_between(
            reference_rider.latitude,
            reference_rider.longitude,
            collection_request.latitude,
            collection_request.longitude,
        )
        collection_request.arrival_gate_open = collection_request.distance_km <= KHATABOOK_COLLECTION_GEOFENCE_KM
    else:
        collection_request.distance_km = None
        collection_request.arrival_gate_open = False
    collection_request.map_url = collection_request.customer.google_maps_url
    collection_request.status_chip = (
        'success'
        if collection_request.status == KhataBookCollectionStatus.COMPLETED
        else 'info'
        if collection_request.status == KhataBookCollectionStatus.ACCEPTED
        else 'warn'
    )
    if collection_request.status == KhataBookCollectionStatus.ACCEPTED:
        collection_request.flow_headline = 'KhataBook collection assigned'
        collection_request.flow_detail = 'Do not ask for payment on the original order. Collect the weekly KhataBook due only for this repayment request.'
    elif collection_request.status == KhataBookCollectionStatus.COMPLETED:
        collection_request.flow_headline = 'KhataBook collection completed'
        collection_request.flow_detail = 'The weekly credit due was collected and the customer ledger is now closed.'
    else:
        collection_request.flow_headline = 'KhataBook collection requested'
        collection_request.flow_detail = 'A customer nearby wants to clear the weekly KhataBook due through rider-assisted COD / UPI collection.'
    return collection_request


def build_checkout_session_payload(*, customer: CustomerProfile, cart: dict[str, Any], checkout_data: dict[str, str]) -> dict[str, Any]:
    delivery_slot = normalize_delivery_slot(checkout_data.get('delivery_slot', DEFAULT_DELIVERY_SLOT))
    snapshot = build_cart_snapshot(cart, delivery_slot=delivery_slot)
    delivery_address = build_delivery_address(customer)
    payment_method = checkout_data.get('payment_method', PaymentMethod.COD)
    customer_notes = checkout_data.get('customer_notes', '')
    amount = sum(Decimal(group['total']) for group in snapshot['groups']) if snapshot['groups'] else Decimal('0.00')
    return {
        'delivery_slot': delivery_slot,
        'payment_method': payment_method,
        'customer_notes': customer_notes,
        'delivery_address': delivery_address,
        'cart_snapshot': snapshot,
        'cart_signature': build_checkout_signature(
            snapshot=snapshot,
            payment_method=payment_method,
            customer_notes=customer_notes,
            delivery_address=delivery_address,
            delivery_slot=delivery_slot,
        ),
        'amount': amount,
        'currency': 'INR',
    }


def save_pending_checkout(request: HttpRequest, *, payment_method: str, customer_notes: str, delivery_slot: str) -> None:
    request.session[PENDING_CHECKOUT_SESSION_KEY] = {
        'delivery_slot': normalize_delivery_slot(delivery_slot),
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
    khata_cycle = next((order.khata_cycle for order in orders if order.khata_cycle_id), None)
    delivery_slot = orders[0].delivery_slot if orders else DEFAULT_DELIVERY_SLOT
    request.session[LAST_CHECKOUT_SESSION_KEY] = {
        'order_ids': [order.id for order in orders],
        'delivery_slot': delivery_slot,
        'payment_method': payment_method,
        'estimated_total': decimal_to_str(sum(order.total_amount for order in orders)) if orders else '0.00',
        'checkout_session_id': checkout_session.id if checkout_session else None,
        'khata_cycle_id': khata_cycle.id if khata_cycle else None,
        'khata_due_date': khata_cycle.due_date.isoformat() if khata_cycle else '',
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


def create_razorpay_order_for_khatabook_cycle(cycle: KhataBookCycle) -> dict[str, Any]:
    cycle = refresh_khatabook_cycle(cycle)
    if cycle.outstanding_amount <= Decimal('0.00'):
        raise CheckoutValidationError('This KhataBook cycle does not have any outstanding balance to pay.')
    payload = {
        'amount': int((cycle.outstanding_amount * 100).quantize(Decimal('1'))),
        'currency': 'INR',
        'receipt': f'grx-khata-{cycle.id}',
        'notes': {
            'khatabook_cycle_id': str(cycle.id),
            'customer_phone': cycle.customer.phone,
            'flow': 'khatabook_due',
        },
    }
    razorpay_order = razorpay_api_request(path='/orders', method='POST', payload=payload)
    cycle.razorpay_order_id = razorpay_order.get('id', '')
    cycle.failure_reason = ''
    cycle.save(update_fields=['razorpay_order_id', 'failure_reason', 'updated_at'])
    return razorpay_order


def fetch_razorpay_payment(payment_id: str) -> dict[str, Any]:
    return razorpay_api_request(path=f'/payments/{payment_id}')


def fetch_razorpay_order(order_id: str) -> dict[str, Any]:
    return razorpay_api_request(path=f'/orders/{order_id}')


def create_cod_payment_link(*, request: HttpRequest, order: Order) -> dict[str, Any]:
    if order_has_open_cod_payment_link(order):
        return {
            'id': order.cod_payment_link_id,
            'short_url': order.cod_payment_link_url,
            'status': order.cod_payment_link_status or 'created',
        }

    payload = {
        'amount': int((order.total_amount * 100).quantize(Decimal('1'))),
        'currency': 'INR',
        'accept_partial': False,
        'description': f'COD online payment for {order.display_id}',
        'reference_id': order.display_id,
        'customer': {
            'name': order.customer.full_name,
            'email': order.customer.email,
            'contact': order.customer.phone,
        },
        'notify': {
            'email': False,
            'sms': False,
        },
        'reminder_enable': False,
        'callback_url': build_order_detail_absolute_url(request, order),
        'callback_method': 'get',
        'notes': {
            'order_id': str(order.id),
            'order_display_id': order.display_id,
            'flow': 'cod_online',
        },
    }
    payment_link = razorpay_api_request(path='/payment_links', method='POST', payload=payload)
    order.cod_collection_mode = CodCollectionMode.ONLINE
    order.cod_payment_link_id = payment_link.get('id', '')
    order.cod_payment_link_url = payment_link.get('short_url', '')
    order.cod_payment_link_status = payment_link.get('status', 'created')
    order.save(
        update_fields=[
            'cod_collection_mode',
            'cod_payment_link_id',
            'cod_payment_link_url',
            'cod_payment_link_status',
            'updated_at',
        ]
    )
    return payment_link


def build_settlement_upi_url(order: Order) -> str:
    upi_id = getattr(settings, 'RAZORPAY_SETTLEMENT_UPI_ID', '').strip()
    if not upi_id:
        return ''
    params = {
        'pa': upi_id,
        'pn': getattr(settings, 'GRAMEXPRESS_APP_NAME', 'GramExpress'),
        'am': f'{order.total_amount:.2f}',
        'cu': 'INR',
        'tn': f'COD settlement {order.display_id}',
    }
    return f'upi://pay?{urllib_parse.urlencode(params)}'


def create_rider_settlement_qr(order: Order) -> dict[str, Any]:
    if order.settlement_status == SettlementStatus.QR_READY and (order.settlement_qr_id or order.settlement_qr_image_url):
        return {
            'id': order.settlement_qr_id,
            'image_url': order.settlement_qr_image_url,
            'status': 'active',
        }

    if settlement_qr_fallback_ready() and not is_razorpay_ready():
        order.settlement_status = SettlementStatus.QR_READY
        order.settlement_qr_image_url = getattr(settings, 'RAZORPAY_SETTLEMENT_QR_IMAGE_URL', '').strip()
        order.settlement_generated_at = timezone.now()
        order.save(update_fields=['settlement_status', 'settlement_qr_image_url', 'settlement_generated_at', 'updated_at'])
        return {
            'id': '',
            'image_url': order.settlement_qr_image_url,
            'status': 'active',
        }

    qr_payload = {
        'type': 'upi_qr',
        'usage': 'single_use',
        'fixed_amount': True,
        'payment_amount': int((order.total_amount * 100).quantize(Decimal('1'))),
        'name': f'{getattr(settings, "GRAMEXPRESS_APP_NAME", "GramExpress")} COD Settlement',
        'description': f'Rider settlement for {order.display_id}',
        'notes': {
            'order_id': str(order.id),
            'order_display_id': order.display_id,
            'flow': 'cod_settlement',
        },
    }
    try:
        qr_code = razorpay_api_request(path='/payments/qr_codes', method='POST', payload=qr_payload)
    except CheckoutValidationError:
        fallback_image_url = getattr(settings, 'RAZORPAY_SETTLEMENT_QR_IMAGE_URL', '').strip()
        if not fallback_image_url:
            raise
        order.settlement_status = SettlementStatus.QR_READY
        order.settlement_qr_image_url = fallback_image_url
        order.settlement_generated_at = timezone.now()
        order.save(update_fields=['settlement_status', 'settlement_qr_image_url', 'settlement_generated_at', 'updated_at'])
        return {
            'id': '',
            'image_url': fallback_image_url,
            'status': 'active',
        }
    order.settlement_status = SettlementStatus.QR_READY
    order.settlement_qr_id = qr_code.get('id', '')
    order.settlement_qr_image_url = qr_code.get('image_url', '')
    order.settlement_generated_at = timezone.now()
    order.save(
        update_fields=[
            'settlement_status',
            'settlement_qr_id',
            'settlement_qr_image_url',
            'settlement_generated_at',
            'updated_at',
        ]
    )
    return qr_code


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


def build_khatabook_razorpay_context(cycle: KhataBookCycle, customer: CustomerProfile) -> dict[str, Any]:
    return {
        'key': getattr(settings, 'RAZORPAY_KEY_ID', ''),
        'amount': int((cycle.outstanding_amount * 100).quantize(Decimal('1'))),
        'currency': 'INR',
        'name': getattr(settings, 'GRAMEXPRESS_APP_NAME', 'GramExpress'),
        'description': f'KhataBook due for week starting {cycle.week_start.strftime("%b %d")}',
        'order_id': cycle.razorpay_order_id,
        'prefill': {
            'name': customer.full_name,
            'email': customer.email,
            'contact': customer.phone,
        },
        'notes': {
            'khatabook_cycle_id': str(cycle.id),
            'due_date': cycle.due_date.isoformat(),
        },
        'theme': {
            'color': '#14532d',
        },
        'khatabook_cycle_id': cycle.id,
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


def create_khatabook_checkout_session(*, customer: CustomerProfile, cart: dict[str, Any], checkout_data: dict[str, str]) -> CheckoutSession:
    payload = build_checkout_session_payload(customer=customer, cart=cart, checkout_data=checkout_data)
    return CheckoutSession.objects.create(
        customer=customer,
        payment_method=PaymentMethod.KHATABOOK,
        payment_status=PaymentStatus.PENDING,
        amount=payload['amount'],
        currency=payload['currency'],
        customer_notes=payload['customer_notes'],
        delivery_address=payload['delivery_address'],
        cart_snapshot=payload['cart_snapshot'],
        cart_signature=payload['cart_signature'],
        receipt=f'grx-khata-{customer.id}-{int(timezone.now().timestamp())}',
    )


def build_checkout_context(
    *,
    customer: CustomerProfile,
    cart: dict[str, Any],
    checkout_data: dict[str, str],
    checkout_session: CheckoutSession | None = None,
) -> dict[str, Any]:
    selected_slot = normalize_delivery_slot(checkout_data.get('delivery_slot', DEFAULT_DELIVERY_SLOT))
    selected_slot_config = delivery_slot_config(selected_slot)
    payment_method = checkout_data.get('payment_method', PaymentMethod.COD)
    customer_notes = checkout_data.get('customer_notes', '')
    razorpay_enabled = is_razorpay_ready()
    totals = []
    estimated_total = Decimal('0.00')
    estimated_subtotal = Decimal('0.00')
    estimated_delivery_fee = Decimal('0.00')
    estimated_shopkeeper_commission_fee = Decimal('0.00')
    estimated_platform_fee = Decimal('0.00')
    for group in cart['groups']:
        fee_breakup = checkout_fee_breakup(subtotal=group['subtotal'], delivery_fee=delivery_slot_fee(selected_slot))
        totals.append(
            {
                'shop': group['shop'],
                'subtotal': fee_breakup['subtotal'],
                'delivery_fee': fee_breakup['delivery_fee'],
                'shopkeeper_commission_fee': fee_breakup['shopkeeper_commission_fee'],
                'platform_fee': fee_breakup['platform_fee'],
                'total': fee_breakup['total'],
                'item_count': sum(item['quantity'] for item in group['items']),
                'delivery_slot': selected_slot,
            }
        )
        estimated_subtotal += fee_breakup['subtotal']
        estimated_delivery_fee += fee_breakup['delivery_fee']
        estimated_shopkeeper_commission_fee += fee_breakup['shopkeeper_commission_fee']
        estimated_platform_fee += fee_breakup['platform_fee']
        estimated_total += fee_breakup['total']
    return {
        'customer': customer,
        'cart': cart,
        'checkout_data': checkout_data,
        'selected_delivery_slot': selected_slot,
        'selected_delivery_slot_config': selected_slot_config,
        'selected_delivery_slot_chip': delivery_slot_chip_class(selected_slot),
        'delivery_slot_options': delivery_slot_options(selected_slot),
        'payment_method': payment_method,
        'payment_method_label': dict(PaymentMethod.choices).get(payment_method, payment_method),
        'customer_notes': customer_notes,
        'delivery_address': build_delivery_address(customer),
        'group_totals': totals,
        'estimated_total': estimated_total,
        'estimated_subtotal': estimated_subtotal,
        'estimated_delivery_fee': estimated_delivery_fee,
        'estimated_shopkeeper_commission_fee': estimated_shopkeeper_commission_fee,
        'estimated_platform_fee': estimated_platform_fee,
        'estimated_eta': selected_slot_config['time_label'],
        'is_cod': payment_method == PaymentMethod.COD,
        'is_khatabook': payment_method == PaymentMethod.KHATABOOK,
        'razorpay_enabled': razorpay_enabled,
        'razorpay_key_id': getattr(settings, 'RAZORPAY_KEY_ID', ''),
        'checkout_session': checkout_session,
        'khatabook_due_date': next_monday(timezone.localdate()),
        'khatabook_credit_window_days': 7,
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
        if payment_method == PaymentMethod.KHATABOOK:
            order_bill_breakup = build_order_bill_breakup(order)
            create_notification(
                shop_owner=order.shop.owner,
                title='KhataBook credit order added',
                body=(
                    f'{order.display_id} entered KhataBook with Rs. {order_bill_breakup["shop_credit_exposure"]} '
                    'counted as storefront credit exposure. '
                    f'This credit stays open until {order.credit_due_date.strftime("%b %d") if order.credit_due_date else "next Monday"}.'
                ),
                notification_type=NotificationType.PAYMENT,
            )
        create_notification(
            customer=order.customer,
            order=order,
            title='Order confirmed',
            body=(
                f'Order #{order.id} from {order.shop.name} was added to KhataBook with repayment due by '
                f'{order.credit_due_date.strftime("%b %d")}.'
                if payment_method == PaymentMethod.KHATABOOK and order.credit_due_date
                else f'Order #{order.id} from {order.shop.name} was created successfully.'
            ),
            notification_type=(
                NotificationType.PAYMENT
                if payment_method in [PaymentMethod.RAZORPAY, PaymentMethod.KHATABOOK]
                else NotificationType.ORDER
            ),
        )
        for rider in eligible_available_riders(order.shop):
            create_notification(
                rider=rider,
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
        khata_cycle = None
        if locked_session.payment_method == PaymentMethod.KHATABOOK:
            khata_cycle = get_or_create_khatabook_cycle(customer=locked_session.customer)

        for group_snapshot in group_snapshots:
            shop = Shop.objects.select_related('owner').get(pk=group_snapshot['shop_id'])
            if shop.approval_status != ApprovalStatus.APPROVED or not shop.is_open:
                raise CheckoutValidationError(f'{shop.name} is no longer available for checkout.')
            order_time = timezone.now()
            delivery_slot = normalize_delivery_slot(group_snapshot.get('delivery_slot') or cart_snapshot.get('delivery_slot'))
            delivery_fee = Decimal(group_snapshot.get('delivery_fee', '0.00'))
            delivery_deadline = delivery_slot_deadline_from(order_time, delivery_slot)
            order_distance_km = Decimal(
                str(kilometers_between(shop.latitude, shop.longitude, locked_session.customer.latitude, locked_session.customer.longitude))
            ).quantize(Decimal('0.01'))

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

            order = Order.objects.create(
                customer=locked_session.customer,
                shop=shop,
                checkout_session=locked_session,
                khata_cycle=khata_cycle,
                status=OrderStatus.CONFIRMED,
                payment_method=locked_session.payment_method,
                payment_status=locked_session.payment_status,
                credit_due_date=khata_cycle.due_date if khata_cycle else None,
                delivery_slot=delivery_slot,
                delivery_deadline=delivery_deadline,
                delivery_fee=delivery_fee,
                distance_km=order_distance_km,
                delivery_address=locked_session.delivery_address,
                customer_notes=locked_session.customer_notes,
                customer_otp=generate_delivery_otp(),
                total_amount=Decimal(group_snapshot['total']),
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
            created_orders.append(order)

        locked_session.completed_at = timezone.now()
        locked_session.save(update_fields=['completed_at', 'updated_at'])
        if khata_cycle is not None:
            refresh_khatabook_cycle(khata_cycle)

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
        products = [annotate_catalog_product(product) for product in shop.products.filter(is_visible=True)]
        shop_rating = shop.orders.filter(customer_rating__isnull=False).aggregate(
            avg=Avg('customer_rating'),
            count=Count('customer_rating'),
        )
        rating_average = shop_rating['avg']
        shop.display_rating = round(float(rating_average), 1) if rating_average is not None else float(shop.rating)
        shop.rating_count = shop_rating['count'] or 0
        if not shop.image_source:
            fallback_image = next((product.image_source for product in products if product.image_source), '')
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
                'icon': 'store',
            }
        for product in products:
            category_key = (product.category or '').strip()
            if category_key and category_key not in category_map:
                category_map[category_key] = {
                    'label': category_key,
                    'slug': category_key.lower().replace(' ', '-'),
                    'icon': 'shopping-bag',
                }
            if len(category_map) >= 6:
                break
        if len(category_map) >= 6:
            continue

    cart = build_cart_context(request)
    orders = (
        customer.orders.select_related('shop', 'rider', 'checkout_session', 'khata_cycle')
        .prefetch_related('items__product')
        .all()
    )
    for order in orders:
        enrich_order_progress(order)
        if order.rider:
            order.rider_route_url = build_google_route_url(
                order.shop.latitude,
                order.shop.longitude,
                order.rider.latitude,
                order.rider.longitude,
            )

    khatabook_cycle = (
        customer.khatabook_cycles.order_by('-week_start').first()
    )
    khatabook_summary = build_khatabook_cycle_summary(khatabook_cycle)
    maybe_create_customer_khatabook_default_notification(customer)

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
        'khatabook_cycle': khatabook_cycle,
        'khatabook_summary': khatabook_summary,
        'customer_khatabook_warning': (
            {
                'title': 'KhataBook default alert',
                'detail': (
                    f'Rs. {khatabook_summary["outstanding_amount"]} is already overdue from '
                    f'{khatabook_summary["due_date"].strftime("%b %d, %Y")}.'
                ),
            }
            if khatabook_summary['is_defaulted']
            else None
        ),
    }


def shop_workspace_context(request: HttpRequest, *, editing_product_id: str | None = None) -> dict[str, Any]:
    owner = request.role_profile
    shop = (
        Shop.objects.select_related('owner')
        .prefetch_related('products', 'orders__customer', 'orders__rider', 'orders__items__product')
        .filter(owner=owner)
        .first()
    )
    if shop is None:
        raise Shop.DoesNotExist
    sync_shop_owner_approval(owner, shop)
    shop_khatabook = build_shop_khatabook_context(shop)
    approval_cards = [
        {
            'label': 'Owner approval',
            'value': owner.get_approval_status_display(),
            'detail': 'Admin approval for the shop owner account linked to this storefront.',
            'is_approved': owner.approval_status == ApprovalStatus.APPROVED,
        },
        {
            'label': 'Storefront approval',
            'value': shop.get_approval_status_display(),
            'detail': 'Store listing approval that controls whether customers can view and order from this shop.',
            'is_approved': shop.approval_status == ApprovalStatus.APPROVED,
        },
    ]
    editing_product = get_object_or_404(Product, pk=editing_product_id, shop=shop) if editing_product_id else None
    orders = list(shop.orders.all())
    for order in orders:
        enrich_order_progress(order)
        order.item_count = sum(item.quantity for item in order.items.all())
        order.can_mark_confirmed = order.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED]
        order.can_mark_packed = order.status in [OrderStatus.CONFIRMED, OrderStatus.PACKED]
        order.can_cancel_from_store = order.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PACKED]
        order.packing_priority_label = f'P{order.slot_priority}'
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
            order.fulfillment_title = 'Rider picked up and is delivering'
            order.fulfillment_hint = 'Customer and store were updated at pickup. The final step is delivery confirmation.'
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
        if order.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED]:
            order.queue_anchor_at = order.created_at
        elif order.status == OrderStatus.PACKED:
            order.queue_anchor_at = order.milestone_timestamps.get('accepted') or order.updated_at
        elif order.status == OrderStatus.OUT_FOR_DELIVERY:
            order.queue_anchor_at = order.milestone_timestamps.get('pickup') or order.updated_at
        else:
            order.queue_anchor_at = order.delivered_at or order.updated_at
        queue_age_minutes = max(int((timezone.now() - order.queue_anchor_at).total_seconds() // 60), 0)
        order.queue_age_label = elapsed_time_label(order.queue_anchor_at)
        if order.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED, OrderStatus.PACKED]:
            if queue_age_minutes >= 30:
                order.queue_priority_label = 'Needs attention'
                order.queue_priority_chip = 'warn'
            elif queue_age_minutes >= 15:
                order.queue_priority_label = 'Watch closely'
                order.queue_priority_chip = 'info'
            else:
                order.queue_priority_label = 'On track'
                order.queue_priority_chip = 'success'
        elif order.status == OrderStatus.OUT_FOR_DELIVERY:
            order.queue_priority_label = 'On the road'
            order.queue_priority_chip = 'success'
        else:
            order.queue_priority_label = 'Closed'
            order.queue_priority_chip = 'info'
        order.store_support_copy = 'Use support if packing is blocked, rider handoff is delayed, or delivery closes with an issue.'
    active_queue_sort = lambda order: (
        order.slot_priority,
        order.delivery_deadline or timezone.now() + timedelta(days=365),
        order.queue_anchor_at,
        order.id,
    )
    needs_packing_orders = sorted(
        [order for order in orders if order.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED]],
        key=active_queue_sort,
    )
    waiting_for_rider_orders = sorted(
        [order for order in orders if order.status == OrderStatus.PACKED],
        key=active_queue_sort,
    )
    out_for_delivery_orders = sorted(
        [order for order in orders if order.status == OrderStatus.OUT_FOR_DELIVERY],
        key=active_queue_sort,
    )
    slot_order_sections = build_order_slot_sections(
        [order for order in orders if order.status not in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]]
    )
    closed_orders = sorted(
        [order for order in orders if order.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]],
        key=lambda order: (order.delivered_at or order.updated_at),
        reverse=True,
    )
    products = [annotate_catalog_product(product) for product in shop.products.all()]
    notifications = list(user_notifications(request.user))
    today = timezone.localdate()
    live_product_count = sum(1 for product in products if product.is_visible)
    hidden_product_count = sum(1 for product in products if not product.is_visible)
    low_stock_products = [product for product in products if 0 < product.stock <= 10]
    out_of_stock_products = [product for product in products if product.stock <= 0]
    active_order_count = sum(
        1 for order in orders if order.status not in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]
    )
    delivered_order_count = sum(1 for order in orders if order.status == OrderStatus.DELIVERED)
    pending_orders_count = sum(1 for order in orders if order.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED])
    out_of_stock_count = len(out_of_stock_products)
    pending_deliveries_count = active_order_count
    orders_today = [
        order
        for order in orders
        if order.status != OrderStatus.CANCELLED and timezone.localtime(order.created_at).date() == today
    ]
    orders_today_count = len(orders_today)
    revenue_today = sum((order.total_amount for order in orders_today), Decimal('0.00'))
    total_revenue = sum(
        (order.total_amount for order in orders if order.status != OrderStatus.CANCELLED),
        Decimal('0.00'),
    )
    new_credit_orders_count = sum(1 for order in orders_today if order.payment_method == PaymentMethod.KHATABOOK)
    customers_count = len({order.customer_id for order in orders if order.status != OrderStatus.CANCELLED})
    rating_snapshot = shop.orders.filter(customer_rating__isnull=False).aggregate(
        avg=Avg('customer_rating'),
        count=Count('customer_rating'),
    )
    shop.display_rating = round(float(rating_snapshot['avg']), 1) if rating_snapshot['avg'] is not None else float(shop.rating)
    shop.rating_count = rating_snapshot['count'] or 0
    store_public_url = request.build_absolute_uri(reverse('core:customer_store_detail', args=[shop.slug]))
    profile_completion_checks = [
        {
            'label': 'Store details',
            'is_complete': bool(shop.name and shop.area and shop.get_shop_type_display()),
            'detail': 'Name, category, and local area are visible to customers.',
        },
        {
            'label': 'Store address',
            'is_complete': bool(shop.address_line_1 and shop.district and shop.pincode),
            'detail': 'Delivery routing uses the saved address and pincode.',
        },
        {
            'label': 'Store state',
            'is_complete': bool((shop.state or '').strip()),
            'detail': 'State helps address autofill stay more accurate for customers and riders.',
        },
        {
            'label': 'Store photo',
            'is_complete': bool(shop.image_source),
            'detail': 'A storefront photo builds trust before the first order arrives.',
        },
        {
            'label': 'Phone number',
            'is_complete': bool(owner.phone),
            'detail': 'Customers and operations can reach the shop owner when needed.',
        },
        {
            'label': 'Store description',
            'is_complete': bool((shop.description or '').strip()),
            'detail': 'Your shop summary helps customers understand what you sell.',
        },
    ]
    profile_incomplete_count = sum(1 for item in profile_completion_checks if not item['is_complete'])
    profile_completion_percent = int(
        round(((len(profile_completion_checks) - profile_incomplete_count) / len(profile_completion_checks)) * 100)
    )
    setup_checklist = [
        {
            'label': 'Owner approval',
            'is_complete': owner.approval_status == ApprovalStatus.APPROVED,
            'detail': 'Admin approval for the store owner account.',
        },
        {
            'label': 'Storefront approval',
            'is_complete': shop.approval_status == ApprovalStatus.APPROVED,
            'detail': 'Approval for the listing customers can browse and order from.',
        },
        {
            'label': 'Add products',
            'is_complete': live_product_count > 0,
            'detail': 'At least one product should be live before you promote the store.',
        },
        {
            'label': 'Finish storefront profile',
            'is_complete': profile_incomplete_count == 0,
            'detail': f'{profile_completion_percent}% of the core storefront profile is complete.',
        },
        {
            'label': 'Open the store',
            'is_complete': shop.is_open,
            'detail': 'Turn the storefront on to start receiving new customer orders.',
        },
    ]
    setup_progress_complete = sum(1 for item in setup_checklist if item['is_complete'])
    setup_progress_total = len(setup_checklist)
    setup_progress_percent = int(round((setup_progress_complete / setup_progress_total) * 100))
    approval_timeline = [
        {
            'label': 'Store submitted',
            'value': 'Completed',
            'detail': 'The store workspace exists and is ready for operational review.',
            'chip': 'success',
        },
        {
            'label': 'Owner approval',
            'value': owner.get_approval_status_display(),
            'detail': 'This governs the store owner account attached to the workspace.',
            'chip': 'success' if owner.approval_status == ApprovalStatus.APPROVED else 'warn',
        },
        {
            'label': 'Storefront approval',
            'value': shop.get_approval_status_display(),
            'detail': 'This controls whether customers can find and order from the store.',
            'chip': 'success' if shop.approval_status == ApprovalStatus.APPROVED else 'warn',
        },
        {
            'label': 'Go Live status',
            'value': 'Live' if shop.approval_status == ApprovalStatus.APPROVED and shop.is_open else 'Not live',
            'detail': (
                'Customers can browse and place orders right now.'
                if shop.approval_status == ApprovalStatus.APPROVED and shop.is_open
                else 'The workspace is still waiting on approval, catalog setup, or the open-store toggle.'
            ),
            'chip': 'success' if shop.approval_status == ApprovalStatus.APPROVED and shop.is_open else 'info',
        },
    ]
    pending_approvals_count = sum(1 for card in approval_cards if not card['is_approved'])
    if shop.approval_status != ApprovalStatus.APPROVED or owner.approval_status != ApprovalStatus.APPROVED:
        go_live_status = {
            'title': 'Approval in progress',
            'detail': 'Use store settings to keep your details accurate while the review finishes.',
            'chip': 'warn',
            'action_label': 'Edit Store',
            'action_url': reverse('core:shop_settings'),
        }
    elif live_product_count == 0:
        go_live_status = {
            'title': 'Add products to go live confidently',
            'detail': 'Your store can open now, but adding products first will make the first customer visit useful.',
            'chip': 'info',
            'action_label': 'Add Product',
            'action_url': reverse('core:shop_products'),
        }
    elif shop.is_open:
        go_live_status = {
            'title': 'Store is live',
            'detail': f'Customers can order now and {live_product_count} product{"s" if live_product_count != 1 else ""} are visible.',
            'chip': 'success',
            'action_label': 'Open Orders',
            'action_url': reverse('core:shop_orders'),
        }
    else:
        go_live_status = {
            'title': 'Ready to go live',
            'detail': 'Approvals are done and products are ready. Turn the store on when the team is ready for orders.',
            'chip': 'info',
            'action_label': 'Open Store',
            'action_url': reverse('core:shop_dashboard'),
        }
    quick_actions = [
        {
            'label': 'Add Product',
            'detail': 'Add new items, prices, stock, and tags to the live catalog.',
            'url': reverse('core:shop_products'),
            'icon': 'plus',
        },
        {
            'label': 'Open Orders',
            'detail': 'Review new requests, packing flow, and rider handoff in one queue.',
            'url': reverse('core:shop_orders'),
            'icon': 'clipboard-list',
        },
        {
            'label': 'Share Store Link',
            'detail': 'Copy a direct store link that signed-in customers can open immediately.',
            'url': reverse('core:customer_store_detail', args=[shop.slug]),
            'icon': 'store',
            'copy_text': store_public_url,
            'copy_label': 'Copy Link',
        },
        {
            'label': 'Add Credit Customer',
            'detail': 'Jump into KhataBook to monitor credit orders and recovery progress.',
            'url': reverse('core:shop_khatabook'),
            'icon': 'wallet',
        },
        {
            'label': 'Update Store Details',
            'detail': 'Refresh address, photos, description, and storefront readiness.',
            'url': reverse('core:shop_settings'),
            'icon': 'square-pen',
        },
    ]
    today_summary = [
        {
            'label': 'Orders Today',
            'value': orders_today_count,
            'detail': (
                'No orders yet. Share your store link to start receiving orders.'
                if orders_today_count == 0
                else 'Orders placed today across all payment methods.'
            ),
            'chip': 'info' if orders_today_count == 0 else 'success',
        },
        {
            'label': 'Revenue Today',
            'value': f'Rs. {revenue_today}',
            'detail': 'Today\'s revenue from non-cancelled orders.',
            'chip': 'success' if revenue_today > Decimal('0.00') else 'info',
        },
        {
            'label': 'Pending Deliveries',
            'value': pending_deliveries_count,
            'detail': 'All active orders that still need packing, pickup, or final delivery.',
            'chip': 'warn' if pending_deliveries_count else 'success',
        },
        {
            'label': 'New Credit Orders',
            'value': new_credit_orders_count,
            'detail': (
                'No credit orders yet. Credit activity will appear here.'
                if new_credit_orders_count == 0
                else 'KhataBook orders created today.'
            ),
            'chip': 'warn' if new_credit_orders_count else 'info',
        },
    ]
    business_overview = [
        {
            'label': 'Total Orders',
            'value': len(orders),
            'detail': 'All orders received so far in this storefront.',
        },
        {
            'label': 'Total Revenue',
            'value': f'Rs. {total_revenue}',
            'detail': 'Gross order value excluding cancelled orders.',
        },
        {
            'label': 'Products Live',
            'value': live_product_count,
            'detail': (
                'No products added. Add your first product to go live.'
                if live_product_count == 0
                else 'Products currently listed in the storefront catalog.'
            ),
        },
        {
            'label': 'Store Rating',
            'value': f'{shop.display_rating:.1f}',
            'detail': (
                f'Based on {shop.rating_count} customer rating{"s" if shop.rating_count != 1 else ""}.'
                if shop.rating_count
                else 'No customer ratings yet. The default score is showing for now.'
            ),
        },
        {
            'label': 'Customers',
            'value': customers_count,
            'detail': 'Unique customers who have placed at least one non-cancelled order.',
        },
    ]
    attention_cards = [
        {
            'label': 'Pending Orders',
            'value': pending_orders_count,
            'detail': (
                'Orders are waiting for confirmation or packing.'
                if pending_orders_count
                else 'No pending orders are waiting on the store right now.'
            ),
            'chip': 'warn' if pending_orders_count else 'success',
            'url': reverse('core:shop_orders'),
        },
        {
            'label': 'Products Out of Stock',
            'value': out_of_stock_count,
            'detail': (
                'Some products need stock updates before customers hit a dead end.'
                if out_of_stock_count
                else 'Catalog stock looks healthy right now.'
            ),
            'chip': 'danger' if out_of_stock_count else 'success',
            'url': reverse('core:shop_products'),
        },
        {
            'label': 'Profile Incomplete',
            'value': profile_incomplete_count,
            'detail': (
                f'{profile_completion_percent}% of the storefront profile is complete.'
                if profile_incomplete_count
                else 'Storefront profile is complete and customer-facing.'
            ),
            'chip': 'warn' if profile_incomplete_count else 'success',
            'url': reverse('core:shop_settings'),
        },
        {
            'label': 'Pending Approvals',
            'value': pending_approvals_count,
            'detail': (
                'One or more approval steps are still in review.'
                if pending_approvals_count
                else 'Owner and storefront approvals are complete.'
            ),
            'chip': 'warn' if pending_approvals_count else 'success',
            'url': reverse('core:shop_settings'),
        },
    ]
    notification_groups = [
        {
            'label': 'Recent Activities',
            'items': notifications[:4],
            'empty_message': 'Recent store activity will appear here.',
        },
        {
            'label': 'Approval Updates',
            'items': [note for note in notifications if note.notification_type in [NotificationType.STORE, NotificationType.SYSTEM]][:3],
            'empty_message': 'Approval updates will appear here once review activity happens.',
        },
        {
            'label': 'Order Notifications',
            'items': [note for note in notifications if note.notification_type in [NotificationType.ORDER, NotificationType.RIDER]][:3],
            'empty_message': 'Order alerts will appear here when customers place or update orders.',
        },
        {
            'label': 'Payment Notifications',
            'items': [note for note in notifications if note.notification_type == NotificationType.PAYMENT][:3],
            'empty_message': 'Payment and KhataBook updates will appear here.',
        },
    ]
    return {
        'shop': shop,
        'orders': orders,
        'slot_order_sections': slot_order_sections,
        'order_sections': [
            {
                'label': 'Needs packing',
                'eyebrow': 'Store action',
                'description': 'Orders that still need confirmation or packing before rider handoff.',
                'orders': needs_packing_orders,
            },
            {
                'label': 'Waiting for rider or pickup',
                'eyebrow': 'Dispatch ready',
                'description': 'Orders that are packed and either waiting for rider acceptance or handoff at the store.',
                'orders': waiting_for_rider_orders,
            },
            {
                'label': 'Out for delivery',
                'eyebrow': 'On the road',
                'description': 'Orders already picked up by the rider and moving to the customer.',
                'orders': out_for_delivery_orders,
            },
            {
                'label': 'Closed orders',
                'eyebrow': 'History',
                'description': 'Delivered and cancelled orders stay here for review and ratings.',
                'orders': closed_orders,
            },
        ],
        'editing_product': editing_product,
        'notifications': notifications,
        'notification_groups': notification_groups,
        'live_product_count': live_product_count,
        'hidden_product_count': hidden_product_count,
        'catalog_products': products,
        'low_stock_products': low_stock_products,
        'out_of_stock_products': out_of_stock_products,
        'approval_cards': approval_cards,
        'approval_timeline': approval_timeline,
        'setup_checklist': setup_checklist,
        'setup_progress_complete': setup_progress_complete,
        'setup_progress_total': setup_progress_total,
        'setup_progress_percent': setup_progress_percent,
        'go_live_status': go_live_status,
        'quick_actions': quick_actions,
        'today_summary': today_summary,
        'business_overview': business_overview,
        'attention_cards': attention_cards,
        'store_public_url': store_public_url,
        'profile_completion_checks': profile_completion_checks,
        'profile_completion_percent': profile_completion_percent,
        'profile_incomplete_count': profile_incomplete_count,
        'location_ready_for_go_live': shop_location_is_configured(shop),
        'shop_khatabook': shop_khatabook,
        'active_order_count': active_order_count,
        'delivered_order_count': delivered_order_count,
        'dashboard_role': RoleType.SHOP,
        'page_nav': shop_page_nav(),
    }


def redirect_missing_shop_setup(request: HttpRequest) -> HttpResponse:
    messages.info(request, 'Complete your store details to open the store workspace.')
    return redirect('core:shop_start')


def rider_workspace_context(request: HttpRequest) -> dict[str, Any]:
    rider = request.role_profile
    slot_filter = normalize_delivery_slot(request.GET.get('slot', '')) if request.GET.get('slot') else ''
    active_riders = RiderProfile.objects.filter(approval_status=ApprovalStatus.APPROVED, is_available=True).count()
    dispatch_radius = rider.max_service_radius_km if active_riders < 3 else rider.service_radius_km
    order_candidates = (
        Order.objects.filter(
            status__in=[OrderStatus.CONFIRMED, OrderStatus.PACKED, OrderStatus.OUT_FOR_DELIVERY],
        )
        .select_related('customer', 'shop', 'rider', 'checkout_session', 'khata_cycle')
        .prefetch_related('items__product')
    )
    available_orders = []
    active_orders = []
    completed_orders = []
    available_khatabook_requests = []
    active_khatabook_requests = []
    completed_khatabook_requests = []
    if rider.approval_status == ApprovalStatus.APPROVED:
        for order in order_candidates:
            enrich_rider_order(order, rider)
            if order.rider_id == rider.id:
                active_orders.append(order)
            elif order.rider_id is None and order.pickup_distance_km <= dispatch_radius:
                available_orders.append(order)
        collection_candidates = (
            KhataBookCollectionRequest.objects.filter(
                status__in=[KhataBookCollectionStatus.REQUESTED, KhataBookCollectionStatus.ACCEPTED]
            )
            .select_related('customer', 'khata_cycle', 'rider')
        )
        for collection_request in collection_candidates:
            if (
                collection_request.status == KhataBookCollectionStatus.ACCEPTED
                and collection_request.rider_id
                and not collection_request.collection_otp
            ):
                ensure_khatabook_collection_otp_ready(
                    collection_request=collection_request,
                    rider=collection_request.rider,
                )
                collection_request.refresh_from_db()
            enrich_khatabook_collection_request(collection_request, rider=rider)
            if collection_request.rider_id == rider.id:
                active_khatabook_requests.append(collection_request)
            elif (
                collection_request.rider_id is None
                and rider.is_available
                and collection_request.distance_km is not None
                and collection_request.distance_km <= dispatch_radius
            ):
                available_khatabook_requests.append(collection_request)
    available_orders.sort(
        key=lambda order: (
            order.slot_priority,
            order.delivery_deadline or timezone.now() + timedelta(days=365),
            order.pickup_distance_km,
            order.id,
        )
    )
    available_khatabook_requests.sort(key=lambda collection_request: (collection_request.distance_km or 9999, collection_request.id))
    active_orders.sort(key=order_slot_sort_key)
    active_khatabook_requests.sort(key=lambda collection_request: (collection_request.created_at, collection_request.id))
    filtered_active_orders = [order for order in active_orders if not slot_filter or order.delivery_slot == slot_filter]
    active_orders_by_slot = build_order_slot_sections(filtered_active_orders if slot_filter else active_orders)
    completed_queryset = (
        rider.orders.filter(status=OrderStatus.DELIVERED)
        .select_related('customer', 'shop', 'checkout_session', 'khata_cycle')
        .prefetch_related('items__product')
        .order_by('-delivered_at', '-updated_at')
    )
    for order in completed_queryset:
        enrich_rider_order(order, rider)
        completed_orders.append(order)
    completed_collection_queryset = (
        rider.khatabook_collection_requests.filter(status=KhataBookCollectionStatus.COMPLETED)
        .select_related('customer', 'khata_cycle')
        .order_by('-completed_at', '-updated_at')
    )
    for collection_request in completed_collection_queryset:
        enrich_khatabook_collection_request(collection_request, rider=rider)
        completed_khatabook_requests.append(collection_request)

    completed_delivery_count = len(completed_orders)
    completed_credit_delivery_count = sum(1 for order in completed_orders if order.payment_method == PaymentMethod.KHATABOOK)
    completed_direct_payment_delivery_count = sum(1 for order in completed_orders if order.payment_method != PaymentMethod.KHATABOOK)
    completed_khatabook_collection_count = len(completed_khatabook_requests)
    today = timezone.localdate()
    commission_earnings = quantize_money(Decimal(completed_delivery_count) * RIDER_COMMISSION_PER_DELIVERY)
    total_distance_incentive = quantize_money(
        sum((order.rider_distance_incentive for order in completed_orders), Decimal('0.00'))
    )
    total_peak_time_bonus = quantize_money(
        sum((order.rider_peak_time_bonus for order in completed_orders), Decimal('0.00'))
    )
    khatabook_collection_incentive = quantize_money(
        Decimal(completed_khatabook_collection_count) * RIDER_KHATABOOK_COLLECTION_INCENTIVE
    )
    incentive_earned = quantize_money(
        total_distance_incentive + total_peak_time_bonus + khatabook_collection_incentive
    )
    bonus_earned = rider_high_completion_bonus(completed_delivery_count)
    penalty_amount = Decimal('0.00')
    final_payout = quantize_money(commission_earnings + bonus_earned + incentive_earned - penalty_amount)
    today_completed_orders = [
        order
        for order in completed_orders
        if order.delivered_at and timezone.localtime(order.delivered_at).date() == today
    ]
    today_khatabook_collections = [
        collection_request
        for collection_request in completed_khatabook_requests
        if collection_request.completed_at and timezone.localtime(collection_request.completed_at).date() == today
    ]
    today_commission_earnings = quantize_money(Decimal(len(today_completed_orders)) * RIDER_COMMISSION_PER_DELIVERY)
    today_distance_incentive = quantize_money(
        sum((order.rider_distance_incentive for order in today_completed_orders), Decimal('0.00'))
    )
    today_peak_time_bonus = quantize_money(
        sum((order.rider_peak_time_bonus for order in today_completed_orders), Decimal('0.00'))
    )
    today_khatabook_collection_incentive = quantize_money(
        Decimal(len(today_khatabook_collections)) * RIDER_KHATABOOK_COLLECTION_INCENTIVE
    )
    today_incentive_earnings = quantize_money(
        today_distance_incentive + today_peak_time_bonus + today_khatabook_collection_incentive
    )
    today_earnings = quantize_money(today_commission_earnings + today_incentive_earnings)
    today_distance_travelled_km = sum(
        (
            Decimal(
                str(
                    kilometers_between(
                        order.shop.latitude,
                        order.shop.longitude,
                        order.customer.latitude,
                        order.customer.longitude,
                    )
                )
            )
            for order in today_completed_orders
        ),
        Decimal('0.0'),
    ).quantize(Decimal('0.1'))
    average_earnings = (
        (final_payout / len(completed_orders)).quantize(Decimal('0.01'))
        if completed_orders
        else Decimal('0.00')
    )
    approved_riders = list(
        RiderProfile.objects.filter(approval_status=ApprovalStatus.APPROVED)
        .only('id', 'full_name')
        .order_by('id')
    )
    peer_rider_count = len(approved_riders) or 1
    peer_completed_orders = list(
        Order.objects.filter(
            status=OrderStatus.DELIVERED,
            rider__approval_status=ApprovalStatus.APPROVED,
            rider__isnull=False,
        )
        .select_related('rider')
        .only('id', 'rider_id', 'delivery_fee')
    )
    peer_commission_by_rider: dict[int, Decimal] = defaultdict(lambda: Decimal('0.00'))
    peer_completed_count_by_rider: dict[int, int] = defaultdict(int)
    for peer_order in peer_completed_orders:
        peer_commission_by_rider[peer_order.rider_id] += RIDER_COMMISSION_PER_DELIVERY
        peer_completed_count_by_rider[peer_order.rider_id] += 1

    platform_completed_order_count = len(peer_completed_orders)
    total_peer_commission = sum(peer_commission_by_rider.values(), Decimal('0.00'))
    peer_average_commission = quantize_money(total_peer_commission / Decimal(peer_rider_count))
    peer_average_completed_deliveries = quantize_percent(Decimal(platform_completed_order_count) / Decimal(peer_rider_count))
    peer_commission_delta = quantize_money(commission_earnings - peer_average_commission)
    peer_completed_delta = quantize_percent(Decimal(completed_delivery_count) - peer_average_completed_deliveries)
    peer_commission_delta_abs = quantize_money(abs(peer_commission_delta))
    peer_completed_delta_abs = quantize_percent(abs(peer_completed_delta))
    rider_peer_rank = 1 + sum(
        1
        for approved_rider in approved_riders
        if peer_commission_by_rider[approved_rider.id] > commission_earnings
    )
    if bonus_earned > 0:
        payout_status_label = 'Performance bonus active'
        payout_status_detail = 'Your completed-delivery volume unlocked a performance bonus on top of commission and incentives.'
        payout_status_tone = 'success'
    elif incentive_earned > 0:
        payout_status_label = 'Incentives active'
        payout_status_detail = 'This payout includes variable incentives from distance, peak-hour, or KhataBook recovery work.'
        payout_status_tone = 'info'
    else:
        payout_status_label = 'Commission only'
        payout_status_detail = 'This payout currently comes from completed-delivery commission only.'
        payout_status_tone = 'warn'
    dashboard_queue = []
    for order in available_orders:
        dashboard_queue.append(
            {
                'kind': 'order',
                'display_id': order.display_id,
                'pickup_label': order.shop.name,
                'pickup_detail': order.pickup_address,
                'drop_label': order.customer.full_name,
                'drop_detail': order.dropoff_address,
                'distance_km': order.pickup_distance_km,
                'distance_label': f'{order.pickup_distance_km} km away',
                'payment_label': order.dashboard_payment_label,
                'payment_chip': order.dashboard_payment_chip,
                'accept_url': reverse('core:rider_accept_order', args=[order.id]),
                'accept_label': 'Accept',
            }
        )
    for collection_request in available_khatabook_requests:
        dashboard_queue.append(
            {
                'kind': 'collection',
                'display_id': collection_request.display_id,
                'pickup_label': 'Current dispatch point',
                'pickup_detail': 'Recovery task starts from your saved dispatch location.',
                'drop_label': collection_request.customer.full_name,
                'drop_detail': collection_request.collection_address,
                'distance_km': collection_request.distance_km or Decimal('0.0'),
                'distance_label': f'{collection_request.distance_km} km away' if collection_request.distance_km is not None else 'Nearby',
                'payment_label': 'KhataBook',
                'payment_chip': 'rider-payment-chip-khata',
                'accept_url': reverse('core:rider_accept_khatabook_collection', args=[collection_request.id]),
                'accept_label': 'Accept Collection',
            }
        )
    dashboard_queue.sort(key=lambda job: (job['distance_km'], job['display_id']))
    return {
        'rider': rider,
        'available_orders': available_orders,
        'available_khatabook_requests': available_khatabook_requests,
        'active_orders': filtered_active_orders,
        'all_active_orders': active_orders,
        'active_orders_by_slot': active_orders_by_slot,
        'active_khatabook_requests': active_khatabook_requests,
        'priority_order': filtered_active_orders[0] if filtered_active_orders else (active_orders[0] if active_orders else None),
        'priority_khatabook_request': active_khatabook_requests[0] if active_khatabook_requests else None,
        'completed_orders': completed_orders,
        'completed_khatabook_requests': completed_khatabook_requests,
        'location_form': RiderLocationForm(initial={'latitude': rider.latitude, 'longitude': rider.longitude}),
        'google_maps_browser_api_key': getattr(settings, 'GOOGLE_MAPS_BROWSER_API_KEY', ''),
        'notifications': user_notifications(request.user),
        'dispatch_radius': dispatch_radius,
        'today_completed_delivery_count': len(today_completed_orders),
        'today_khatabook_collection_count': len(today_khatabook_collections),
        'today_distance_travelled_km': today_distance_travelled_km,
        'dashboard_queue': dashboard_queue,
        'delivery_history': completed_orders[:6],
        'completed_delivery_count': completed_delivery_count,
        'completed_credit_delivery_count': completed_credit_delivery_count,
        'completed_direct_payment_delivery_count': completed_direct_payment_delivery_count,
        'completed_khatabook_collection_count': completed_khatabook_collection_count,
        'slot_filter': slot_filter,
        'delivery_slot_filters': delivery_slot_options(slot_filter or DEFAULT_DELIVERY_SLOT),
        'new_order_count': len(available_orders),
        'new_khatabook_collection_count': len(available_khatabook_requests),
        'active_order_count': len(active_orders),
        'active_khatabook_collection_count': len(active_khatabook_requests),
        'today_earnings': today_earnings,
        'total_earnings': final_payout,
        'commission_earnings': commission_earnings,
        'average_earnings': average_earnings,
        'delivery_fee_per_order': RIDER_COMMISSION_PER_DELIVERY,
        'bonus_earned': bonus_earned,
        'performance_bonus': bonus_earned,
        'distance_incentive_earned': total_distance_incentive,
        'peak_time_bonus_earned': total_peak_time_bonus,
        'khatabook_collection_incentive_earned': khatabook_collection_incentive,
        'incentive_earned': incentive_earned,
        'penalty_amount': penalty_amount,
        'final_payout': final_payout,
        'today_commission_earnings': today_commission_earnings,
        'today_distance_incentive': today_distance_incentive,
        'today_peak_time_bonus': today_peak_time_bonus,
        'today_khatabook_collection_incentive': today_khatabook_collection_incentive,
        'today_incentive_earnings': today_incentive_earnings,
        'platform_completed_order_count': platform_completed_order_count,
        'peer_rider_count': peer_rider_count,
        'peer_average_commission': peer_average_commission,
        'peer_average_completed_deliveries': peer_average_completed_deliveries,
        'peer_commission_delta': peer_commission_delta,
        'peer_completed_delta': peer_completed_delta,
        'peer_commission_delta_abs': peer_commission_delta_abs,
        'peer_completed_delta_abs': peer_completed_delta_abs,
        'peer_commission_is_ahead': peer_commission_delta >= 0,
        'peer_completed_is_ahead': peer_completed_delta >= 0,
        'rider_peer_rank': rider_peer_rank,
        'payout_status_label': payout_status_label,
        'payout_status_detail': payout_status_detail,
        'payout_status_tone': payout_status_tone,
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
    milestones = getattr(order, 'milestone_timestamps', None) or build_order_milestone_timestamps(order)
    events = [
        {
            'key': 'placed',
            'label': 'Order placed',
            'caption': f'{order.display_id} was created successfully and sent to the store.',
            'completed': True,
            'current': not order.rider_id and order.status != OrderStatus.CANCELLED,
            'timestamp': milestones.get('placed'),
        },
        {
            'key': 'accepted',
            'label': 'Rider accepted',
            'caption': (
                f'{order.rider.full_name} accepted the order and is heading to the store.'
                if order.rider_id
                else 'Waiting for a nearby rider to accept this order.'
            ),
            'completed': bool(order.rider_id),
            'current': bool(order.rider_id) and order.status not in [OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED, OrderStatus.CANCELLED],
            'timestamp': milestones.get('accepted'),
        },
        {
            'key': 'transit',
            'label': 'Pickup confirmed',
            'caption': 'Rider arrived at the store, collected the order, and is moving toward the customer.',
            'completed': order.status in [OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED],
            'current': order.status == OrderStatus.OUT_FOR_DELIVERY,
            'timestamp': milestones.get('pickup'),
        },
        {
            'key': 'delivered',
            'label': 'Delivered',
            'caption': 'Order handoff completed successfully.',
            'completed': order.status == OrderStatus.DELIVERED,
            'current': order.status == OrderStatus.DELIVERED,
            'timestamp': milestones.get('delivered'),
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
                'timestamp': milestones.get('cancelled'),
            }
        )
    return events


def build_order_eta_label(order: Order) -> str:
    if getattr(order, 'is_deadline_overdue', False):
        return 'Overdue'
    if getattr(order, 'time_remaining_label', '') and order.status not in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]:
        return order.time_remaining_label
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
            'title': 'Rider picked up your order',
            'caption': 'The pickup is complete. Keep your OTP ready for handoff.',
            'detail': 'The app and your email both update at this stage so you know the order is now moving to your address.',
            'chip_class': 'info',
        }
    if order.status == OrderStatus.PACKED:
        return {
            'title': 'Rider accepted the order',
            'caption': 'The order is assigned and the rider is heading to the store.',
            'detail': 'The next rider update will appear when pickup is confirmed in the app.',
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
    reference = order_payment_reference(order)
    if order.payment_method == PaymentMethod.COD:
        if order.cod_collection_mode == CodCollectionMode.ONLINE:
            if order.payment_status == PaymentStatus.PAID:
                return {
                    'label': 'COD paid online',
                    'detail': 'The customer completed the emailed Razorpay payment link for this order.',
                    'chip_class': 'success',
                    'status_label': 'Paid online',
                    'reference': reference,
                    'link_url': order.cod_payment_link_url,
                    'link_label': 'Open payment link',
                }
            return {
                'label': 'COD online payment requested',
                'detail': 'The rider sent a Razorpay payment link to the customer and both dashboards update after payment succeeds.',
                'chip_class': 'info',
                'status_label': 'Payment link sent',
                'reference': reference,
                'link_url': order.cod_payment_link_url,
                'link_label': 'Open payment link',
            }
        if order.cod_collection_mode == CodCollectionMode.CASH:
            if order.settlement_status == SettlementStatus.PAID:
                return {
                    'label': 'Cash paid and settled',
                    'detail': 'The customer paid cash at handoff and the rider settled the amount back to GramExpress.',
                    'chip_class': 'success',
                    'status_label': 'Settled',
                    'reference': order.settlement_payment_id or reference,
                    'link_url': '',
                    'link_label': '',
                }
            return {
                'label': 'Cash paid at handoff',
                'detail': 'The customer confirmed cash payment. The rider now sees a Razorpay settlement QR in the rider dashboard.',
                'chip_class': 'warn',
                'status_label': 'Rider settlement pending',
                'reference': order.settlement_payment_id or reference,
                'link_url': '',
                'link_label': '',
            }
        return {
            'label': 'Cash on delivery',
            'detail': 'The rider can either email a Razorpay payment link or collect cash and wait for customer cash confirmation.',
            'chip_class': 'warn',
            'status_label': 'Pending',
            'reference': reference,
            'link_url': '',
            'link_label': '',
        }
    if order.payment_method == PaymentMethod.KHATABOOK:
        if order.payment_status == PaymentStatus.PAID:
            return {
                'label': 'KhataBook settled',
                'detail': 'This platform credit order has been repaid successfully for the weekly KhataBook cycle.',
                'chip_class': 'success',
                'status_label': 'Paid',
                'reference': reference,
                'link_url': '',
                'link_label': '',
            }
        due_label = order.credit_due_date.strftime('%b %d') if order.credit_due_date else 'the next Monday'
        return {
            'label': 'Added to KhataBook',
            'detail': f'This order is on a 7-day credit line. The amount stays due until {due_label}.',
            'chip_class': 'warn',
            'status_label': 'Credit open',
            'reference': reference,
            'link_url': '',
            'link_label': 'Open KhataBook',
        }
    if order.payment_status == PaymentStatus.PAID:
        return {
            'label': 'Paid online',
            'detail': 'Online payment was captured successfully for this order.',
            'chip_class': 'success',
            'status_label': order.get_payment_status_display(),
            'reference': reference,
            'link_url': '',
            'link_label': '',
        }
    if order.payment_status == PaymentStatus.FAILED:
        return {
            'label': 'Payment failed',
            'detail': 'This online payment did not complete successfully.',
            'chip_class': 'warn',
            'status_label': order.get_payment_status_display(),
            'reference': reference,
            'link_url': '',
            'link_label': '',
        }
    return {
        'label': 'Online payment pending',
        'detail': 'Payment is still waiting for a confirmed result.',
        'chip_class': 'info',
        'status_label': order.get_payment_status_display(),
        'reference': reference,
        'link_url': '',
        'link_label': '',
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

def eligible_available_riders(shop: Shop):
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
    return rider_pool


def nearest_available_rider(shop: Shop):
    rider_pool = eligible_available_riders(shop)
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

    if request.GET.get('reset') == '1':
        request.session.pop(PENDING_LOGIN_SESSION_KEY, None)

    pending_login = request.session.get(PENDING_LOGIN_SESSION_KEY)
    if pending_login and request.method == 'GET':
        return redirect('core:login_verify')

    login_form = LoginForm(
        initial={
            'identity': request.GET.get('email')
            or request.GET.get('identity')
            or (pending_login or {}).get('email', '')
        }
    )

    if request.method == 'POST':
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
                        return redirect('core:login_verify')
                    token.delete()
                    messages.error(request, detail)
                else:
                    request.session.pop(PENDING_LOGIN_SESSION_KEY, None)
                    login(request, authenticated)
                    messages.success(request, 'Signed in successfully.')
                    return redirect(get_dashboard_url_for_user(authenticated))

    return disable_html_cache(
        render(
            request,
            'core/login.html',
            {
                'form': login_form,
                'google_client_id': getattr(settings, 'GOOGLE_CLIENT_ID', ''),
            },
        )
    )


def login_verify_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_for_user(request.user))

    pending_login = request.session.get(PENDING_LOGIN_SESSION_KEY)
    if not pending_login:
        messages.error(request, 'Your email sign-in session expired. Please enter your details again.')
        return redirect('core:login')

    user = get_user_model().objects.filter(pk=pending_login.get('user_id')).first()
    if not user:
        request.session.pop(PENDING_LOGIN_SESSION_KEY, None)
        messages.error(request, 'That email login session is no longer valid.')
        return redirect('core:login')

    otp_form = LoginOtpVerifyForm()
    if request.method == 'POST':
        action = request.POST.get('action', 'verify_login_otp')
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
                return redirect('core:login_verify')
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

    return disable_html_cache(
        render(
            request,
            'core/login_verify.html',
            {
                'otp_form': otp_form,
                'pending_login_masked_email': mask_email(pending_login['email']),
                'pending_login_role_label': role_label(get_role_profile(user)[0] or ''),
                'otp_expiry_minutes': getattr(settings, 'OTP_EXPIRY_MINUTES', 10),
            },
        )
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
    return disable_html_cache(
        render(
            request,
            'core/register.html',
            {
                'role_cards': registration_role_links(
                    full_name=request.GET.get('full_name', '').strip(),
                    email=request.GET.get('email', '').strip(),
                    selected_role=request.GET.get('account_type', '').strip(),
                ),
                'pending_registration': request.session.get(PENDING_REGISTRATION_SESSION_KEY, {}),
                'google_client_id': getattr(settings, 'GOOGLE_CLIENT_ID', ''),
            },
        )
    )


def register_details_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_for_user(request.user))

    pending_registration = request.session.get(PENDING_REGISTRATION_SESSION_KEY, {})
    selected_role = (
        request.POST.get('account_type')
        or request.GET.get('account_type')
        or pending_registration.get('account_type', '')
    )
    if selected_role not in ACCOUNT_ROLE_CHOICES:
        messages.info(request, 'Choose a role before continuing with registration.')
        return redirect('core:register')

    initial_data = {
        'account_type': selected_role,
        'full_name': request.GET.get('full_name', ''),
        'email': request.GET.get('email', ''),
        'latitude': DEFAULT_LATITUDE,
        'longitude': DEFAULT_LONGITUDE,
    }
    if pending_registration.get('account_type') == selected_role:
        initial_data.update(pending_registration)

    form = UnifiedRegistrationForm(initial=initial_data, selected_role=selected_role)

    if request.method == 'POST':
        form = UnifiedRegistrationForm(request.POST, selected_role=selected_role)
        if form.is_valid():
            cleaned_data = form.cleaned_data.copy()
            cleaned_data['phone'] = normalize_phone(cleaned_data['phone'])
            cleaned_data['email'] = cleaned_data['email'].strip().lower()
            conflicts = contact_conflicts(phone=cleaned_data['phone'], email=cleaned_data['email'])
            if conflicts['phone']:
                form.add_error('phone', 'This mobile number is already linked to an existing account.')
            if conflicts['email']:
                form.add_error('email', 'This email address is already linked to an existing account.')
            if not any(conflicts.values()):
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
                    return redirect('core:register_verify')
                token.delete()
                form.add_error(None, detail)

    return disable_html_cache(
        render(
            request,
            registration_details_template(selected_role),
            {
                'form': form,
                'selected_role': selected_role,
                'selected_role_label': role_label(selected_role),
                'selected_role_copy': REGISTRATION_ROLE_ONBOARDING_COPY.get(selected_role, ''),
                'google_maps_browser_api_key': getattr(settings, 'GOOGLE_MAPS_BROWSER_API_KEY', ''),
            },
        )
    )


def register_verify_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_for_user(request.user))

    pending_registration = request.session.get(PENDING_REGISTRATION_SESSION_KEY)
    if not pending_registration:
        messages.error(request, 'Your registration session expired. Please fill the form again.')
        return redirect('core:register')

    otp_form = LoginOtpVerifyForm()
    if request.method == 'POST':
        action = request.POST.get('action', 'verify_register_otp')
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
                return redirect('core:register_verify')
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

    return disable_html_cache(
        render(
            request,
            'core/register_verify.html',
            {
                'otp_form': otp_form,
                'pending_registration': pending_registration,
                'pending_registration_phone': pending_registration.get('phone', ''),
                'pending_registration_role_label': role_label(pending_registration.get('account_type', '')),
                'otp_expiry_minutes': getattr(settings, 'OTP_EXPIRY_MINUTES', 10),
            },
        )
    )


def email_otp_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_for_user(request.user))

    if request.GET.get('reset') == '1':
        request.session.pop(PENDING_EMAIL_OTP_SESSION_KEY, None)

    pending_email_otp = request.session.get(PENDING_EMAIL_OTP_SESSION_KEY)
    if pending_email_otp and request.method == 'GET':
        return redirect('core:email_otp_verify')

    request_form = EmailOtpRequestForm(initial={'email': (pending_email_otp or {}).get('email', request.GET.get('email', ''))})

    if request.method == 'POST':
        request_form = EmailOtpRequestForm(request.POST)
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
                    messages.success(request, 'We sent a 6 digit OTP to your email address.')
                    return redirect('core:email_otp_verify')
                token.delete()
                request_form.add_error('email', detail)

    return disable_html_cache(
        render(
            request,
            'core/email_otp.html',
            {
                'request_form': request_form,
            },
        )
    )


def email_otp_verify_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(get_dashboard_url_for_user(request.user))

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

    verify_form = EmailOtpVerifyForm(initial={'email': email})

    if request.method == 'POST':
        action = request.POST.get('action', 'verify')
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
                return redirect('core:email_otp_verify')
            token.delete()
            messages.error(request, detail)
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

    return disable_html_cache(
        render(
            request,
            'core/email_otp_verify.html',
            {
                'verify_form': verify_form,
                'pending_email_otp': pending_email_otp,
                'pending_email_otp_masked_email': mask_email(email),
                'pending_email_otp_role_label': role_label(pending_email_otp.get('role', '')),
                'otp_expiry_minutes': getattr(settings, 'OTP_EXPIRY_MINUTES', 10),
            },
        )
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
    active_role, active_profile = get_role_profile(request.user)
    order.bill_breakup = build_order_bill_breakup(order)
    order.subtotal_amount = order.bill_breakup['subtotal']
    order.shopkeeper_commission_fee = order.bill_breakup['shopkeeper_commission_fee']
    order.platform_fee = order.bill_breakup['platform_fee']
    if active_role == RoleType.RIDER:
        enrich_rider_order(order, active_profile)
    else:
        enrich_order_progress(order)
    related_notifications = order.notifications.order_by('-created_at')[:6]
    timeline = build_order_timeline(order)
    status_summary = build_order_status_summary(order)
    payment_summary = order.payment_summary
    shop_map_url = order.shop.google_maps_url
    customer_map_url = order.customer.google_maps_url
    return disable_html_cache(
        render(
            request,
            'core/order_detail.html',
            {
                'order': order,
                'timeline': timeline,
                'related_notifications': related_notifications,
                'active_role': active_role,
                'show_customer_actions': active_role == RoleType.CUSTOMER,
                'status_summary': status_summary,
                'payment_summary': payment_summary,
                'eta_label': build_order_eta_label(order),
                'shop_map_url': shop_map_url,
                'customer_map_url': customer_map_url,
            },
        )
    )


@login_required
def order_tracking_view(request: HttpRequest, order_id: int) -> HttpResponse:
    messages.info(request, 'Live tracking is unavailable in this version. Use order details and email updates instead.')
    return redirect('core:order_detail', order_id=order_id)


def customer_start(request: HttpRequest) -> HttpResponse:
    return redirect(f'{reverse("core:register_details")}?account_type={RoleType.CUSTOMER}')


def shop_start(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        active_role, profile = get_role_profile(request.user)
        if active_role != RoleType.SHOP:
            messages.error(request, 'This area is only for shop accounts.')
            return redirect(get_dashboard_url_for_user(request.user))
        if profile.shops.exists():
            return redirect('core:shop_dashboard')

        form = ShopUpdateForm(
            request.POST or None,
            request.FILES or None,
            initial={
                'is_open': False,
                'latitude': DEFAULT_LATITUDE,
                'longitude': DEFAULT_LONGITUDE,
            },
        )
        form.fields['is_open'].help_text = 'Your store stays offline until admin approval is complete.'

        if request.method == 'POST' and form.is_valid():
            shop = form.save(commit=False)
            shop.owner = profile
            shop.approval_status = ApprovalStatus.PENDING
            shop.is_open = False
            shop.save()
            create_notification(
                shop_owner=profile,
                title='Store sent for approval',
                body=f'{shop.name} is waiting for admin approval before it goes live.',
                notification_type=NotificationType.STORE,
            )
            messages.success(request, 'Store setup saved. Your workspace is ready for review.')
            return redirect('core:shop_dashboard')

        return disable_html_cache(
            render(
                request,
                'core/shop_start_setup.html',
                {
                    'form': form,
                    'shop_owner': profile,
                    'google_maps_browser_api_key': getattr(settings, 'GOOGLE_MAPS_BROWSER_API_KEY', ''),
                },
            )
        )
    return redirect(f'{reverse("core:register_details")}?account_type={RoleType.SHOP}')


def rider_start(request: HttpRequest) -> HttpResponse:
    return redirect(f'{reverse("core:register_details")}?account_type={RoleType.RIDER}')

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
    products = [annotate_catalog_product(product) for product in shop.products.filter(is_visible=True)]
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
    checkout_data = pending_checkout_data(request) or {
        'delivery_slot': DEFAULT_DELIVERY_SLOT,
        'payment_method': PaymentMethod.COD,
        'customer_notes': '',
    }
    context['cart'] = build_cart_context(request, delivery_slot=checkout_data.get('delivery_slot'))
    context['cart_fixed_total'] = sum(
        (
            group['subtotal'] + group['shopkeeper_commission_fee'] + group['platform_fee']
            for group in context['cart']['groups']
        ),
        Decimal('0.00'),
    )
    context['cart_estimated_total'] = context['cart_fixed_total'] + (
        context['cart']['delivery_slot_fee'] * len(context['cart']['groups'])
    )
    context['delivery_slot_options'] = delivery_slot_options(checkout_data.get('delivery_slot'))
    context['selected_delivery_slot'] = normalize_delivery_slot(checkout_data.get('delivery_slot', DEFAULT_DELIVERY_SLOT))
    context['selected_delivery_slot_config'] = delivery_slot_config(context['selected_delivery_slot'])
    context['order_form'] = CustomerOrderMetaForm(
        initial=checkout_data,
        enable_razorpay=context['razorpay_enabled'],
    )
    return render(request, 'core/customer_cart.html', context)


@role_required(RoleType.CUSTOMER)
def customer_khatabook_view(request: HttpRequest) -> HttpResponse:
    context = customer_workspace_context(request)
    customer = request.role_profile
    khata_cycle = customer.khatabook_cycles.order_by('-week_start').first()
    if khata_cycle:
        khata_cycle = refresh_khatabook_cycle(khata_cycle)
    collection_request = active_khatabook_collection_request(khata_cycle)

    khatabook_razorpay_checkout = None
    if khata_cycle and khata_cycle.outstanding_amount > Decimal('0.00') and context['razorpay_enabled']:
        try:
            if not khata_cycle.razorpay_order_id:
                create_razorpay_order_for_khatabook_cycle(khata_cycle)
            khatabook_razorpay_checkout = build_khatabook_razorpay_context(khata_cycle, customer)
        except CheckoutValidationError as error:
            messages.warning(request, str(error))

    context.update(
        {
            'khatabook_cycle': khata_cycle,
            'khatabook_summary': build_khatabook_cycle_summary(khata_cycle),
            'khatabook_orders': (
                customer.orders.filter(khata_cycle=khata_cycle)
                .select_related('shop')
                .order_by('-created_at')
                if khata_cycle
                else []
            ),
            'khatabook_collection_request': collection_request,
            'khatabook_razorpay_checkout': khatabook_razorpay_checkout,
        }
    )
    return disable_html_cache(render(request, 'core/customer_khatabook.html', context))


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
    return disable_html_cache(render(request, 'core/customer_orders.html', context))


@role_required(RoleType.CUSTOMER)
@require_POST
def customer_khatabook_request_collection(request: HttpRequest) -> HttpResponse:
    cycle = request.role_profile.khatabook_cycles.order_by('-week_start').first()
    if not cycle:
        messages.info(request, 'You do not have an active KhataBook due yet.')
        return redirect('core:customer_khatabook')
    cycle = refresh_khatabook_cycle(cycle)
    if cycle.outstanding_amount <= Decimal('0.00'):
        messages.success(request, 'This KhataBook cycle is already settled.')
        return redirect('core:customer_khatabook')

    active_request = active_khatabook_collection_request(cycle)
    if active_request:
        if active_request.rider_id:
            messages.info(request, 'A rider is already assigned to this KhataBook collection request.')
        else:
            messages.info(request, 'Your KhataBook collection request is already open for nearby riders.')
        return redirect('core:customer_khatabook')

    collection_request = KhataBookCollectionRequest.objects.create(
        customer=request.role_profile,
        khata_cycle=cycle,
        amount=cycle.outstanding_amount,
        collection_address=build_delivery_address(request.role_profile),
        collection_notes='Customer requested COD / UPI repayment for the weekly KhataBook due.',
        collection_otp='',
        latitude=request.role_profile.latitude,
        longitude=request.role_profile.longitude,
    )

    cycle.status = KhataBookCycleStatus.COLLECTION_REQUESTED
    cycle.settlement_method = KhataBookSettlementMethod.COD_UPI
    cycle.collection_requested_at = timezone.now()
    cycle.failure_reason = ''
    cycle.save(
        update_fields=[
            'status',
            'settlement_method',
            'collection_requested_at',
            'failure_reason',
            'updated_at',
        ]
    )
    create_notification(
        customer=request.role_profile,
        title='KhataBook collection requested',
        body='COD / UPI repayment was requested. A delivery agent might take time to arrive for the collection handoff.',
        notification_type=NotificationType.PAYMENT,
    )
    for nearby_rider in eligible_available_riders_for_collection_request(collection_request):
        create_notification(
            rider=nearby_rider,
            title='KhataBook collection request nearby',
            body=(
                f'{collection_request.display_id} is ready nearby for Rs. {collection_request.amount}. '
                'Open the rider dashboard to accept this credit collection.'
            ),
            notification_type=NotificationType.PAYMENT,
        )
    messages.success(request, 'COD / UPI collection was requested. A delivery agent might take time to arrive.')
    return redirect('core:customer_khatabook')


@role_required(RoleType.CUSTOMER)
@require_POST
def customer_khatabook_razorpay_complete(request: HttpRequest) -> HttpResponse:
    customer = request.role_profile
    cycle = get_object_or_404(
        KhataBookCycle.objects.select_related('customer'),
        pk=request.POST.get('khatabook_cycle_id'),
        customer=customer,
    )
    cycle = refresh_khatabook_cycle(cycle)
    if cycle.outstanding_amount <= Decimal('0.00'):
        messages.success(request, 'This KhataBook cycle is already paid.')
        return redirect('core:customer_khatabook')

    razorpay_payment_id = request.POST.get('razorpay_payment_id', '').strip()
    razorpay_order_id = request.POST.get('razorpay_order_id', '').strip()
    razorpay_signature = request.POST.get('razorpay_signature', '').strip()
    if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
        messages.error(request, 'Razorpay did not return the KhataBook payment confirmation details.')
        return redirect('core:customer_khatabook')
    if razorpay_order_id != cycle.razorpay_order_id:
        messages.error(request, 'The KhataBook payment order did not match this weekly due.')
        return redirect('core:customer_khatabook')
    if not verify_razorpay_payment_signature(
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        razorpay_signature=razorpay_signature,
    ):
        cycle.failure_reason = 'KhataBook payment signature verification failed.'
        cycle.save(update_fields=['failure_reason', 'updated_at'])
        messages.error(request, 'We could not verify the KhataBook payment signature. Please try again.')
        return redirect('core:customer_khatabook')

    try:
        razorpay_payment = fetch_razorpay_payment(razorpay_payment_id)
        razorpay_order = fetch_razorpay_order(razorpay_order_id)
    except CheckoutValidationError as error:
        messages.error(request, str(error))
        return redirect('core:customer_khatabook')

    expected_amount = int((cycle.outstanding_amount * 100).quantize(Decimal('1')))
    payment_status = razorpay_payment.get('status', '')
    if (
        razorpay_payment.get('order_id') != razorpay_order_id
        or razorpay_order.get('id') != razorpay_order_id
        or int(razorpay_order.get('amount', 0)) != expected_amount
        or int(razorpay_payment.get('amount', 0)) != expected_amount
        or payment_status not in ['authorized', 'captured']
    ):
        cycle.failure_reason = 'KhataBook payment verification did not pass all checks.'
        cycle.save(update_fields=['failure_reason', 'updated_at'])
        messages.error(request, 'KhataBook payment verification failed. Your due is still open.')
        return redirect('core:customer_khatabook')

    cycle.razorpay_payment_id = razorpay_payment_id
    cycle.razorpay_signature = razorpay_signature
    cycle.settlement_method = KhataBookSettlementMethod.RAZORPAY_UPI
    cycle.save(update_fields=['razorpay_payment_id', 'razorpay_signature', 'settlement_method', 'updated_at'])
    mark_khatabook_cycle_paid(
        cycle,
        settlement_method=KhataBookSettlementMethod.RAZORPAY_UPI,
        payment_reference=razorpay_payment_id,
    )
    create_notification(
        customer=customer,
        title='KhataBook payment received',
        body=f'Your KhataBook due for the week starting {cycle.week_start.strftime("%b %d")} was settled successfully.',
        notification_type=NotificationType.PAYMENT,
    )
    messages.success(request, 'KhataBook due paid successfully through Razorpay UPI.')
    return redirect('core:customer_khatabook')


@role_required(RoleType.CUSTOMER)
@require_POST
def customer_khatabook_razorpay_failed(request: HttpRequest) -> HttpResponse:
    cycle = get_object_or_404(
        KhataBookCycle,
        pk=request.POST.get('khatabook_cycle_id'),
        customer=request.role_profile,
    )
    error_message = (
        request.POST.get('error_description')
        or request.POST.get('error_reason')
        or 'The KhataBook UPI payment was not completed.'
    )
    cycle.failure_reason = error_message[:240]
    cycle.save(update_fields=['failure_reason', 'updated_at'])
    messages.error(request, cycle.failure_reason)
    return redirect('core:customer_khatabook')


@role_required(RoleType.CUSTOMER)
@require_POST
def customer_confirm_cod_cash(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(
        Order.objects.select_related('customer', 'rider', 'shop__owner', 'shop'),
        pk=order_id,
        customer=request.role_profile,
    )
    if order.payment_method != PaymentMethod.COD:
        messages.error(request, 'Cash confirmation is only available for COD orders.')
        return redirect('core:order_detail', order_id=order.id)
    if order.status not in [OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED]:
        messages.error(request, 'Cash confirmation is only available once delivery is in progress or completed.')
        return redirect('core:order_detail', order_id=order.id)
    if not order.rider_id:
        messages.error(request, 'A rider must be assigned before COD cash can be confirmed.')
        return redirect('core:order_detail', order_id=order.id)
    if order.cod_collection_mode == CodCollectionMode.ONLINE and order_customer_payment_complete(order):
        messages.error(request, 'This COD order was already paid online.')
        return redirect('core:order_detail', order_id=order.id)

    with transaction.atomic():
        locked_order = Order.objects.select_for_update().select_related('rider', 'shop__owner', 'customer').get(pk=order.pk)
        locked_order.cod_collection_mode = CodCollectionMode.CASH
        locked_order.payment_status = PaymentStatus.PAID
        locked_order.customer_paid_at = locked_order.customer_paid_at or timezone.now()
        locked_order.cash_confirmed_at = timezone.now()
        if locked_order.settlement_status != SettlementStatus.PAID and not can_create_settlement_qr():
            locked_order.settlement_status = SettlementStatus.FAILED
        locked_order.save(
            update_fields=[
                'cod_collection_mode',
                'payment_status',
                'customer_paid_at',
                'cash_confirmed_at',
                'settlement_status',
                'updated_at',
            ]
        )

    qr_ready = False
    qr_error = ''
    if locked_order.settlement_status == SettlementStatus.FAILED and not can_create_settlement_qr():
        qr_error = 'Configure Razorpay QR collection or a settlement QR fallback image to finish rider settlement.'
    elif locked_order.settlement_status != SettlementStatus.PAID:
        try:
            create_rider_settlement_qr(locked_order)
            qr_ready = True
        except CheckoutValidationError as error:
            locked_order.settlement_status = SettlementStatus.FAILED
            locked_order.save(update_fields=['settlement_status', 'updated_at'])
            qr_error = str(error)

    create_notification(
        customer=locked_order.customer,
        order=locked_order,
        title='Cash payment recorded',
        body=f'{locked_order.display_id} was marked as cash paid. Rider settlement is now being tracked.',
        notification_type=NotificationType.PAYMENT,
    )
    create_notification(
        rider=locked_order.rider,
        order=locked_order,
        title='Customer marked cash paid',
        body=(
            f'{locked_order.display_id} was confirmed as cash paid. '
            f'{"Open the settlement QR in your dashboard to pay GramExpress." if qr_ready else "Settlement QR generation needs attention."}'
        ),
        notification_type=NotificationType.PAYMENT,
    )
    create_notification(
        shop_owner=locked_order.shop.owner,
        order=locked_order,
        title='COD cash confirmed',
        body=f'{locked_order.display_id} was marked as cash paid by the customer.',
        notification_type=NotificationType.PAYMENT,
    )
    if qr_ready:
        messages.success(request, 'Cash payment recorded. The rider now has a settlement QR in the rider dashboard.')
    else:
        messages.warning(request, f'Cash payment recorded, but the rider settlement QR is not ready yet. {qr_error}'.strip())
    return redirect('core:order_detail', order_id=order.id)


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
    product = get_object_or_404(
        Product.objects.select_related('shop'),
        pk=product_id,
        is_visible=True,
        shop__approval_status=ApprovalStatus.APPROVED,
    )
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
            if not product.is_visible:
                cart.pop(key, None)
                messages.error(request, 'That product is no longer available in the storefront.')
                save_cart(request, cart)
                return redirect(request.POST.get('next') or reverse('core:customer_cart'))
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
    checkout_data = pending_checkout_data(request) or {
        'delivery_slot': DEFAULT_DELIVERY_SLOT,
        'payment_method': PaymentMethod.COD,
        'customer_notes': '',
    }
    cart = build_cart_context(request, delivery_slot=checkout_data.get('delivery_slot'))
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
                    'delivery_slot': form.cleaned_data['delivery_slot'],
                    'payment_method': form.cleaned_data['payment_method'],
                    'customer_notes': form.cleaned_data['customer_notes'],
                }
                cart = build_cart_context(request, delivery_slot=checkout_data['delivery_slot'])
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
            cart = build_cart_context(request, delivery_slot=checkout_data.get('delivery_slot'))
            if checkout_data['payment_method'] == PaymentMethod.RAZORPAY:
                messages.info(request, 'Use the Razorpay payment button to complete your online order.')
                return redirect('core:customer_checkout')

            if checkout_data['payment_method'] == PaymentMethod.KHATABOOK:
                checkout_session = create_khatabook_checkout_session(customer=customer, cart=cart, checkout_data=checkout_data)
            else:
                checkout_session = create_cod_checkout_session(customer=customer, cart=cart, checkout_data=checkout_data)
            try:
                created_orders = finalize_checkout_session(checkout_session)
            except CheckoutValidationError as error:
                checkout_session.failure_reason = str(error)
                checkout_session.save(update_fields=['failure_reason', 'updated_at'])
                messages.error(request, str(error))
                refreshed_cart = build_cart_context(request, delivery_slot=checkout_data.get('delivery_slot'))
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
            if checkout_data['payment_method'] == PaymentMethod.KHATABOOK:
                khata_due_date = next((order.credit_due_date for order in created_orders if order.credit_due_date), None)
                due_copy = f' Repayment is due by {khata_due_date.strftime("%b %d")}.' if khata_due_date else ''
                messages.success(request, f'{len(created_orders)} order(s) were added to KhataBook.{due_copy}')
            else:
                messages.success(request, f'{len(created_orders)} order(s) placed across your selected stores.')
            return redirect('core:customer_checkout_success')
    checkout_data = pending_checkout_data(request) or checkout_data
    cart = build_cart_context(request, delivery_slot=checkout_data.get('delivery_slot'))

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
    payment_link_entity = event_payload.get('payload', {}).get('payment_link', {}).get('entity', {})
    qr_code_entity = event_payload.get('payload', {}).get('qr_code', {}).get('entity', {})

    if payment_link_entity.get('id'):
        order = Order.objects.filter(cod_payment_link_id=payment_link_entity.get('id')).select_related('customer', 'rider', 'shop__owner').first()
        if not order:
            return JsonResponse({'status': 'ignored'})
        if event_name == 'payment_link.paid':
            order.cod_collection_mode = CodCollectionMode.ONLINE
            order.cod_payment_link_status = payment_link_entity.get('status', 'paid')
            order.payment_status = PaymentStatus.PAID
            order.customer_paid_at = order.customer_paid_at or timezone.now()
            order.payment_reference = payment_entity.get('id', order.payment_reference)
            order.save(
                update_fields=[
                    'cod_collection_mode',
                    'cod_payment_link_status',
                    'payment_status',
                    'customer_paid_at',
                    'payment_reference',
                    'updated_at',
                ]
            )
            create_notification(
                customer=order.customer,
                order=order,
                title='COD payment received',
                body=f'{order.display_id} COD online payment was captured successfully.',
                notification_type=NotificationType.PAYMENT,
            )
            if order.rider_id:
                create_notification(
                    rider=order.rider,
                    order=order,
                    title='Customer paid online',
                    body=f'{order.display_id} customer payment is complete. You can finish the handoff after OTP verification.',
                    notification_type=NotificationType.PAYMENT,
                )
            create_notification(
                shop_owner=order.shop.owner,
                order=order,
                title='COD online payment received',
                body=f'{order.display_id} customer payment was completed through Razorpay.',
                notification_type=NotificationType.PAYMENT,
            )
        elif event_name in ['payment_link.cancelled', 'payment_link.expired', 'payment_link.partially_paid']:
            order.cod_payment_link_status = payment_link_entity.get('status', order.cod_payment_link_status)
            order.save(update_fields=['cod_payment_link_status', 'updated_at'])
        return JsonResponse({'status': 'ok'})

    if qr_code_entity.get('id'):
        order = Order.objects.filter(settlement_qr_id=qr_code_entity.get('id')).select_related('customer', 'rider', 'shop__owner').first()
        if not order:
            return JsonResponse({'status': 'ignored'})
        if event_name == 'qr_code.credited':
            order.settlement_status = SettlementStatus.PAID
            order.settlement_paid_at = order.settlement_paid_at or timezone.now()
            order.settlement_payment_id = payment_entity.get('id', order.settlement_payment_id)
            order.save(update_fields=['settlement_status', 'settlement_paid_at', 'settlement_payment_id', 'updated_at'])
            create_notification(
                rider=order.rider,
                order=order,
                title='COD settlement received',
                body=f'{order.display_id} settlement to GramExpress was recorded successfully.',
                notification_type=NotificationType.PAYMENT,
            )
            create_notification(
                customer=order.customer,
                order=order,
                title='Cash payment closed',
                body=f'{order.display_id} cash payment and rider settlement are both complete.',
                notification_type=NotificationType.PAYMENT,
            )
            create_notification(
                shop_owner=order.shop.owner,
                order=order,
                title='COD settlement completed',
                body=f'{order.display_id} cash collection settlement was completed successfully.',
                notification_type=NotificationType.PAYMENT,
            )
        return JsonResponse({'status': 'ok'})

    razorpay_order_id = payment_entity.get('order_id') or order_entity.get('id')
    if not razorpay_order_id:
        return JsonResponse({'status': 'ignored'})

    checkout_session = CheckoutSession.objects.filter(razorpay_order_id=razorpay_order_id).first()
    if not checkout_session:
        cycle = KhataBookCycle.objects.filter(razorpay_order_id=razorpay_order_id).select_related('customer').first()
        if not cycle:
            return JsonResponse({'status': 'ignored'})
        if event_name in ['payment.captured', 'order.paid']:
            cycle.razorpay_payment_id = payment_entity.get('id', cycle.razorpay_payment_id)
            cycle.settlement_method = KhataBookSettlementMethod.RAZORPAY_UPI
            cycle.save(update_fields=['razorpay_payment_id', 'settlement_method', 'updated_at'])
            mark_khatabook_cycle_paid(
                cycle,
                settlement_method=KhataBookSettlementMethod.RAZORPAY_UPI,
                payment_reference=cycle.razorpay_payment_id,
                paid_at=timezone.now(),
            )
            create_notification(
                customer=cycle.customer,
                title='KhataBook payment received',
                body=f'Your KhataBook due for the week starting {cycle.week_start.strftime("%b %d")} was settled successfully.',
                notification_type=NotificationType.PAYMENT,
            )
        elif event_name == 'payment.failed':
            error_message = (
                payment_entity.get('error_description')
                or payment_entity.get('error_reason')
                or 'The KhataBook UPI payment failed.'
            )
            cycle.failure_reason = error_message[:240]
            cycle.save(update_fields=['failure_reason', 'updated_at'])
        return JsonResponse({'status': 'ok'})

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
        .select_related('shop', 'rider', 'checkout_session', 'khata_cycle')
        .order_by('-created_at')
    )
    khata_cycle = (
        KhataBookCycle.objects.filter(pk=payload.get('khata_cycle_id')).first()
        if payload.get('khata_cycle_id')
        else None
    )
    delivery_slot = normalize_delivery_slot(payload.get('delivery_slot', DEFAULT_DELIVERY_SLOT))
    return render(
        request,
        'core/checkout_success.html',
        {
            'orders': orders,
            'delivery_slot': delivery_slot,
            'delivery_slot_config': delivery_slot_config(delivery_slot),
            'payment_method': payload.get('payment_method', PaymentMethod.COD),
            'payment_method_label': dict(PaymentMethod.choices).get(
                payload.get('payment_method', PaymentMethod.COD),
                payload.get('payment_method', PaymentMethod.COD),
            ),
            'estimated_total': Decimal(payload.get('estimated_total', '0.00')),
            'primary_order': orders[0] if orders else None,
            'estimated_eta': delivery_slot_config(delivery_slot)['time_label'],
            'khatabook_summary': build_khatabook_cycle_summary(khata_cycle),
            'checkout_session': (
                CheckoutSession.objects.filter(pk=payload.get('checkout_session_id')).first()
                if payload.get('checkout_session_id')
                else None
            ),
        },
    )


def order_slot_api_payload(order: Order) -> dict[str, Any]:
    slot_meta = delivery_slot_config(order.delivery_slot)
    deadline_state = delivery_deadline_state(
        order.delivery_deadline,
        reference_time=timezone.now(),
        window_start=order.created_at,
    )
    return {
        'id': order.id,
        'display_id': order.display_id,
        'status': order.status,
        'status_label': order.get_status_display(),
        'delivery_slot': order.delivery_slot,
        'delivery_slot_label': getattr(order, 'delivery_slot_name', slot_meta['name']),
        'delivery_slot_time_label': getattr(order, 'delivery_slot_time_label', slot_meta['time_label']),
        'deadline': order.delivery_deadline.isoformat() if order.delivery_deadline else '',
        'deadline_label': getattr(
            order,
            'deadline_label',
            timezone.localtime(order.delivery_deadline).strftime('%b %d, %H:%M') if order.delivery_deadline else 'Pending',
        ),
        'time_remaining': getattr(order, 'time_remaining_label', deadline_state['time_remaining_label']),
        'is_overdue': getattr(order, 'is_deadline_overdue', deadline_state['is_overdue']),
        'total_amount': decimal_to_str(order.total_amount),
        'delivery_fee': decimal_to_str(order.delivery_fee),
        'distance_km': decimal_to_str(order.distance_km),
        'shop': order.shop.name,
        'customer': order.customer.full_name,
        'item_count': sum(item.quantity for item in order.items.all()),
    }


@role_required(RoleType.SHOP)
@require_GET
def shop_orders_by_slot_api(request: HttpRequest) -> JsonResponse:
    context = shop_workspace_context(request)
    return JsonResponse(
        {
            'slots': [
                {
                    'code': section['code'],
                    'label': section['label'],
                    'time_label': section['time_label'],
                    'tag': section['tag'],
                    'order_count': len(section['orders']),
                    'orders': [order_slot_api_payload(order) for order in section['orders']],
                }
                for section in context['slot_order_sections']
            ]
        }
    )


@role_required(RoleType.RIDER)
@require_GET
def rider_orders_by_slot_api(request: HttpRequest) -> JsonResponse:
    context = rider_workspace_context(request)
    return JsonResponse(
        {
            'slot_filter': context['slot_filter'],
            'slots': [
                {
                    'code': section['code'],
                    'label': section['label'],
                    'time_label': section['time_label'],
                    'tag': section['tag'],
                    'order_count': len(section['orders']),
                    'orders': [order_slot_api_payload(order) for order in section['orders']],
                }
                for section in context['active_orders_by_slot']
            ]
        }
    )


@role_required(RoleType.CUSTOMER)
@require_POST
def customer_order_create_api(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body.decode('utf-8')) if request.body else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({'error': 'Could not read the order payload.'}, status=400)

    delivery_slot = normalize_delivery_slot(str(payload.get('delivery_slot', DEFAULT_DELIVERY_SLOT)).strip())
    payment_method = str(payload.get('payment_method', PaymentMethod.COD)).strip() or PaymentMethod.COD
    customer_notes = str(payload.get('customer_notes', '')).strip()
    if payment_method == PaymentMethod.RAZORPAY:
        return JsonResponse({'error': 'Use the web checkout review flow for Razorpay orders.'}, status=400)

    cart = build_cart_context(request, delivery_slot=delivery_slot)
    try:
        validate_checkout_cart(cart)
    except CheckoutValidationError as error:
        return JsonResponse({'error': str(error)}, status=400)

    checkout_data = {
        'delivery_slot': delivery_slot,
        'payment_method': payment_method,
        'customer_notes': customer_notes,
    }
    checkout_session = (
        create_khatabook_checkout_session(customer=request.role_profile, cart=cart, checkout_data=checkout_data)
        if payment_method == PaymentMethod.KHATABOOK
        else create_cod_checkout_session(customer=request.role_profile, cart=cart, checkout_data=checkout_data)
    )
    try:
        created_orders = finalize_checkout_session(checkout_session)
    except CheckoutValidationError as error:
        checkout_session.failure_reason = str(error)
        checkout_session.save(update_fields=['failure_reason', 'updated_at'])
        return JsonResponse({'error': str(error)}, status=400)

    save_cart(request, {})
    set_last_checkout_payload(
        request,
        orders=created_orders,
        payment_method=checkout_data['payment_method'],
        checkout_session=checkout_session,
    )
    clear_pending_checkout(request)
    return JsonResponse(
        {
            'ok': True,
            'delivery_slot': delivery_slot,
            'orders': [order_slot_api_payload(order) for order in created_orders],
        }
    )


@role_required(RoleType.CUSTOMER)
@require_POST
def customer_rate_order(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(Order, pk=order_id, customer=request.role_profile)
    can_rate_order = order.can_be_rated_by_customer
    form = RatingForm(request.POST, instance=order)
    next_url = request.POST.get('next') or reverse('core:order_detail', args=[order.id])
    if can_rate_order and form.is_valid():
        rated_order = form.save()
        refresh_ratings()
        create_notification(
            shop_owner=rated_order.shop.owner,
            order=rated_order,
            title='New delivery feedback',
            body=f'Order #{rated_order.id} received delivery feedback with a {rated_order.customer_rating}/5 driver rating.',
            notification_type=NotificationType.ORDER,
        )
        if rated_order.rider:
            create_notification(
                rider=rated_order.rider,
                order=rated_order,
                title='Customer rated your delivery',
                body=f'Customer rated your delivery on order #{rated_order.id} with {rated_order.customer_rating}/5.',
                notification_type=NotificationType.RIDER,
            )
        messages.success(request, 'Thanks for rating the driver and sharing your delivery feedback.')
    else:
        messages.error(request, 'This delivery cannot be rated right now.')
    return redirect(next_url)


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
    try:
        context = shop_workspace_context(request)
    except Shop.DoesNotExist:
        return redirect_missing_shop_setup(request)
    return render(request, 'core/shop_dashboard.html', context)


@role_required(RoleType.SHOP)
@require_POST
def shop_toggle_store_state(request: HttpRequest) -> HttpResponse:
    try:
        context = shop_workspace_context(request)
    except Shop.DoesNotExist:
        return redirect_missing_shop_setup(request)

    shop = context['shop']
    redirect_to = request.POST.get('next') or reverse('core:shop_dashboard')

    if shop.approval_status != ApprovalStatus.APPROVED:
        messages.error(request, 'Your store can go live only after admin approval.')
        return redirect(redirect_to)

    if not shop.is_open and not shop_location_is_configured(shop):
        messages.error(request, 'Set your exact store location in Storefront Settings before going live.')
        return redirect('core:shop_settings')

    shop.is_open = not shop.is_open
    shop.save(update_fields=['is_open', 'updated_at'])

    if shop.is_open:
        create_notification(
            shop_owner=request.role_profile,
            title='Store opened',
            body='Your store is now visible for customers and ready to accept orders.',
            notification_type=NotificationType.STORE,
        )
        messages.success(request, 'Your store is now open.')
    else:
        create_notification(
            shop_owner=request.role_profile,
            title='Store closed',
            body='Your store is now offline for customers until you open it again.',
            notification_type=NotificationType.STORE,
        )
        messages.success(request, 'Your store is now closed.')

    return redirect(redirect_to)


@role_required(RoleType.SHOP)
def shop_orders_view(request: HttpRequest) -> HttpResponse:
    try:
        context = shop_workspace_context(request)
    except Shop.DoesNotExist:
        return redirect_missing_shop_setup(request)
    context['store_rating_form'] = StoreRatingForm()
    return disable_html_cache(render(request, 'core/shop_orders.html', context))


@role_required(RoleType.SHOP)
def shop_khatabook_view(request: HttpRequest) -> HttpResponse:
    try:
        context = shop_workspace_context(request)
    except Shop.DoesNotExist:
        return redirect_missing_shop_setup(request)
    return disable_html_cache(render(request, 'core/shop_khatabook.html', context))


@role_required(RoleType.SHOP)
@require_POST
def shop_send_khatabook_reminder(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(
        Order.objects.select_related('shop', 'customer', 'khata_cycle'),
        pk=order_id,
        shop__owner=request.role_profile,
        payment_method=PaymentMethod.KHATABOOK,
    )
    if order.payment_status == PaymentStatus.PAID or order.credit_paid_at:
        messages.info(request, 'This KhataBook order is already paid.')
        return redirect('core:shop_khatabook')
    due_date = order.credit_due_date or (order.khata_cycle.due_date if order.khata_cycle_id else None)
    due_copy = f' It is due by {due_date.strftime("%b %d, %Y")}.' if due_date else ''
    reminder_body = (
        f'{order.shop.name} sent a KhataBook payment reminder for {order.display_id}. '
        f'Rs. {order.total_amount} is still pending on your credit cycle.{due_copy}'
    )
    create_notification(
        customer=order.customer,
        order=order,
        title='KhataBook payment reminder',
        body=reminder_body,
        notification_type=NotificationType.PAYMENT,
    )
    if order.customer.email:
        try:
            send_mail(
                subject=f'KhataBook reminder for {order.display_id}',
                message=reminder_body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@gramexpress.local'),
                recipient_list=[order.customer.email],
                fail_silently=False,
            )
        except Exception:
            pass
    messages.success(request, f'Reminder sent to {order.customer.full_name}.')
    return redirect('core:shop_khatabook')


@role_required(RoleType.SHOP)
@require_POST
def shop_mark_khatabook_order_paid(request: HttpRequest, order_id: int) -> HttpResponse:
    order = get_object_or_404(
        Order.objects.select_related('shop', 'customer', 'khata_cycle'),
        pk=order_id,
        shop__owner=request.role_profile,
        payment_method=PaymentMethod.KHATABOOK,
    )
    if order.payment_status == PaymentStatus.PAID or order.credit_paid_at:
        messages.info(request, 'This KhataBook order is already marked as paid.')
        return redirect('core:shop_khatabook')
    if order.khata_cycle_id:
        mark_khatabook_cycle_paid(
            order.khata_cycle,
            settlement_method=KhataBookSettlementMethod.COD_UPI,
            payment_reference=f'shop-manual-{order.khata_cycle_id}',
        )
        create_notification(
            customer=order.customer,
            order=order,
            title='KhataBook payment recorded',
            body=(
                f'{order.shop.name} marked the KhataBook cycle containing {order.display_id} as recovered. '
                'Your credit due now shows as paid.'
            ),
            notification_type=NotificationType.PAYMENT,
        )
        messages.success(request, f'The KhataBook cycle for {order.display_id} was marked as paid.')
        return redirect('core:shop_khatabook')
    order.payment_status = PaymentStatus.PAID
    order.credit_paid_at = timezone.now()
    order.payment_reference = f'shop-manual-{order.id}'
    order.save(update_fields=['payment_status', 'credit_paid_at', 'payment_reference', 'updated_at'])
    messages.success(request, f'{order.display_id} was marked as paid.')
    return redirect('core:shop_khatabook')


@role_required(RoleType.SHOP)
def shop_products_view(request: HttpRequest) -> HttpResponse:
    try:
        context = shop_workspace_context(request, editing_product_id=request.GET.get('edit_product'))
    except Shop.DoesNotExist:
        return redirect_missing_shop_setup(request)
    shop = context['shop']
    editing_product = context['editing_product']
    product_query = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()
    if request.method == 'POST':
        target_product = editing_product if request.POST.get('product_id') else None
        product_form = ProductForm(request.POST, request.FILES, instance=target_product)
        if product_form.is_valid():
            product = product_form.save(commit=False)
            product.shop = shop
            product.save()
            messages.success(request, 'Product saved successfully.')
            return redirect('core:shop_products')
    else:
        product_form = ProductForm(instance=editing_product)
    context['product_form'] = product_form
    all_catalog_products = list(context['catalog_products'])
    catalog_products = list(all_catalog_products)
    if product_query:
        query = product_query.lower()
        catalog_products = [
            product for product in catalog_products
            if query in f'{product.name} {product.category} {product.unit} {product.preview_description}'.lower()
        ]
    if category_filter:
        catalog_products = [product for product in catalog_products if product.category == category_filter]
    context['catalog_products'] = catalog_products
    context['catalog_category_options'] = sorted(
        {product.category for product in all_catalog_products},
    )
    context['catalog_query'] = product_query
    context['catalog_category'] = category_filter
    return render(request, 'core/shop_products.html', context)


@role_required(RoleType.SHOP)
def shop_settings_view(request: HttpRequest) -> HttpResponse:
    try:
        context = shop_workspace_context(request)
    except Shop.DoesNotExist:
        return redirect_missing_shop_setup(request)
    shop = context['shop']
    if request.method == 'POST' and request.POST.get('action') == 'update_shop':
        was_approved = shop.approval_status == ApprovalStatus.APPROVED
        shop_form = ShopUpdateForm(request.POST, request.FILES, instance=shop)
        if shop_form.is_valid():
            updated_shop = shop_form.save(commit=False)
            if updated_shop.approval_status != ApprovalStatus.APPROVED:
                updated_shop.approval_status = ApprovalStatus.PENDING
                updated_shop.is_open = False
            elif not shop_location_is_configured(updated_shop):
                updated_shop.is_open = False
            updated_shop.save()
            create_notification(
                shop_owner=request.role_profile,
                title='Store profile updated',
                body='Your store details changed and may need a fresh approval review.',
                notification_type=NotificationType.STORE,
            )
            if was_approved and not shop_location_is_configured(updated_shop):
                messages.error(request, 'Store details were saved, but the store stayed closed until location is fully set.')
            messages.success(request, 'Shop details updated.')
            return redirect('core:shop_settings')
    else:
        shop_form = ShopUpdateForm(instance=shop)
    context['shop_form'] = shop_form
    context['google_maps_browser_api_key'] = getattr(settings, 'GOOGLE_MAPS_BROWSER_API_KEY', '')
    context['shop_location_preview_url'] = build_google_embed_place_url(shop.latitude, shop.longitude)
    context['location_ready_for_go_live'] = shop_location_is_configured(shop)
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
def shop_update_product_stock(request: HttpRequest, product_id: int) -> HttpResponse:
    product = get_object_or_404(Product, pk=product_id, shop__owner=request.role_profile)
    try:
        stock_quantity = max(0, int(request.POST.get('stock', product.stock)))
    except (TypeError, ValueError):
        messages.error(request, 'Enter a valid stock quantity.')
        return redirect('core:shop_products')
    product.stock = stock_quantity
    product.save(update_fields=['stock', 'updated_at'])
    messages.success(request, f'Stock updated for {product.name}.')
    return redirect('core:shop_products')


@role_required(RoleType.SHOP)
@require_POST
def shop_toggle_product_visibility(request: HttpRequest, product_id: int) -> HttpResponse:
    product = get_object_or_404(Product, pk=product_id, shop__owner=request.role_profile)
    product.is_visible = not product.is_visible
    product.save(update_fields=['is_visible', 'updated_at'])
    messages.success(
        request,
        f'{product.name} is now {"visible to customers" if product.is_visible else "hidden from customers"}.',
    )
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
    can_rate_order = order.can_be_rated_by_store
    form = StoreRatingForm(request.POST, instance=order)
    if can_rate_order and form.is_valid():
        rated_order = form.save()
        refresh_ratings()
        create_notification(
            rider=rated_order.rider,
            order=rated_order,
            title='Store rated your delivery',
            body=f'The store rated order #{rated_order.id} with {rated_order.store_rating}/5.',
            notification_type=NotificationType.RIDER,
        )
        messages.success(request, 'Rider rating saved.')
    else:
        messages.error(request, 'This delivery cannot be rated right now.')
    return redirect('core:shop_orders')

@role_required(RoleType.RIDER)
def rider_dashboard(request: HttpRequest) -> HttpResponse:
    redirect_response = handle_rider_availability_toggle(request, request.role_profile)
    if redirect_response:
        return redirect_response
    context = rider_workspace_context(request)
    return disable_html_cache(render(request, 'core/rider_dashboard.html', context))


@role_required(RoleType.RIDER)
def rider_deliveries_view(request: HttpRequest) -> HttpResponse:
    context = rider_workspace_context(request)
    return disable_html_cache(render(request, 'core/rider_deliveries.html', context))


@role_required(RoleType.RIDER)
def rider_completed_orders_view(request: HttpRequest) -> HttpResponse:
    context = rider_workspace_context(request)
    return disable_html_cache(render(request, 'core/rider_completed_orders.html', context))


@role_required(RoleType.RIDER)
def rider_earnings_view(request: HttpRequest) -> HttpResponse:
    context = rider_workspace_context(request)
    return disable_html_cache(render(request, 'core/rider_earnings.html', context))


@role_required(RoleType.RIDER)
def rider_profile_view(request: HttpRequest) -> HttpResponse:
    rider = request.role_profile
    redirect_response = handle_rider_availability_toggle(request, rider)
    if redirect_response:
        return redirect_response

    context = rider_workspace_context(request)
    return render(request, 'core/rider_profile.html', context)


@require_GET
def rider_profile_api(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated or not hasattr(request.user, 'rider_profile'):
        return JsonResponse({'error': 'Only riders can access this profile endpoint.'}, status=403)
    return JsonResponse({'rider': rider_profile_payload(request.user.rider_profile)})


@require_POST
def rider_upload_photo_api(request: HttpRequest) -> JsonResponse:
    account_type = request.POST.get('account_type') or request.GET.get('account_type')
    if not request.user.is_authenticated and account_type != RoleType.RIDER:
        return JsonResponse({'error': 'Only riders can upload a profile photo.'}, status=403)
    if request.user.is_authenticated and not hasattr(request.user, 'rider_profile'):
        return JsonResponse({'error': 'Only riders can upload a profile photo.'}, status=403)
    capture_error = validate_live_rider_capture(request)
    if capture_error:
        return JsonResponse({'error': capture_error}, status=400)

    content, extension, error_message = extract_rider_photo_upload(request)
    if error_message:
        return JsonResponse({'error': error_message}, status=400)

    if request.user.is_authenticated and hasattr(request.user, 'rider_profile'):
        rider = request.user.rider_profile
        photo_url = save_rider_photo_to_profile(rider, content, extension)
        return JsonResponse(
            {
                'ok': True,
                'event': 'rider_photo_updated',
                'photo_url': photo_url,
                'rider': rider_profile_payload(rider),
            }
        )

    photo_url = save_temporary_rider_photo(content, extension)
    return JsonResponse(
        {
            'ok': True,
            'photo_url': photo_url,
        }
    )


@require_http_methods(['POST', 'PUT'])
def rider_update_photo_api(request: HttpRequest) -> JsonResponse:
    if not request.user.is_authenticated or not hasattr(request.user, 'rider_profile'):
        return JsonResponse({'error': 'Only riders can update a profile photo.'}, status=403)
    capture_error = validate_live_rider_capture(request)
    if capture_error:
        return JsonResponse({'error': capture_error}, status=400)

    content, extension, error_message = extract_rider_photo_upload(request)
    if error_message:
        return JsonResponse({'error': error_message}, status=400)

    rider = request.user.rider_profile
    photo_url = save_rider_photo_to_profile(rider, content, extension)
    return JsonResponse(
        {
            'ok': True,
            'event': 'rider_photo_updated',
            'photo_url': photo_url,
            'rider': rider_profile_payload(rider),
        }
    )


@role_required(RoleType.RIDER)
@require_POST
def rider_toggle_availability(request: HttpRequest) -> HttpResponse:
    rider = request.role_profile
    go_online = request.POST.get('is_available') == 'on'

    if rider.approval_status != ApprovalStatus.APPROVED and go_online:
        messages.error(request, 'Admin approval is required before you can go live for dispatch.')
        return redirect(rider_availability_redirect_target(request))

    rider.is_available = go_online
    rider.save(update_fields=['is_available', 'updated_at'])
    messages.success(request, 'Rider availability updated.')
    return redirect(rider_availability_redirect_target(request))


@role_required(RoleType.RIDER)
@require_POST
def rider_resend_customer_otp(request: HttpRequest, order_id: int) -> HttpResponse:
    rider = request.role_profile
    locked_order = get_object_or_404(
        Order.objects.select_related('customer', 'shop__owner', 'shop', 'rider'),
        pk=order_id,
        rider=rider,
    )

    if locked_order.status != OrderStatus.OUT_FOR_DELIVERY:
        messages.error(request, 'OTP reminders are only available for active drop-off orders.')
        return redirect(rider_order_redirect_target(request, order_id))

    latest_resend = (
        locked_order.notifications.filter(
            notification_type=NotificationType.RIDER,
            title='Delivery OTP resent',
        )
        .order_by('-created_at')
        .first()
    )
    if latest_resend and timezone.now() < latest_resend.created_at + timezone.timedelta(seconds=delivery_otp_resend_cooldown_seconds()):
        messages.error(
            request,
            f'Wait {delivery_otp_resend_cooldown_seconds()} seconds before resending the OTP again.',
        )
        return redirect(rider_order_redirect_target(request, order_id))

    locked_order.customer_otp = generate_delivery_otp()
    locked_order.save(update_fields=['customer_otp', 'updated_at'])

    email_delivered, email_detail = send_order_status_email(
        order=locked_order,
        subject=f'Delivery OTP reminder for {locked_order.display_id}',
        headline='Your delivery OTP has been resent.',
        detail=(
            f'{rider.full_name} requested a fresh handoff reminder while completing your delivery. '
            f'Use OTP {locked_order.customer_otp} only when the order is handed to you.'
        ),
    )
    sms_delivered, sms_detail = send_customer_delivery_otp_sms(
        order=locked_order,
        intro='Your GramExpress rider resent the delivery handoff code.',
    )
    create_notification(
        customer=locked_order.customer,
        order=locked_order,
        title='Delivery OTP resent',
        body=f'Order #{locked_order.id} delivery OTP reminder sent again: {locked_order.customer_otp}.',
        notification_type=NotificationType.RIDER,
    )
    if email_delivered or sms_delivered:
        message_bits = []
        if email_delivered:
            message_bits.append('email')
        if sms_delivered:
            message_bits.append('SMS')
        messages.success(request, f'Customer OTP reminder sent again by {" and ".join(message_bits)}.')
    else:
        messages.error(request, email_detail if email_detail != 'No customer email is available for this order.' else sms_detail)
    return redirect(rider_order_redirect_target(request, order_id))


@role_required(RoleType.RIDER)
@require_POST
def rider_update_location(request: HttpRequest) -> HttpResponse:
    rider = request.role_profile
    form = RiderLocationForm(request.POST)
    next_url = request.POST.get('next') or ''
    redirect_target = (
        next_url
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()})
        else reverse('core:rider_profile')
    )
    if form.is_valid():
        rider.latitude = form.cleaned_data['latitude']
        rider.longitude = form.cleaned_data['longitude']
        rider.save(update_fields=['latitude', 'longitude', 'updated_at'])
        messages.success(request, 'Dispatch location updated for your rider workspace.')
    else:
        messages.error(request, 'Could not update location.')
    return redirect(redirect_target)


@role_required(RoleType.RIDER)
@require_POST
def rider_request_cod_online_payment(request: HttpRequest, order_id: int) -> HttpResponse:
    rider = request.role_profile
    locked_order = get_object_or_404(
        Order.objects.select_related('customer', 'shop__owner', 'shop', 'rider'),
        pk=order_id,
        rider=rider,
    )
    if locked_order.payment_method != PaymentMethod.COD:
        messages.error(request, 'This action is only available for COD orders.')
        return redirect(rider_order_redirect_target(request, order_id))
    if locked_order.status != OrderStatus.OUT_FOR_DELIVERY:
        messages.error(request, 'Request the COD payment link only after pickup starts delivery.')
        return redirect(rider_order_redirect_target(request, order_id))
    if not (locked_order.customer.email or '').strip():
        messages.error(request, 'Customer email is required before sending the COD payment link.')
        return redirect(rider_order_redirect_target(request, order_id))
    if not is_razorpay_ready():
        messages.error(request, 'Razorpay is not configured yet for COD online payment links.')
        return redirect(rider_order_redirect_target(request, order_id))
    if locked_order.cod_collection_mode == CodCollectionMode.CASH and locked_order.cash_confirmed_at:
        messages.error(request, 'This COD order is already marked as cash paid.')
        return redirect(rider_order_redirect_target(request, order_id))
    if order_customer_payment_complete(locked_order):
        messages.info(request, 'Customer payment is already recorded for this order.')
        return redirect(rider_order_redirect_target(request, order_id))

    try:
        create_cod_payment_link(request=request, order=locked_order)
    except CheckoutValidationError as error:
        messages.error(request, str(error))
        return redirect(rider_order_redirect_target(request, order_id))

    email_sent, email_detail = send_cod_payment_link_email(order=locked_order)
    create_notification(
        customer=locked_order.customer,
        order=locked_order,
        title='COD payment link ready',
        body=f'{locked_order.display_id} now has an online payment link: {locked_order.cod_payment_link_url}',
        notification_type=NotificationType.PAYMENT,
    )
    create_notification(
        rider=locked_order.rider,
        order=locked_order,
        title='COD payment link sent',
        body=f'{locked_order.display_id} payment link was prepared for the customer.',
        notification_type=NotificationType.PAYMENT,
    )
    create_notification(
        shop_owner=locked_order.shop.owner,
        order=locked_order,
        title='COD payment link sent',
        body=f'{locked_order.display_id} customer can now pay online through Razorpay before final handoff.',
        notification_type=NotificationType.PAYMENT,
    )
    if email_sent:
        messages.success(request, 'Recieve Money Online link sent to the customer email and reflected in both dashboards.')
    else:
        messages.warning(
            request,
            f'Payment link is ready in the app, but the email could not be sent automatically. {email_detail}',
        )
    return redirect(rider_order_redirect_target(request, order_id))


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
        body=f'{locked_rider.full_name} accepted order #{locked_order.id} and is heading to the store.',
        notification_type=NotificationType.RIDER,
    )
    create_notification(
        shop_owner=locked_order.shop.owner,
        order=locked_order,
        title='Rider assigned',
        body=f'{locked_rider.full_name} accepted order #{locked_order.id} and is on the way to pickup.',
        notification_type=NotificationType.RIDER,
    )
    customer_emailed, _ = send_order_status_email(
        order=locked_order,
        subject=f'Your order {locked_order.display_id} now has a rider',
        headline='A rider has accepted your order.',
        detail=(
            f'{locked_rider.full_name} is now handling your delivery. '
            'The next app update will happen when pickup is confirmed at the store.'
        ),
    )
    store_emailed, _ = send_store_order_status_email(
        order=locked_order,
        subject=f'Rider assigned for {locked_order.display_id}',
        headline='A rider has accepted this order.',
        detail=f'{locked_rider.full_name} is heading to the store for pickup.',
    )
    messages.success(
        request,
        f'Order #{locked_order.id} assigned to {locked_rider.full_name}.'
        f'{" Customer updated." if customer_emailed else ""}'
        f'{" Store updated." if store_emailed else ""}',
    )
    return redirect('core:rider_deliveries')


@role_required(RoleType.RIDER)
@require_POST
def rider_accept_khatabook_collection(request: HttpRequest, request_id: int) -> HttpResponse:
    rider = request.role_profile
    if rider.approval_status != ApprovalStatus.APPROVED or not rider.is_available:
        messages.error(request, 'Only approved and available riders can accept KhataBook collection requests.')
        return redirect('core:rider_deliveries')

    with transaction.atomic():
        locked_rider = RiderProfile.objects.select_for_update().get(pk=rider.pk)
        if locked_rider.approval_status != ApprovalStatus.APPROVED or not locked_rider.is_available:
            messages.error(request, 'This rider account is no longer available for KhataBook collections.')
            return redirect('core:rider_deliveries')

        collection_request = (
            KhataBookCollectionRequest.objects.select_for_update()
            .select_related('customer', 'khata_cycle', 'rider')
            .filter(pk=request_id)
            .first()
        )
        if not collection_request or collection_request.rider_id is not None:
            messages.error(request, 'That KhataBook collection was already claimed by another rider.')
            return redirect('core:rider_deliveries')
        if collection_request.status != KhataBookCollectionStatus.REQUESTED:
            messages.error(request, 'This KhataBook collection request is no longer open.')
            return redirect('core:rider_deliveries')

        dispatch_radius = locked_rider.max_service_radius_km if RiderProfile.objects.filter(approval_status=ApprovalStatus.APPROVED, is_available=True).count() < 3 else locked_rider.service_radius_km
        distance_km = kilometers_between(
            locked_rider.latitude,
            locked_rider.longitude,
            collection_request.latitude,
            collection_request.longitude,
        )
        if distance_km > dispatch_radius:
            messages.error(request, 'This KhataBook collection request is outside your current dispatch radius.')
            return redirect('core:rider_deliveries')

        collection_request.rider = locked_rider
        collection_request.status = KhataBookCollectionStatus.ACCEPTED
        collection_request.accepted_at = timezone.now()
        collection_request.collection_otp = generate_delivery_otp()
        collection_request.save(update_fields=['rider', 'status', 'accepted_at', 'collection_otp', 'updated_at'])
        locked_rider.is_available = False
        locked_rider.save(update_fields=['is_available', 'updated_at'])

    otp_email_sent, otp_sms_sent = ensure_khatabook_collection_otp_ready(
        collection_request=collection_request,
        rider=locked_rider,
    )
    create_notification(
        customer=collection_request.customer,
        title='Rider assigned for KhataBook collection',
        body=(
            f'{locked_rider.full_name} accepted {collection_request.display_id}. '
            'A fresh 6-digit KhataBook repayment OTP was sent to your registered contact for the handoff.'
        ),
        notification_type=NotificationType.PAYMENT,
    )
    create_notification(
        rider=locked_rider,
        title='KhataBook collection accepted',
        body=f'{collection_request.display_id} is now in your active queue for Rs. {collection_request.amount}.',
        notification_type=NotificationType.PAYMENT,
    )
    if otp_email_sent or otp_sms_sent:
        messages.success(request, f'{collection_request.display_id} assigned to {locked_rider.full_name}. Customer OTP sent for repayment authentication.')
    else:
        messages.success(request, f'{collection_request.display_id} assigned to {locked_rider.full_name}.')
    return redirect('core:rider_deliveries')


@role_required(RoleType.RIDER)
@require_POST
def rider_complete_khatabook_collection(request: HttpRequest, request_id: int) -> HttpResponse:
    rider = request.role_profile
    otp = request.POST.get('collection_otp', '').strip()

    with transaction.atomic():
        locked_rider = RiderProfile.objects.select_for_update().get(pk=rider.pk)
        collection_request = get_object_or_404(
            KhataBookCollectionRequest.objects.select_for_update().select_related('customer', 'khata_cycle'),
            pk=request_id,
            rider=locked_rider,
        )
        if collection_request.status != KhataBookCollectionStatus.ACCEPTED:
            messages.error(request, 'This KhataBook collection is not ready to complete.')
            return redirect('core:rider_deliveries')

        distance_km = kilometers_between(
            locked_rider.latitude,
            locked_rider.longitude,
            collection_request.latitude,
            collection_request.longitude,
        )
        if distance_km > KHATABOOK_COLLECTION_GEOFENCE_KM:
            messages.error(request, f'Get closer to the customer to complete collection. You are {distance_km} km away.')
            return redirect('core:rider_deliveries')
        if otp != collection_request.collection_otp:
            messages.error(request, 'KhataBook collection OTP did not match.')
            return redirect('core:rider_deliveries')

        paid_at = timezone.now()
        collection_request.status = KhataBookCollectionStatus.COMPLETED
        collection_request.payment_reference = f'khata-cod-{collection_request.id}'
        collection_request.completed_at = paid_at
        collection_request.save(update_fields=['status', 'payment_reference', 'completed_at', 'updated_at'])
        mark_khatabook_cycle_paid(
            collection_request.khata_cycle,
            settlement_method=KhataBookSettlementMethod.COD_UPI,
            payment_reference=collection_request.payment_reference,
            paid_at=paid_at,
        )
        locked_rider.is_available = True
        locked_rider.save(update_fields=['is_available', 'updated_at'])

    create_notification(
        customer=collection_request.customer,
        title='KhataBook collection completed',
        body=f'{collection_request.display_id} was collected successfully and your weekly KhataBook due is now closed.',
        notification_type=NotificationType.PAYMENT,
    )
    create_notification(
        rider=locked_rider,
        title='KhataBook collection completed',
        body=f'{collection_request.display_id} was marked complete for Rs. {collection_request.amount}.',
        notification_type=NotificationType.PAYMENT,
    )
    messages.success(request, f'{collection_request.display_id} marked as collected.')
    return redirect('core:rider_completed_orders')


@role_required(RoleType.RIDER)
@require_POST
def rider_resend_khatabook_collection_otp(request: HttpRequest, request_id: int) -> HttpResponse:
    rider = request.role_profile
    collection_request = get_object_or_404(
        KhataBookCollectionRequest.objects.select_related('customer', 'rider', 'khata_cycle'),
        pk=request_id,
        rider=rider,
    )
    if collection_request.status != KhataBookCollectionStatus.ACCEPTED:
        messages.error(request, 'Repayment OTPs can only be resent for active accepted KhataBook collections.')
        return redirect('core:rider_deliveries')

    otp_email_sent, otp_sms_sent = ensure_khatabook_collection_otp_ready(
        collection_request=collection_request,
        rider=rider,
        force_new=True,
    )
    if otp_email_sent or otp_sms_sent:
        messages.success(request, f'Fresh repayment OTP sent again for {collection_request.display_id}.')
    else:
        messages.warning(
            request,
            f'A new repayment OTP was generated for {collection_request.display_id}, but automatic delivery to the customer contact could not be confirmed.',
        )
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
            status_message = 'pickup was confirmed and delivery is now in progress'
            customer_status_message = (
                f'Order #{locked_order.id} pickup was confirmed and the rider is now heading to your address. '
                f'Delivery OTP: {locked_order.customer_otp}.'
            )
            success_message = f'Pickup confirmed for order #{locked_order.id}.'
            email_subject = f'Your order {locked_order.display_id} has been picked up'
            email_headline = 'Your rider arrived at the store and confirmed pickup.'
            email_detail = (
                'The app status now shows that pickup is complete and delivery is in progress. '
                f'Your handoff OTP is {locked_order.customer_otp}. We will continue sending updates by email.'
            )
            store_status_message = (
                f'Order #{locked_order.id} was picked up by {locked_rider.full_name} and is now on the way to the customer.'
            )
            store_email_subject = f'{locked_order.display_id} picked up by rider'
            store_email_headline = 'The rider confirmed pickup from your store.'
            store_email_detail = (
                f'{locked_rider.full_name} marked arrival at pickup and collected the order. '
                'The customer has been updated in the app and by email.'
            )
        else:
            if locked_order.status != OrderStatus.OUT_FOR_DELIVERY:
                messages.error(request, 'This order must be out for delivery before completion.')
                return redirect('core:rider_deliveries')
            if locked_order.payment_method == PaymentMethod.COD and locked_order.cod_collection_mode == CodCollectionMode.ONLINE and not order_customer_payment_complete(locked_order):
                messages.error(request, 'Wait for the customer Razorpay payment link to complete before marking this COD order delivered.')
                return redirect('core:rider_deliveries')
            if delivery_otp_is_expired(locked_order):
                messages.error(request, 'Customer OTP expired. Resend a fresh OTP before completing delivery.')
                return redirect('core:rider_deliveries')
            if otp != locked_order.customer_otp:
                messages.error(request, 'Customer OTP did not match.')
                return redirect('core:rider_deliveries')

            locked_order.status = OrderStatus.DELIVERED
            locked_order.delivered_at = timezone.now()
            if locked_order.payment_method == PaymentMethod.COD and locked_order.cod_collection_mode == CodCollectionMode.ONLINE:
                locked_order.settlement_status = SettlementStatus.NOT_REQUIRED
            locked_order.save(update_fields=['status', 'updated_at', 'delivered_at', 'settlement_status'])
            locked_rider.is_available = True
            locked_rider.save(update_fields=['is_available', 'updated_at'])
            status_message = 'was delivered successfully'
            if locked_order.payment_method == PaymentMethod.COD and locked_order.cod_collection_mode == CodCollectionMode.CASH:
                customer_status_message = (
                    f'Order #{locked_order.id} was delivered successfully. Cash handoff is recorded and rider settlement is now tracked.'
                )
            elif locked_order.payment_method == PaymentMethod.COD and locked_order.cod_collection_mode == CodCollectionMode.ONLINE:
                customer_status_message = f'Order #{locked_order.id} was delivered successfully after online COD payment.'
            else:
                customer_status_message = f'Order #{locked_order.id} was delivered successfully.'
            success_message = f'Order #{locked_order.id} marked as delivered.'
            email_subject = f'Your order {locked_order.display_id} was delivered'
            email_headline = 'Your order has been delivered successfully.'
            if locked_order.payment_method == PaymentMethod.COD and locked_order.cod_collection_mode == CodCollectionMode.CASH:
                email_detail = (
                    'The rider completed delivery and the order now reflects a cash handoff. '
                    'The rider settlement back to GramExpress is tracked separately in the rider dashboard.'
                )
                store_status_message = (
                    f'Order #{locked_order.id} was delivered successfully by {locked_rider.full_name}. '
                    'Customer cash handoff is recorded.'
                )
            elif locked_order.payment_method == PaymentMethod.COD and locked_order.cod_collection_mode == CodCollectionMode.ONLINE:
                email_detail = (
                    'The rider completed delivery after the COD online payment link was successfully paid. '
                    'Your final invoice summary is included below.'
                )
                store_status_message = (
                    f'Order #{locked_order.id} was delivered successfully by {locked_rider.full_name} after online COD payment.'
                )
            else:
                email_detail = 'Thank you for ordering with GramExpress. Your final invoice summary is included below.'
                store_status_message = f'Order #{locked_order.id} was delivered successfully by {locked_rider.full_name}.'
            store_email_subject = f'{locked_order.display_id} delivered successfully'
            store_email_headline = 'The rider completed delivery for this order.'
            store_email_detail = (
                f'{locked_rider.full_name} marked the order as delivered after customer OTP verification.'
            )

    create_notification(
        customer=locked_order.customer,
        order=locked_order,
        title='Delivery status updated',
        body=customer_status_message,
        notification_type=NotificationType.RIDER,
    )
    create_notification(
        shop_owner=locked_order.shop.owner,
        order=locked_order,
        title='Delivery status updated',
        body=store_status_message,
        notification_type=NotificationType.RIDER,
    )
    customer_emailed, _ = send_order_status_email(
        order=locked_order,
        subject=email_subject,
        headline=email_headline,
        detail=email_detail,
    )
    customer_sms_sent = False
    if next_status == OrderStatus.OUT_FOR_DELIVERY:
        customer_sms_sent, _ = send_customer_delivery_otp_sms(
            order=locked_order,
            intro='Your GramExpress order was picked up. Share this code only at delivery handoff.',
        )
    store_emailed, _ = send_store_order_status_email(
        order=locked_order,
        subject=store_email_subject,
        headline=store_email_headline,
        detail=store_email_detail,
    )
    messages.success(
        request,
        f'{success_message}'
        f'{" Customer emailed." if customer_emailed else ""}'
        f'{" Customer SMS sent." if customer_sms_sent else ""}'
        f'{" Store emailed." if store_emailed else ""}',
    )
    if next_status == OrderStatus.DELIVERED:
        return redirect('core:rider_completed_orders')
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
                    'src': '/static/core/gramexpress.webp',
                    'sizes': '512x512',
                    'type': 'image/webp',
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
        f'/static/core/gramexpress.webp?v={asset_version}',
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
