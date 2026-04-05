from datetime import timedelta
from decimal import Decimal
from functools import lru_cache

from django.conf import settings
from django.db import models
from django.db.utils import OperationalError, ProgrammingError
from django.utils import timezone
from django.utils.text import slugify

DEFAULT_DELIVERY_FEE = Decimal('15.00')


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
    KHATABOOK = 'khata', 'KhataBook Credit'


class PaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PAID = 'paid', 'Paid'
    FAILED = 'failed', 'Failed'


class DeliverySlot(models.TextChoices):
    PRIORITY = 'PRIORITY', 'Priority Delivery'
    ECO = 'ECO', 'Eco Delivery'
    COST_SAVER = 'COST_SAVER', 'Saver Delivery'
    BUDGET = 'BUDGET', 'Next Day'


class CodCollectionMode(models.TextChoices):
    ONLINE = 'online', 'Online COD Payment'
    CASH = 'cash', 'Cash Collected'


class SettlementStatus(models.TextChoices):
    NOT_REQUIRED = 'not_required', 'Not Required'
    QR_READY = 'qr_ready', 'QR Ready'
    PAID = 'paid', 'Settled'
    FAILED = 'failed', 'Failed'


class KhataBookCycleStatus(models.TextChoices):
    OPEN = 'open', 'Open'
    COLLECTION_REQUESTED = 'collection_requested', 'Collection Requested'
    PAID = 'paid', 'Paid'


class KhataBookSettlementMethod(models.TextChoices):
    COD_UPI = 'cod_upi', 'COD / UPI Collection'
    RAZORPAY_UPI = 'razorpay_upi', 'Razorpay UPI'


class KhataBookCollectionStatus(models.TextChoices):
    REQUESTED = 'requested', 'Requested'
    ACCEPTED = 'accepted', 'Accepted'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


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


DEFAULT_DELIVERY_SLOT = DeliverySlot.ECO
DELIVERY_SLOT_RULES = {
    DeliverySlot.PRIORITY: {
        'name': 'Priority Delivery',
        'time_label': '30-40 minutes',
        'description': 'Fast delivery with highest priority.',
        'delivery_fee': Decimal('20.00'),
        'color': 'red',
        'priority_level': 1,
        'time_limit': timedelta(minutes=40),
        'tag': 'Fastest',
    },
    DeliverySlot.ECO: {
        'name': 'Eco Delivery',
        'time_label': '1-4 hours',
        'description': 'Optimized route delivery.',
        'delivery_fee': Decimal('10.00'),
        'color': 'green',
        'priority_level': 2,
        'time_limit': timedelta(hours=4),
        'tag': 'Recommended',
    },
    DeliverySlot.COST_SAVER: {
        'name': 'Saver Delivery',
        'time_label': '4-8 hours',
        'description': 'Delivered during low traffic routes.',
        'delivery_fee': Decimal('5.00'),
        'color': 'blue',
        'priority_level': 3,
        'time_limit': timedelta(hours=8),
        'tag': 'Save Money',
    },
    DeliverySlot.BUDGET: {
        'name': 'Next Day',
        'time_label': 'Next day delivery',
        'description': 'Free delivery on the next available day.',
        'delivery_fee': Decimal('0.00'),
        'color': 'gray',
        'priority_level': 4,
        'time_limit': timedelta(days=1),
        'tag': 'Free',
    },
}


def clear_delivery_slot_cache() -> None:
    get_delivery_slot_setting_overrides.cache_clear()


@lru_cache(maxsize=1)
def get_delivery_slot_setting_overrides() -> dict[str, dict[str, object]]:
    try:
        settings_map = {
            setting.code: {
                'name': setting.name,
                'time_label': setting.time_label,
                'description': setting.description,
                'delivery_fee': setting.delivery_fee,
                'color': setting.color,
                'priority_level': setting.priority_level,
                'time_limit': timedelta(minutes=setting.time_limit_minutes),
                'tag': setting.tag,
            }
            for setting in DeliverySlotSetting.objects.all()
        }
    except (OperationalError, ProgrammingError):
        return {}
    legacy_aliases = {
        DeliverySlot.COST_SAVER: {
            'name': ('Cost Saver', 'Saver Delivery'),
        },
        DeliverySlot.BUDGET: {
            'name': ('Budget Delivery', 'Next Day'),
            'time_label': ('8-12 hours', 'Next day delivery'),
            'description': ('Lowest cost delivery with flexible timing.', 'Free delivery on the next available day.'),
            'tag': ('Lowest Cost', 'Free'),
        },
    }
    for code, replacements in legacy_aliases.items():
        slot = settings_map.get(code)
        if not slot:
            continue
        for field_name, values in replacements.items():
            old_value, new_value = values
            if slot.get(field_name) == old_value:
                slot[field_name] = new_value
    return settings_map


def delivery_slot_rule(slot_code: str) -> dict[str, object]:
    selected_slot = slot_code if slot_code in DELIVERY_SLOT_RULES else DEFAULT_DELIVERY_SLOT
    rule = dict(DELIVERY_SLOT_RULES[selected_slot])
    override = get_delivery_slot_setting_overrides().get(selected_slot)
    if override:
        rule.update(override)
    return rule


def delivery_slot_fee(slot_code: str) -> Decimal:
    return Decimal(str(delivery_slot_rule(slot_code)['delivery_fee'])).quantize(Decimal('0.01'))


