from django.contrib import admin

from .models import (
    CustomerProfile,
    EmailOtpToken,
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
    list_display = ('full_name', 'phone', 'district', 'preferred_language')
    search_fields = ('full_name', 'phone', 'email')


@admin.register(ShopOwnerProfile)
class ShopOwnerProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'approval_status')
    list_filter = ('approval_status',)
    search_fields = ('full_name', 'phone', 'email')
    list_editable = ('approval_status',)


@admin.register(RiderProfile)
class RiderProfileAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'phone', 'vehicle_type', 'approval_status', 'is_available', 'rating')
    list_filter = ('approval_status', 'vehicle_type', 'is_available')
    search_fields = ('full_name', 'phone', 'email')
    list_editable = ('approval_status', 'is_available')
    actions = [approve_riders, reject_riders]


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ('name', 'shop_type', 'district', 'approval_status', 'is_open', 'owner', 'rating')
    list_filter = ('shop_type', 'approval_status', 'district', 'is_open')
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'owner__full_name', 'district')
    list_editable = ('approval_status', 'is_open')
    actions = [approve_stores, reject_stores]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'shop', 'price', 'stock', 'category')
    list_filter = ('category', 'shop__shop_type')
    search_fields = ('name', 'shop__name')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'shop', 'rider', 'status', 'payment_method', 'payment_status', 'total_amount', 'delivered_at')
    list_filter = ('status', 'payment_method', 'payment_status')
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
