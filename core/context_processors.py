from django.urls import reverse

from .models import RoleType


def shell_navigation(request):
    user = request.user
    active_role = None
    dashboard_label = 'Login'
    dashboard_url = reverse('core:login')

    if user.is_authenticated:
        if user.is_staff:
            active_role = RoleType.ADMIN
            dashboard_label = 'Django Admin'
            dashboard_url = reverse('admin:index')
        elif hasattr(user, 'customer_profile'):
            active_role = RoleType.CUSTOMER
            dashboard_label = 'Customer Hub'
            dashboard_url = reverse('core:customer_dashboard')
        elif hasattr(user, 'shop_owner_profile'):
            active_role = RoleType.SHOP
            dashboard_label = 'Store Hub'
            dashboard_url = reverse('core:shop_dashboard')
        elif hasattr(user, 'rider_profile'):
            active_role = RoleType.RIDER
            dashboard_label = 'Rider Hub'
            dashboard_url = reverse('core:rider_dashboard')

    return {
        'shell_active_role': active_role,
        'shell_dashboard_label': dashboard_label,
        'shell_dashboard_url': dashboard_url,
    }
