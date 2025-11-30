from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from apps.api.serializers import (
    UserSerializer, UserProfileSerializer, AddressSerializer,
    CategorySerializer, ProductSerializer, ProductImageSerializer, ReviewSerializer,
    CartSerializer, CartItemSerializer,
    OrderSerializer, OrderItemSerializer, ShippingMethodSerializer,
    PaymentSerializer, CardToCardTransferSerializer, PaymentGatewayConfigSerializer,
    DeviceTypeSerializer, ProtocolSerializer, DeviceSerializer,
    LocationDataSerializer, GeofenceSerializer, AlertSerializer,
    SubscriptionPlanSerializer, SubscriptionSerializer, PaymentRecordSerializer
)
from apps.accounts.models import UserProfile, Address
from apps.products.models import Category, Product, ProductImage, Review
from apps.cart.models import Cart, CartItem
from apps.orders.models import Order, OrderItem, ShippingMethod
from apps.payments.models import Payment, CardToCardTransfer, PaymentGatewayConfig
from apps.gps_devices.models import DeviceType, Protocol, Device
from apps.tracking.models import LocationData, Geofence, Alert
from apps.subscriptions.models import SubscriptionPlan, Subscription, PaymentRecord


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet for User model"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['date_joined', 'username']

    def get_permissions(self):
        if self.action in ['create', 'login']:
            return [permissions.AllowAny()]
        return super().get_permissions()

    @action(detail=False, methods=['post'])
    def login(self, request):
        """Custom login endpoint"""
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({'error': 'Username and password are required'},
                          status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': UserSerializer(user).data
            })
        return Response({'error': 'Invalid credentials'},
                       status=status.HTTP_401_UNAUTHORIZED)


class UserProfileViewSet(viewsets.ModelViewSet):
    """ViewSet for UserProfile model"""
    queryset = UserProfile.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return UserProfile.objects.filter(user=self.request.user)


class AddressViewSet(viewsets.ModelViewSet):
    """ViewSet for Address model"""
    queryset = Address.objects.all()
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Category model"""
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['parent', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Product model"""
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['category', 'is_featured', 'is_active', 'stock_quantity']
    search_fields = ['name', 'description', 'sku']
    ordering_fields = ['price', 'created_at', 'name']


class ProductImageViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for ProductImage model"""
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    permission_classes = [permissions.AllowAny]


class ReviewViewSet(viewsets.ModelViewSet):
    """ViewSet for Review model"""
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['product', 'rating', 'is_verified_purchase']
    search_fields = ['title', 'comment']
    ordering_fields = ['created_at', 'rating']

    def get_queryset(self):
        return Review.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class CartViewSet(viewsets.ModelViewSet):
    """ViewSet for Cart model"""
    serializer_class = CartSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Cart.objects.all()

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)

    def get_or_create_cart(self):
        """Get or create cart for current user"""
        cart, created = Cart.objects.get_or_create(user=self.request.user)
        return cart

    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current user's cart"""
        cart = self.get_or_create_cart()
        serializer = self.get_serializer(cart)
        return Response(serializer.data)


class CartItemViewSet(viewsets.ModelViewSet):
    """ViewSet for CartItem model"""
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = CartItem.objects.all()

    def get_queryset(self):
        return CartItem.objects.filter(cart__user=self.request.user)

    def perform_create(self, serializer):
        cart = Cart.objects.get_or_create(user=self.request.user)[0]
        serializer.save(cart=cart)


class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet for Order model"""
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Order.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'created_at']
    search_fields = ['order_number']
    ordering_fields = ['created_at', 'total_amount']

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class OrderItemViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for OrderItem model"""
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return OrderItem.objects.filter(order__user=self.request.user)


class ShippingMethodViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for ShippingMethod model"""
    queryset = ShippingMethod.objects.filter(is_active=True)
    serializer_class = ShippingMethodSerializer
    permission_classes = [permissions.AllowAny]


class PaymentViewSet(viewsets.ModelViewSet):
    """ViewSet for Payment model"""
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Payment.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'payment_method']
    search_fields = ['transaction_id', 'order__order_number']
    ordering_fields = ['created_at', 'amount']

    def get_queryset(self):
        return Payment.objects.filter(order__user=self.request.user)


class CardToCardTransferViewSet(viewsets.ModelViewSet):
    """ViewSet for CardToCardTransfer model"""
    serializer_class = CardToCardTransferSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = CardToCardTransfer.objects.all()

    def get_queryset(self):
        return CardToCardTransfer.objects.filter(payment__order__user=self.request.user)


class PaymentGatewayConfigViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for PaymentGatewayConfig model"""
    queryset = PaymentGatewayConfig.objects.filter(is_active=True)
    serializer_class = PaymentGatewayConfigSerializer
    permission_classes = [permissions.AllowAny]


class DeviceTypeViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for DeviceType model"""
    queryset = DeviceType.objects.filter(is_active=True)
    serializer_class = DeviceTypeSerializer
    permission_classes = [permissions.AllowAny]


class ProtocolViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for Protocol model"""
    queryset = Protocol.objects.filter(is_active=True)
    serializer_class = ProtocolSerializer
    permission_classes = [permissions.AllowAny]


class DeviceViewSet(viewsets.ModelViewSet):
    """ViewSet for Device model"""
    serializer_class = DeviceSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Device.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'device_type', 'protocol']
    search_fields = ['name', 'imei', 'device_id', 'serial_number']
    ordering_fields = ['created_at', 'name']

    def get_queryset(self):
        return Device.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class LocationDataViewSet(viewsets.ModelViewSet):
    """ViewSet for LocationData model"""
    serializer_class = LocationDataSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = LocationData.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['device', 'timestamp']
    search_fields = ['address']
    ordering_fields = ['timestamp', 'received_at']

    def get_queryset(self):
        return LocationData.objects.filter(device__user=self.request.user)


class GeofenceViewSet(viewsets.ModelViewSet):
    """ViewSet for Geofence model"""
    serializer_class = GeofenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Geofence.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['shape', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'name']

    def get_queryset(self):
        return Geofence.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class AlertViewSet(viewsets.ModelViewSet):
    """ViewSet for Alert model"""
    serializer_class = AlertSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Alert.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['alert_type', 'severity', 'is_read', 'is_resolved']
    search_fields = ['message']
    ordering_fields = ['created_at', 'severity']

    def get_queryset(self):
        return Alert.objects.filter(device__user=self.request.user)


class SubscriptionPlanViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for SubscriptionPlan model"""
    queryset = SubscriptionPlan.objects.filter(is_active=True)
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['plan_type', 'billing_cycle']
    search_fields = ['name', 'description']
    ordering_fields = ['price_per_year', 'name']


class SubscriptionViewSet(viewsets.ModelViewSet):
    """ViewSet for Subscription model"""
    serializer_class = SubscriptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Subscription.objects.all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'plan', 'billing_cycle']
    search_fields = ['plan__name']
    ordering_fields = ['created_at', 'end_date']

    def get_queryset(self):
        return Subscription.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PaymentRecordViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for PaymentRecord model"""
    serializer_class = PaymentRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = PaymentRecord.objects.all()

    def get_queryset(self):
        return PaymentRecord.objects.filter(subscription__user=self.request.user)


class ProtocolCreateView(generics.CreateAPIView):
    """View for creating new protocols"""
    queryset = Protocol.objects.all()
    serializer_class = ProtocolSerializer
    permission_classes = [permissions.IsAdminUser]


class ProtocolUpdateView(generics.UpdateAPIView):
    """View for updating existing protocols"""
    queryset = Protocol.objects.all()
    serializer_class = ProtocolSerializer
    permission_classes = [permissions.IsAdminUser]
