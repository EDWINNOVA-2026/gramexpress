from django.conf import settings
from django.urls import reverse

from .models import RoleType


def nav_link(label: str, url: str, icon: str, *, match_url: str | None = None) -> dict[str, str]:
    return {
        'label': label,
        'url': url,
        'icon': icon,
        'match_url': match_url or url,
    }


def shell_navigation(request):
    user = request.user
    active_role = None
    dashboard_label = 'Login'
    dashboard_url = reverse('core:login')
    unread_notification_count = 0
    role_links = []
    primary_links = []
    mobile_links = []
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
                nav_link('Admin', reverse('admin:index'), 'shield'),
            ]
            menu_links = [
                nav_link('Admin', reverse('admin:index'), 'shield'),
                nav_link('Support', reverse('core:support'), 'life-buoy'),
            ]
        elif hasattr(user, 'customer_profile'):
            active_role = RoleType.CUSTOMER
            dashboard_label = 'Customer Home'
            dashboard_url = reverse('core:customer_dashboard')
            unread_notification_count = user.customer_profile.notifications.filter(is_read=False).count()
            user_label = user.customer_profile.full_name
            user_initial = (user_label[:1] or 'C').upper()
            role_links = [
                nav_link('Home', reverse('core:customer_dashboard'), 'house'),
                nav_link('Cart', reverse('core:customer_cart'), 'shopping-cart'),
                nav_link('Khata', reverse('core:customer_khatabook'), 'wallet'),
                nav_link('Orders', reverse('core:customer_orders'), 'package'),
                nav_link('Profile', reverse('core:customer_profile'), 'user'),
            ]
            primary_links = role_links[:3]
            mobile_links = [
                nav_link('Home', reverse('core:customer_dashboard'), 'house'),
                nav_link('Cart', reverse('core:customer_cart'), 'shopping-cart'),
                nav_link('Orders', reverse('core:customer_orders'), 'package'),
                nav_link('Khata', reverse('core:customer_khatabook'), 'wallet'),
                nav_link('Profile', reverse('core:customer_profile'), 'user'),
            ]
            menu_links = [
                nav_link('Khata', reverse('core:customer_khatabook'), 'wallet'),
                nav_link('Edit Profile', reverse('core:customer_profile'), 'square-pen'),
                nav_link('Previous Orders', f"{reverse('core:customer_orders')}#history", 'history'),
                nav_link('Customer Support', reverse('core:support'), 'life-buoy'),
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
                    nav_link('Overview', reverse('core:shop_dashboard'), 'layout-dashboard'),
                    nav_link('Orders', reverse('core:shop_orders'), 'clipboard-list'),
                    nav_link('Khata', reverse('core:shop_khatabook'), 'wallet'),
                    nav_link('Catalog', reverse('core:shop_products'), 'boxes'),
                    nav_link('Settings', reverse('core:shop_settings'), 'settings'),
                ]
                primary_links = role_links[:3]
                menu_links = [
                    nav_link('Catalog', reverse('core:shop_products'), 'boxes'),
                    nav_link('Store Settings', reverse('core:shop_settings'), 'settings'),
                    nav_link('Customer Support', reverse('core:support'), 'life-buoy'),
                ]
            else:
                dashboard_label = 'Complete Store Setup'
                dashboard_url = reverse('core:shop_start')
                role_links = [
                    nav_link('Store Setup', reverse('core:shop_start'), 'store'),
                    nav_link('Support', reverse('core:support'), 'life-buoy'),
                ]
                primary_links = role_links
                menu_links = [
                    nav_link('Store Setup', reverse('core:shop_start'), 'store'),
                    nav_link('Customer Support', reverse('core:support'), 'life-buoy'),
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
                nav_link('New', reverse('core:rider_dashboard'), 'package'),
                nav_link('Active', reverse('core:rider_deliveries'), 'bike'),
                nav_link('Done', reverse('core:rider_completed_orders'), 'badge-check'),
                nav_link('Earn', reverse('core:rider_earnings'), 'wallet'),
                nav_link('Profile', reverse('core:rider_profile'), 'user'),
            ]
            primary_links = role_links
            menu_links = [
                nav_link('Edit Profile', reverse('core:rider_profile'), 'square-pen'),
                nav_link('Completed Orders', reverse('core:rider_completed_orders'), 'badge-check'),
                nav_link('Earnings', reverse('core:rider_earnings'), 'wallet'),
                nav_link('Customer Support', reverse('core:support'), 'life-buoy'),
            ]

    return {
        'shell_active_role': active_role,
        'shell_dashboard_label': dashboard_label,
        'shell_dashboard_url': dashboard_url,
        'shell_unread_notification_count': unread_notification_count,
        'shell_role_links': role_links,
        'shell_primary_links': primary_links or role_links[:3],
        'shell_mobile_links': mobile_links or role_links,
        'shell_menu_links': menu_links,
        'shell_user_label': user_label,
        'shell_user_initial': user_initial,
        'shell_rider_menu_state': rider_menu_state,
        'shell_asset_version': getattr(settings, 'APP_ASSET_VERSION', '1'),
        'shell_pwa_enabled': getattr(settings, 'PWA_ENABLED', False),
    }
