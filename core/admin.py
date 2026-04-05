from django.contrib import admin
from django.utils.html import format_html

from .models import (
    ApprovalStatus,
    CustomerProfile,
    DeliverySlotSetting,
    EmailOtpToken,
    KhataBookSubscriptionPurchase,
    Notification,
    Order,
    OrderItem,
    Product,
    RiderProfile,
    Shop,
    ShopOwnerProfile,
)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.action(description='Approve selected stores')
def approve_stores(modeladmin, request, queryset):
    queryset.update(approval_status='approved', is_open=True)
    ShopOwnerProfile.objects.filter(shops__in=queryset).update(approval_status='approved')


@admin.action(description='Reject selected stores')
def reject_stores(modeladmin, request, queryset):
    queryset.update(approval_status='rejected', is_open=False)
    ShopOwnerProfile.objects.filter(shops__in=queryset).update(approval_status='rejected')


@admin.action(description='Approve selected riders')
def approve_riders(modeladmin, request, queryset):
    queryset.update(approval_status='approved', is_available=True)


@admin.action(description='Reject selected riders')
def reject_riders(modeladmin, request, queryset):
    queryset.update(approval_status='rejected', is_available=False)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'district', 'preferred_language', 'khatabook_plan', 'khatabook_credit_limit')
    search_fields = ('full_name', 'phone', 'email')


@admin.register(KhataBookSubscriptionPurchase)
class KhataBookSubscriptionPurchaseAdmin(admin.ModelAdmin):
    list_display = ('customer', 'tier', 'credit_limit', 'subscription_fee', 'status', 'activated_at')
    list_filter = ('tier', 'status')
    search_fields = ('customer__full_name', 'customer__phone', 'razorpay_order_id', 'razorpay_payment_id')


@admin.register(ShopOwnerProfile)
class ShopOwnerProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'approval_status')
    list_filter = ('approval_status',)
    search_fields = ('full_name', 'phone', 'email')
    list_editable = ('approval_status',)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        obj.shops.update(
            approval_status=obj.approval_status,
            **({'is_open': False} if obj.approval_status != ApprovalStatus.APPROVED else {}),
        )


@admin.register(RiderProfile)
class RiderProfileAdmin(admin.ModelAdmin):
    list_display = ('photo_preview_tag', 'full_name', 'phone', 'vehicle_type', 'approval_status', 'is_available', 'rating')
    list_filter = ('approval_status', 'vehicle_type', 'is_available')
    search_fields = ('full_name', 'phone', 'email')
    list_editable = ('approval_status', 'is_available')
    actions = [approve_riders, reject_riders]
    readonly_fields = ('photo_preview_tag',)
    fields = (
        'photo_preview_tag',
        'full_name',
        'phone',
        'email',
        'age',
        'vehicle_type',
        'approval_status',
        'is_available',
        'rating',
        'latitude',
        'longitude',
        'photo_url',
        'photo',
    )

    @admin.display(description='Photo')
    def photo_preview_tag(self, obj):
        if not obj.photo_source:
            return 'No photo'
        return format_html(
            '<img src="{}" alt="{}" style="height:48px;width:48px;border-radius:12px;object-fit:cover;border:1px solid #e2e8f0;" />',
            obj.photo_source,
            obj.full_name,
        )


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'shop_type', 'district', 'approval_status', 'is_open', 'owner', 'rating')
    list_filter = ('shop_type', 'approval_status', 'district', 'is_open')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'owner__full_name', 'district')
    list_editable = ('approval_status', 'is_open')
    actions = [approve_stores, reject_stores]

    def save_model(self, request, obj, form, change):
        if obj.approval_status != ApprovalStatus.APPROVED:
            obj.is_open = False
        super().save_model(request, obj, form, change)
        ShopOwnerProfile.objects.filter(pk=obj.owner_id).update(approval_status=obj.approval_status)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'shop', 'price', 'stock', 'category')
    list_filter = ('category', 'shop__shop_type')
    search_fields = ('name', 'shop__name')


@admin.register(DeliverySlotSetting)
class DeliverySlotSettingAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'delivery_fee', 'time_label', 'priority_level', 'tag')
    list_editable = ('delivery_fee', 'time_label', 'priority_level', 'tag')
    search_fields = ('code', 'name', 'description')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer',
        'shop',
        'rider',
        'status',
        'delivery_slot',
        'delivery_deadline',
        'delivery_fee',
        'payment_method',
        'payment_status',
        'total_amount',
        'delivered_at',
    )
    list_filter = ('status', 'delivery_slot', 'payment_method', 'payment_status')
    search_fields = ('customer__full_name', 'shop__name', 'rider__full_name')
    inlines = [OrderItemInline]


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'customer', 'shop_owner', 'rider', 'order', 'is_read', 'created_at')
    list_filter = ('is_read',)
    search_fields = ('title', 'body')


@admin.register(EmailOtpToken)
class EmailOtpTokenAdmin(admin.ModelAdmin):
    list_display = ('email', 'role', 'code', 'is_used', 'expires_at', 'created_at')
    list_filter = ('role', 'is_used')
    search_fields = ('email', 'code')


admin.site.site_header = 'GramExpress Admin'
admin.site.site_title = 'GramExpress Admin'
admin.site.index_title = 'GramExpress Administration'