def delivery_slot_deadline_from(order_time, slot_code: str):
    return order_time + delivery_slot_rule(slot_code)['time_limit']


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class DeliverySlotSetting(TimeStampedModel):
    code = models.CharField(max_length=20, choices=DeliverySlot.choices, unique=True)
    name = models.CharField(max_length=80)
    description = models.CharField(max_length=200, blank=True)
    time_label = models.CharField(max_length=40)
    time_limit_minutes = models.PositiveIntegerField(default=240)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    color = models.CharField(max_length=20, default='gray')
    priority_level = models.PositiveSmallIntegerField(default=1)
    tag = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ['priority_level', 'code']
        verbose_name = 'Delivery slot setting'
        verbose_name_plural = 'Delivery slot settings'

    def __str__(self) -> str:
        return f'{self.name} ({self.code})'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        clear_delivery_slot_cache()

    def delete(self, *args, **kwargs):
        response = super().delete(*args, **kwargs)
        clear_delivery_slot_cache()
        return response


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

    @property
    def photo_source(self) -> str:
        if self.photo:
            return self.photo.url
        return self.photo_url

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
    state = models.CharField(max_length=80, blank=True)
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
    description = models.TextField(blank=True, default='')
    category = models.CharField(max_length=80)
    unit = models.CharField(max_length=30)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    image_url = models.URLField(blank=True)
    image = models.FileField(upload_to='products/', blank=True)
    color = models.CharField(max_length=20, default='#F1E0B8')
    tag = models.CharField(max_length=80, blank=True)
    is_visible = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']

    @property
    def image_source(self) -> str:
        if self.image:
            return self.image.url
        return self.image_url

    @property
    def stock_status(self) -> str:
        if self.stock <= 0:
            return 'out_of_stock'
        if self.stock <= 10:
            return 'low_stock'
        return 'in_stock'

    @property
    def stock_status_label(self) -> str:
        return {
            'in_stock': 'In Stock',
            'low_stock': 'Low Stock',
            'out_of_stock': 'Out Of Stock',
        }[self.stock_status]

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


class KhataBookCycle(TimeStampedModel):
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='khatabook_cycles',
    )
    week_start = models.DateField(db_index=True)
    due_date = models.DateField(db_index=True)
    status = models.CharField(
        max_length=24,
        choices=KhataBookCycleStatus.choices,
        default=KhataBookCycleStatus.OPEN,
    )
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    settlement_method = models.CharField(
        max_length=24,
        choices=KhataBookSettlementMethod.choices,
        blank=True,
    )
    collection_requested_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    razorpay_order_id = models.CharField(max_length=80, blank=True, db_index=True)
    razorpay_payment_id = models.CharField(max_length=80, blank=True)
    razorpay_signature = models.CharField(max_length=160, blank=True)
    failure_reason = models.CharField(max_length=240, blank=True)

    class Meta:
        ordering = ['-week_start']
        constraints = [
            models.UniqueConstraint(fields=['customer', 'week_start'], name='unique_khatabook_cycle_per_customer_week'),
        ]

    def __str__(self) -> str:
        return f'KhataBook {self.customer.full_name} - {self.week_start}'

    @property
    def outstanding_amount(self) -> Decimal:
        remaining = self.total_amount - self.paid_amount
        return remaining if remaining > Decimal('0.00') else Decimal('0.00')


class KhataBookCollectionRequest(TimeStampedModel, LocationMixin):
    customer = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='khatabook_collection_requests',
    )
    khata_cycle = models.ForeignKey(
        KhataBookCycle,
        on_delete=models.CASCADE,
        related_name='collection_requests',
    )
    rider = models.ForeignKey(
        RiderProfile,
        on_delete=models.SET_NULL,
        related_name='khatabook_collection_requests',
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=KhataBookCollectionStatus.choices,
        default=KhataBookCollectionStatus.REQUESTED,
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    collection_address = models.CharField(max_length=240)
    collection_notes = models.CharField(max_length=200, blank=True)
    collection_otp = models.CharField(max_length=6, blank=True)
    payment_reference = models.CharField(max_length=120, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self) -> str:
        return f'Khata Collection #{self.id} - {self.customer.full_name}'

    @property
    def display_id(self) -> str:
        return f'KHC-{1000 + self.id}'


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
    khata_cycle = models.ForeignKey(
        KhataBookCycle,
        on_delete=models.SET_NULL,
        related_name='orders',
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    payment_method = models.CharField(max_length=12, choices=PaymentMethod.choices, default=PaymentMethod.COD)
    payment_status = models.CharField(max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)
    payment_reference = models.CharField(max_length=120, blank=True)
    credit_due_date = models.DateField(null=True, blank=True)
    credit_paid_at = models.DateTimeField(null=True, blank=True)
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
    delivery_slot = models.CharField(max_length=20, choices=DeliverySlot.choices, default=DEFAULT_DELIVERY_SLOT)
    delivery_deadline = models.DateTimeField(null=True, blank=True)
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=DEFAULT_DELIVERY_FEE)
    distance_km = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal('0.00'))
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
    def delivery_slot_config(self) -> dict[str, object]:
        return delivery_slot_rule(self.delivery_slot)

    @property
    def slot_priority(self) -> int:
        return int(self.delivery_slot_config['priority_level'])

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
            NotificationType.ORDER: 'OD',
            NotificationType.STORE: 'ST',
            NotificationType.RIDER: 'RD',
            NotificationType.PAYMENT: 'PY',
            NotificationType.PROMO: 'PR',
            NotificationType.SYSTEM: 'IN',
        }.get(self.notification_type, 'IN')

    @property
    def icon_name(self) -> str:
        return {
            NotificationType.ORDER: 'package',
            NotificationType.STORE: 'store',
            NotificationType.RIDER: 'bike',
            NotificationType.PAYMENT: 'credit-card',
            NotificationType.PROMO: 'tag',
            NotificationType.SYSTEM: 'bell',
        }.get(self.notification_type, 'bell')


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
