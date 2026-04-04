from django.conf import settings
from django.urls import reverse

from .models import RoleType


def shell_navigation(request):
    user = request.user
    active_role = None
    dashboard_label = 'Login'
    dashboard_url = reverse('core:login')
    unread_notification_count = 0
    role_links = []
    primary_links = []
    menu_links = []
    user_label = ''
    user_initial = 'G'
    rider_menu_state = None

    if user.is_authenticated:
        if user.is_staff:
            active_role = RoleType.ADMIN
            dashboard_label = 'Django Admin'
            dashboard_url = reverse('admin:index')
            user_label = user.get_username()
            user_initial = (user_label[:1] or 'A').upper()
            primary_links = [
                {'label': 'Admin', 'url': reverse('admin:index')},
            ]
            menu_links = [
                {'label': 'Admin', 'url': reverse('admin:index')},
                {'label': 'Support', 'url': reverse('core:support')},
            ]
        elif hasattr(user, 'customer_profile'):
            active_role = RoleType.CUSTOMER
            dashboard_label = 'Customer Home'
            dashboard_url = reverse('core:customer_dashboard')
            unread_notification_count = user.customer_profile.notifications.filter(is_read=False).count()
            user_label = user.customer_profile.full_name
            user_initial = (user_label[:1] or 'C').upper()
            role_links = [
                {'label': 'Home', 'url': reverse('core:customer_dashboard')},
                {'label': 'Cart', 'url': reverse('core:customer_cart')},
                {'label': 'KhataBook', 'url': reverse('core:customer_khatabook')},
                {'label': 'Orders', 'url': reverse('core:customer_orders')},
                {'label': 'Profile', 'url': reverse('core:customer_profile')},
            ]
            primary_links = role_links[:3]
            menu_links = [
                {'label': 'KhataBook', 'url': reverse('core:customer_khatabook')},
                {'label': 'Edit Profile', 'url': reverse('core:customer_profile')},
                {'label': 'Previous Orders', 'url': f"{reverse('core:customer_orders')}#history"},
                {'label': 'Customer Support', 'url': reverse('core:support')},
            ]
        elif hasattr(user, 'shop_owner_profile'):
            active_role = RoleType.SHOP
            unread_notification_count = user.shop_owner_profile.notifications.filter(is_read=False).count()
            user_label = user.shop_owner_profile.full_name
            user_initial = (user_label[:1] or 'S').upper()
            if user.shop_owner_profile.shops.exists():
                dashboard_label = 'Store Home'
                dashboard_url = reverse('core:shop_dashboard')
                role_links = [
                    {'label': 'Overview', 'url': reverse('core:shop_dashboard')},
                    {'label': 'Orders', 'url': reverse('core:shop_orders')},
                    {'label': 'Catalog', 'url': reverse('core:shop_products')},
                    {'label': 'Settings', 'url': reverse('core:shop_settings')},
                ]
                primary_links = role_links[:3]
                menu_links = [
                    {'label': 'Store Settings', 'url': reverse('core:shop_settings')},
                    {'label': 'Customer Support', 'url': reverse('core:support')},
                ]
            else:
                dashboard_label = 'Complete Store Setup'
                dashboard_url = reverse('core:shop_start')
                role_links = [
                    {'label': 'Store Setup', 'url': reverse('core:shop_start')},
                    {'label': 'Support', 'url': reverse('core:support')},
                ]
                primary_links = role_links
                menu_links = [
                    {'label': 'Store Setup', 'url': reverse('core:shop_start')},
                    {'label': 'Customer Support', 'url': reverse('core:support')},
                ]
        elif hasattr(user, 'rider_profile'):
            active_role = RoleType.RIDER
            dashboard_label = 'Rider Home'
            dashboard_url = reverse('core:rider_dashboard')
            unread_notification_count = user.rider_profile.notifications.filter(is_read=False).count()
            user_label = user.rider_profile.full_name
            user_initial = (user_label[:1] or 'R').upper()
            rider_menu_state = {
                'is_available': user.rider_profile.is_available,
                'approval_status': user.rider_profile.approval_status,
            }
            role_links = [
                {'label': 'New', 'url': reverse('core:rider_dashboard')},
                {'label': 'Active', 'url': reverse('core:rider_deliveries')},
                {'label': 'Done', 'url': reverse('core:rider_completed_orders')},
                {'label': 'Earn', 'url': reverse('core:rider_earnings')},
                {'label': 'Profile', 'url': reverse('core:rider_profile')},
            ]
            primary_links = role_links
            menu_links = [
                {'label': 'Edit Profile', 'url': reverse('core:rider_profile')},
                {'label': 'Completed Orders', 'url': reverse('core:rider_completed_orders')},
                {'label': 'Earnings', 'url': reverse('core:rider_earnings')},
                {'label': 'Customer Support', 'url': reverse('core:support')},
            ]

    return {
        'shell_active_role': active_role,
        'shell_dashboard_label': dashboard_label,
        'shell_dashboard_url': dashboard_url,
        'shell_unread_notification_count': unread_notification_count,
        'shell_role_links': role_links,
        'shell_primary_links': primary_links or role_links[:3],
        'shell_menu_links': menu_links,
        'shell_user_label': user_label,
        'shell_user_initial': user_initial,
        'shell_rider_menu_state': rider_menu_state,
        'shell_asset_version': getattr(settings, 'APP_ASSET_VERSION', '1'),
        'shell_pwa_enabled': getattr(settings, 'PWA_ENABLED', False),
    }
