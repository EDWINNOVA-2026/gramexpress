from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class ApprovalStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class ShopType(models.TextChoices):
    KIRANA = 'kirana', 'Kirana'
    MEDICAL = 'medical', 'Medical'
    BAKERY = 'bakery', 'Bakery'


class VehicleType(models.TextChoices):
    ELECTRIC = 'electric', 'Electric'
    PETROL = 'petrol', 'Petrol'


class OrderStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    CONFIRMED = 'confirmed', 'Confirmed'
    PACKED = 'packed', 'Packed'
    OUT_FOR_DELIVERY = 'out_for_delivery', 'Out For Delivery'
    DELIVERED = 'delivered', 'Delivered'
    CANCELLED = 'cancelled', 'Cancelled'


class PaymentMethod(models.TextChoices):
    COD = 'cod', 'Cash On Delivery'
    RAZORPAY = 'razorpay', 'Razorpay'


class PaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PAID = 'paid', 'Paid'
    FAILED = 'failed', 'Failed'


class CodCollectionMode(models.TextChoices):
    ONLINE = 'online', 'Online COD Payment'
    CASH = 'cash', 'Cash Collected'


class SettlementStatus(models.TextChoices):
    NOT_REQUIRED = 'not_required', 'Not Required'
    QR_READY = 'qr_ready', 'QR Ready'
    PAID = 'paid', 'Settled'
    FAILED = 'failed', 'Failed'


class RoleType(models.TextChoices):
    CUSTOMER = 'customer', 'Customer'
    SHOP = 'shop', 'Store Owner'
    RIDER = 'rider', 'Rider'
    ADMIN = 'admin', 'Admin'


class NotificationType(models.TextChoices):
    ORDER = 'order', 'Order'
    STORE = 'store', 'Store'
    RIDER = 'rider', 'Rider'
    PAYMENT = 'payment', 'Payment'
    PROMO = 'promo', 'Promo'
    SYSTEM = 'system', 'System'


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class LocationMixin(models.Model):
    latitude = models.DecimalField(max_digits=9, decimal_places=6, default=Decimal('12.915300'))
    longitude = models.DecimalField(max_digits=9, decimal_places=6, default=Decimal('76.643800'))

    class Meta:
        abstract = True

    @property
    def google_maps_url(self) -> str:
        return f'https://www.google.com/maps/search/?api=1&query={self.latitude},{self.longitude}'

    @property
    def short_coordinates(self) -> str:
        return f'{self.latitude}, {self.longitude}'


class CustomerProfile(TimeStampedModel, LocationMixin):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='customer_profile',
    )
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True)
    preferred_language = models.CharField(max_length=2, default='en')
    address_line_1 = models.CharField(max_length=160)
    address_line_2 = models.CharField(max_length=160, blank=True)
    district = models.CharField(max_length=80)
    pincode = models.CharField(max_length=12)

    class Meta:
        ordering = ['full_name']

    def __str__(self) -> str:
        return f'{self.full_name} ({self.phone})'


class ShopOwnerProfile(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shop_owner_profile',
    )
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True)
    approval_status = models.CharField(
        max_length=12,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )

    class Meta:
        ordering = ['full_name']

    def __str__(self) -> str:
        return self.full_name


class RiderProfile(TimeStampedModel, LocationMixin):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rider_profile',
    )
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True)
    age = models.PositiveIntegerField()
    vehicle_type = models.CharField(max_length=12, choices=VehicleType.choices)
    approval_status = models.CharField(
        max_length=12,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )
    is_available = models.BooleanField(default=False)
    service_radius_km = models.PositiveIntegerField(default=10)
    max_service_radius_km = models.PositiveIntegerField(default=17)
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('4.7'))
    photo_url = models.URLField(blank=True)
    photo = models.FileField(upload_to='riders/', blank=True)

    class Meta:
        ordering = ['full_name']

    def __str__(self) -> str:
        return self.full_name


