from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/google/', views.google_auth_view, name='google_auth'),
    path('auth/register/', views.register_view, name='register'),
    path('auth/email-otp/', views.email_otp_view, name='email_otp'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/mark-all-read/', views.notifications_mark_all_read, name='notifications_mark_all_read'),
    path('notifications/<int:notification_id>/open/', views.notification_open, name='notification_open'),
    path('orders/<int:order_id>/', views.order_detail_view, name='order_detail'),
    path('orders/<int:order_id>/tracking/', views.order_tracking_view, name='order_tracking'),
    path('logout/', views.logout_view, name='logout'),
    path('customer/start/', views.customer_start, name='customer_start'),
    path('customer/dashboard/', views.customer_dashboard, name='customer_dashboard'),
    path('customer/cart/add/<int:product_id>/', views.cart_add, name='cart_add'),
    path('customer/cart/update/<int:product_id>/', views.cart_update, name='cart_update'),
    path('customer/cart/clear/', views.cart_clear, name='cart_clear'),
    path('customer/checkout/', views.customer_checkout, name='customer_checkout'),
    path('customer/order/<int:order_id>/rate/', views.customer_rate_order, name='customer_rate_order'),
    path('shop/start/', views.shop_start, name='shop_start'),
    path('shop/dashboard/', views.shop_dashboard, name='shop_dashboard'),
    path('shop/product/<int:product_id>/delete/', views.shop_delete_product, name='shop_delete_product'),
    path('shop/order/<int:order_id>/status/', views.shop_update_order_status, name='shop_update_order_status'),
    path('shop/order/<int:order_id>/rate/', views.shop_rate_order, name='shop_rate_order'),
    path('rider/start/', views.rider_start, name='rider_start'),
    path('rider/dashboard/', views.rider_dashboard, name='rider_dashboard'),
    path('rider/location/', views.rider_update_location, name='rider_update_location'),
    path('rider/order/<int:order_id>/accept/', views.rider_accept_order, name='rider_accept_order'),
    path('rider/order/<int:order_id>/status/', views.rider_update_order_status, name='rider_update_order_status'),
    path('manifest.json', views.manifest, name='manifest'),
    path('service-worker.js', views.service_worker, name='service_worker'),
]
