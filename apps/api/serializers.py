from rest_framework import serializers
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from apps.accounts.models import UserProfile, Address
from apps.products.models import Category, Product, ProductImage, Review
from apps.cart.models import Cart, CartItem
from apps.orders.models import Order, OrderItem, ShippingMethod
from apps.payments.models import Payment, CardToCardTransfer, PaymentGatewayConfig
from apps.gps_devices.models import DeviceType, Protocol, Device
from apps.tracking.models import LocationData, Geofence, Alert
from apps.subscriptions.models import SubscriptionPlan, Subscription, PaymentRecord


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    password2 = serializers.CharField(write_only=True, required=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'password', 'password2', 'date_joined')
        read_only_fields = ('id', 'date_joined')

    def validate(self, attrs):
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for UserProfile model"""
    user = UserSerializer(read_only=True)

    class Meta:
        model = UserProfile
        fields = '__all__'


class AddressSerializer(serializers.ModelSerializer):
    """Serializer for Address model"""
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Address
        fields = '__all__'


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model"""
    subcategories = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = '__all__'

    def get_subcategories(self, obj):
        if obj.subcategories.exists():
            return CategorySerializer(obj.subcategories.all(), many=True).data
        return []


class ProductImageSerializer(serializers.ModelSerializer):
    """Serializer for ProductImage model"""

    class Meta:
        model = ProductImage
        fields = '__all__'


class ReviewSerializer(serializers.ModelSerializer):
    """Serializer for Review model"""
    user = serializers.StringRelatedField(read_only=True)
    product = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Review
        fields = '__all__'


class ProductSerializer(serializers.ModelSerializer):
    """Serializer for Product model"""
    category = CategorySerializer(read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    reviews = ReviewSerializer(many=True, read_only=True)
    average_rating = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = '__all__'


class CartItemSerializer(serializers.ModelSerializer):
    """Serializer for CartItem model"""
    product = ProductSerializer(read_only=True)
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = '__all__'


class CartSerializer(serializers.ModelSerializer):
    """Serializer for Cart model"""
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.ReadOnlyField()
    total_items = serializers.ReadOnlyField()

    class Meta:
        model = Cart
        fields = '__all__'


class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for OrderItem model"""
    product = ProductSerializer(read_only=True)
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = OrderItem
        fields = '__all__'


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for Order model"""
    items = OrderItemSerializer(many=True, read_only=True)
    user = serializers.StringRelatedField(read_only=True)
    shipping_address = AddressSerializer(read_only=True)
    billing_address = AddressSerializer(read_only=True)
    final_total = serializers.ReadOnlyField()

    class Meta:
        model = Order
        fields = '__all__'


class ShippingMethodSerializer(serializers.ModelSerializer):
    """Serializer for ShippingMethod model"""

    class Meta:
        model = ShippingMethod
        fields = '__all__'


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model"""
    order = OrderSerializer(read_only=True)

    class Meta:
        model = Payment
        fields = '__all__'


class CardToCardTransferSerializer(serializers.ModelSerializer):
    """Serializer for CardToCardTransfer model"""
    payment = PaymentSerializer(read_only=True)

    class Meta:
        model = CardToCardTransfer
        fields = '__all__'


class PaymentGatewayConfigSerializer(serializers.ModelSerializer):
    """Serializer for PaymentGatewayConfig model"""

    class Meta:
        model = PaymentGatewayConfig
        fields = '__all__'


class DeviceTypeSerializer(serializers.ModelSerializer):
    """Serializer for DeviceType model"""

    class Meta:
        model = DeviceType
        fields = '__all__'


class ProtocolSerializer(serializers.ModelSerializer):
    """Serializer for Protocol model"""

    class Meta:
        model = Protocol
        fields = '__all__'


class DeviceSerializer(serializers.ModelSerializer):
    """Serializer for Device model"""
    user = serializers.StringRelatedField(read_only=True)
    product = ProductSerializer(read_only=True)
    device_type = DeviceTypeSerializer(read_only=True)
    protocol = ProtocolSerializer(read_only=True)

    class Meta:
        model = Device
        fields = '__all__'


class LocationDataSerializer(serializers.ModelSerializer):
    """Serializer for LocationData model"""
    device = DeviceSerializer(read_only=True)

    class Meta:
        model = LocationData
        fields = '__all__'


class GeofenceSerializer(serializers.ModelSerializer):
    """Serializer for Geofence model"""
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Geofence
        fields = '__all__'


class AlertSerializer(serializers.ModelSerializer):
    """Serializer for Alert model"""
    device = DeviceSerializer(read_only=True)
    location_data = LocationDataSerializer(read_only=True)

    class Meta:
        model = Alert
        fields = '__all__'


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    """Serializer for SubscriptionPlan model"""

    class Meta:
        model = SubscriptionPlan
        fields = '__all__'


class SubscriptionSerializer(serializers.ModelSerializer):
    """Serializer for Subscription model"""
    user = serializers.StringRelatedField(read_only=True)
    plan = SubscriptionPlanSerializer(read_only=True)
    devices = DeviceSerializer(many=True, read_only=True)
    days_remaining = serializers.ReadOnlyField()

    class Meta:
        model = Subscription
        fields = '__all__'


class PaymentRecordSerializer(serializers.ModelSerializer):
    """Serializer for PaymentRecord model"""
    subscription = SubscriptionSerializer(read_only=True)

    class Meta:
        model = PaymentRecord
        fields = '__all__'