class Shop(TimeStampedModel, LocationMixin):
    owner = models.ForeignKey(
        ShopOwnerProfile,
        on_delete=models.CASCADE,
        related_name='shops',
    )
    name = models.CharField(max_length=140)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    shop_type = models.CharField(max_length=12, choices=ShopType.choices)
    area = models.CharField(max_length=120)
    address_line_1 = models.CharField(max_length=160)
    address_line_2 = models.CharField(max_length=160, blank=True)
    district = models.CharField(max_length=80)
    pincode = models.CharField(max_length=12)
    description = models.TextField(default='Local quick-commerce partner')
    offer = models.CharField(max_length=160, default='Fresh local delivery')
    image_url = models.URLField(blank=True)
    image = models.FileField(upload_to='shops/', blank=True)
    is_open = models.BooleanField(default=False)
    approval_status = models.CharField(
        max_length=12,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )
    rating = models.DecimalField(max_digits=3, decimal_places=1, default=Decimal('4.5'))

    class Meta:
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f'{self.name}-{self.owner.phone}')[:160]
        super().save(*args, **kwargs)

    @property
    def image_source(self) -> str:
        if self.image:
            return self.image.url
        return self.image_url

    def __str__(self) -> str:
        return self.name


class Product(TimeStampedModel):
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='products')
    name = models.CharField(max_length=120)
    subtitle = models.CharField(max_length=160)
    category = models.CharField(max_length=80)
    unit = models.CharField(max_length=30)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image_url = models.URLField(blank=True)
    color = models.CharField(max_length=20, default='#F1E0B8')
    tag = models.CharField(max_length=80, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self) -> str:
        return f'{self.name} - {self.shop.name}'


