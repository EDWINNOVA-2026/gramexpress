from django.urls import reverse

from .models import RoleType


def shell_navigation(request):
    user = request.user
    active_role = None
    dashboard_label = 'Login'
    dashboard_url = reverse('core:login')
    unread_notification_count = 0

    if user.is_authenticated:
        if user.is_staff:
            active_role = RoleType.ADMIN
            dashboard_label = 'Django Admin'
            dashboard_url = reverse('admin:index')
        elif hasattr(user, 'customer_profile'):
            active_role = RoleType.CUSTOMER
            dashboard_label = 'Customer Hub'
            dashboard_url = reverse('core:customer_dashboard')
            unread_notification_count = user.customer_profile.notifications.filter(is_read=False).count()
        elif hasattr(user, 'shop_owner_profile'):
            active_role = RoleType.SHOP
            dashboard_label = 'Store Hub'
            dashboard_url = reverse('core:shop_dashboard')
            unread_notification_count = user.shop_owner_profile.notifications.filter(is_read=False).count()
        elif hasattr(user, 'rider_profile'):
            active_role = RoleType.RIDER
            dashboard_label = 'Rider Hub'
            dashboard_url = reverse('core:rider_dashboard')
            unread_notification_count = user.rider_profile.notifications.filter(is_read=False).count()

    return {
        'shell_active_role': active_role,
        'shell_dashboard_label': dashboard_label,
        'shell_dashboard_url': dashboard_url,
        'shell_unread_notification_count': unread_notification_count,
    }
