from django.urls import path, include
from rest_framework import routers
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework import permissions
from apps.api import views
from apps.api.viewsets import ProtocolHandlerViewSet

# Create a router and register our viewsets with it
router = routers.DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'profiles', views.UserProfileViewSet)
router.register(r'addresses', views.AddressViewSet)
router.register(r'categories', views.CategoryViewSet)
router.register(r'products', views.ProductViewSet)
router.register(r'product-images', views.ProductImageViewSet)
router.register(r'reviews', views.ReviewViewSet)
router.register(r'carts', views.CartViewSet)
router.register(r'cart-items', views.CartItemViewSet)
router.register(r'orders', views.OrderViewSet)
router.register(r'order-items', views.OrderItemViewSet)
router.register(r'shipping-methods', views.ShippingMethodViewSet)
router.register(r'payments', views.PaymentViewSet)
router.register(r'card-transfers', views.CardToCardTransferViewSet)
router.register(r'payment-gateways', views.PaymentGatewayConfigViewSet)
router.register(r'device-types', views.DeviceTypeViewSet)
router.register(r'protocols', views.ProtocolViewSet)
router.register(r'devices', views.DeviceViewSet)
router.register(r'location-data', views.LocationDataViewSet)
router.register(r'geofences', views.GeofenceViewSet)
router.register(r'alerts', views.AlertViewSet)
router.register(r'subscription-plans', views.SubscriptionPlanViewSet)
router.register(r'subscriptions', views.SubscriptionViewSet)
router.register(r'payment-records', views.PaymentRecordViewSet)
router.register(r'protocol-handlers', ProtocolHandlerViewSet, basename='protocol-handler')

# Schema view for Swagger/OpenAPI documentation
schema_view = get_schema_view(
    openapi.Info(
        title="GPS Store API",
        default_version='v1',
        description="API documentation for GPS Store application",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@gpsstore.local"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

# URL patterns
urlpatterns = [
    # JWT token endpoints
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Swagger/OpenAPI documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),

    # API router URLs
    path('', include(router.urls)),

    # Cart current endpoint
    path('cart/current/', views.CartViewSet.as_view({'get': 'current'}), name='cart-current'),
    path('protocols/create/', views.ProtocolCreateView.as_view(), name='protocol-create'),
    path('protocols/<int:pk>/update/', views.ProtocolUpdateView.as_view(), name='protocol-update'),
]