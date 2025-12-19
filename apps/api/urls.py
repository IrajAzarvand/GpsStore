from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import HealthCheckView
from .views import DeviceAssignOwnerView, DeviceAssignSubuserView
from .views import SubuserCreateView
from .viewsets import DeviceViewSet, LocationDataViewSet

router = DefaultRouter()
router.register(r'devices', DeviceViewSet, basename='device')
router.register(r'locations', LocationDataViewSet, basename='location')

urlpatterns = [
    path('v1/health/', HealthCheckView.as_view(), name='api_v1_health'),
    path('v1/auth/token/', TokenObtainPairView.as_view(), name='api_v1_token_obtain_pair'),
    path('v1/auth/token/refresh/', TokenRefreshView.as_view(), name='api_v1_token_refresh'),
    path('v1/subusers/', SubuserCreateView.as_view(), name='api_v1_subuser_create'),
    path('v1/devices/assign-owner/', DeviceAssignOwnerView.as_view(), name='api_v1_device_assign_owner'),
    path('v1/devices/assign-subuser/', DeviceAssignSubuserView.as_view(), name='api_v1_device_assign_subuser'),
    path('v1/', include(router.urls)),
]