class CheckoutSession(TimeStampedModel):
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='checkout_sessions',
    )
    payment_method = models.CharField(max_length=12, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    payment_status = models.CharField(max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=3, default='INR')
    customer_notes = models.CharField(max_length=200, blank=True)
    delivery_address = models.CharField(max_length=240)
    cart_snapshot = models.JSONField(default=dict, blank=True)
    cart_signature = models.CharField(max_length=64)
    receipt = models.CharField(max_length=40, blank=True, db_index=True)
    razorpay_order_id = models.CharField(max_length=80, blank=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=80, blank=True)
    razorpay_signature = models.CharField(max_length=160, blank=True)
    failure_reason = models.CharField(max_length=240, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'Checkout #{self.id} - {self.customer.full_name}'

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None


class Order(TimeStampedModel):
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='orders',
    )
    shop = models.ForeignKey(Shop, on_delete=models.CASCADE, related_name='orders')
    rider = models.ForeignKey(
        RiderProfile,
        on_delete=models.SET_NULL,
        related_name='orders',
        null=True,
        blank=True,
    )
    checkout_session = models.ForeignKey(
        CheckoutSession,
        on_delete=models.SET_NULL,
        related_name='orders',
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    payment_method = models.CharField(max_length=12, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    payment_status = models.CharField(max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    payment_reference = models.CharField(max_length=120, blank=True)
    cod_collection_mode = models.CharField(max_length=12, choices=CodCollectionMode.choices, blank=True)
    cod_payment_link_id = models.CharField(max_length=80, blank=True, db_index=True)
    cod_payment_link_url = models.URLField(blank=True)
    cod_payment_link_status = models.CharField(max_length=24, blank=True)
    customer_paid_at = models.DateTimeField(null=True, blank=True)
    cash_confirmed_at = models.DateTimeField(null=True, blank=True)
    settlement_status = models.CharField(
        max_length=20,
        choices=SettlementStatus.choices,
        default=SettlementStatus.NOT_REQUIRED,
    )
    settlement_qr_id = models.CharField(max_length=80, blank=True, db_index=True)
    settlement_qr_image_url = models.URLField(blank=True)
    settlement_payment_id = models.CharField(max_length=80, blank=True)
    settlement_generated_at = models.DateTimeField(null=True, blank=True)
    settlement_paid_at = models.DateTimeField(null=True, blank=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('20.00'))
    delivery_address = models.CharField(max_length=240)
    customer_otp = models.CharField(max_length=6, default='123456')
    customer_notes = models.CharField(max_length=200, blank=True)
    cancellation_reason = models.CharField(max_length=240, blank=True)
    cancelled_by_role = models.CharField(max_length=12, choices=RoleType.choices, blank=True)
    customer_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    customer_review = models.CharField(max_length=240, blank=True)
    store_rating = models.PositiveSmallIntegerField(null=True, blank=True)
    store_review = models.CharField(max_length=240, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'#{self.id} - {self.customer.full_name}'

    def recalculate_total(self):
        subtotal = sum(item.line_total for item in self.items.all())
        self.total_amount = subtotal + self.delivery_fee

    @property
    def display_id(self) -> str:
        return f'GRX-{1000 + self.id}'

    @property
    def tracking_label(self) -> str:
        if self.rider:
            return f'Assigned to {self.rider.full_name}. Updates are shared by email.'
        return 'Waiting for rider assignment'

    @property
    def can_be_cancelled_by_customer(self) -> bool:
        return self.status in [OrderStatus.PENDING, OrderStatus.CONFIRMED]

    @property
    def can_be_reordered(self) -> bool:
        return self.status in [OrderStatus.DELIVERED, OrderStatus.CANCELLED]

    @property
    def can_be_rated_by_customer(self) -> bool:
        return self.status == OrderStatus.DELIVERED and self.customer_rating is None

    @property
    def can_be_rated_by_store(self) -> bool:
        return self.status == OrderStatus.DELIVERED and self.store_rating is None and self.rider_id is not None


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='order_items')
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity

    def __str__(self) -> str:
        return f'{self.product.name} x {self.quantity}'


class Notification(TimeStampedModel):
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
    )
    shop_owner = models.ForeignKey(
        ShopOwnerProfile,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
    )
    rider = models.ForeignKey(
        RiderProfile,
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True,
        blank=True,
    )
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    notification_type = models.CharField(
        max_length=12,
        choices=NotificationType.choices,
        default=NotificationType.SYSTEM,
    )
    title = models.CharField(max_length=120)
    body = models.CharField(max_length=240)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return self.title

    @property
    def accent_class(self) -> str:
        return {
            NotificationType.ORDER: 'notification-accent-order',
            NotificationType.STORE: 'notification-accent-store',
            NotificationType.RIDER: 'notification-accent-rider',
            NotificationType.PAYMENT: 'notification-accent-payment',
            NotificationType.PROMO: 'notification-accent-promo',
            NotificationType.SYSTEM: 'notification-accent-system',
        }.get(self.notification_type, 'notification-accent-system')

    @property
    def glyph(self) -> str:
        return {
            NotificationType.ORDER: 'Order',
            NotificationType.STORE: 'Store',
            NotificationType.RIDER: 'Rider',
            NotificationType.PAYMENT: 'Pay',
            NotificationType.PROMO: 'Promo',
            NotificationType.SYSTEM: 'Info',
        }.get(self.notification_type, 'Info')


class EmailOtpToken(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='email_otp_tokens',
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=12, choices=RoleType.choices)
    email = models.EmailField()
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_valid(self) -> bool:
        return not self.is_used and self.expires_at >= timezone.now()


class OtpPurpose(models.TextChoices):
    REGISTER = 'register', 'Register'
    LOGIN_EMAIL = 'login_email', 'Login Email'


class OtpChannel(models.TextChoices):
    EMAIL = 'email', 'Email'
    SMS = 'sms', 'SMS'


class AuthOtpToken(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='auth_otp_tokens',
        null=True,
        blank=True,
    )
    role = models.CharField(max_length=12, choices=RoleType.choices, blank=True)
    purpose = models.CharField(max_length=20, choices=OtpPurpose.choices)
    channel = models.CharField(max_length=10, choices=OtpChannel.choices)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    code = models.CharField(max_length=6)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_valid(self) -> bool:
        return not self.is_used and self.expires_at >= timezone.now()
