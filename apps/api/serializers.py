from rest_framework import serializers
from apps.accounts.models import User, UserDevice, generate_unique_subuser_username
from apps.gps_devices.models import State, Model, Device, LocationData, DeviceState, RawGpsData
from apps.api.models import ApiKey

class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model"""
    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'phone', 'date_joined')
        read_only_fields = ('id', 'date_joined')

class SubuserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(required=False, allow_blank=True, default='')
    last_name = serializers.CharField(required=False, allow_blank=True, default='')
    email = serializers.EmailField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        owner = self.context.get('owner')
        if not owner or not getattr(owner, 'id', None):
            raise serializers.ValidationError('owner_required')
        if getattr(owner, 'is_subuser_of_id', None):
            raise serializers.ValidationError('forbidden')
        return attrs

    def create(self, validated_data):
        owner = self.context['owner']

        requested_username = (validated_data.get('username') or '').strip()
        password = validated_data.get('password') or ''
        first_name = (validated_data.get('first_name') or '').strip()
        last_name = (validated_data.get('last_name') or '').strip()
        email = (validated_data.get('email') or '').strip()

        if not requested_username or not password:
            raise serializers.ValidationError('username_and_password_required')

        subuser = None
        last_username = None
        for _ in range(5):
            last_username = generate_unique_subuser_username(owner, requested_username)
            try:
                subuser = User.objects.create_user(
                    username=last_username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    is_active=True,
                )
                break
            except Exception:
                subuser = None

        if subuser is None:
            raise serializers.ValidationError('username_exists')

        subuser.is_subuser_of = owner
        subuser.save(update_fields=['is_subuser_of'])
        return subuser

class StateSerializer(serializers.ModelSerializer):
    """Serializer for State model"""
    class Meta:
        model = State
        fields = '__all__'

class ModelSerializer(serializers.ModelSerializer):
    """Serializer for Device Model"""
    class Meta:
        model = Model
        fields = '__all__'
class DeviceSerializer(serializers.ModelSerializer):
    """Serializer for Device model"""
    owner = UserSerializer(read_only=True)
    model = ModelSerializer(read_only=True)
    
    class Meta:
        model = Device
        fields = '__all__'
class LocationDataSerializer(serializers.ModelSerializer):
    """Serializer for LocationData model"""
    device = DeviceSerializer(read_only=True)
    
    class Meta:
        model = LocationData
        fields = '__all__'
class DeviceStateSerializer(serializers.ModelSerializer):
    """Serializer for DeviceState model"""
    device = DeviceSerializer(read_only=True)
    state = StateSerializer(read_only=True)
    location_data = LocationDataSerializer(read_only=True)
    
    class Meta:
        model = DeviceState
        fields = '__all__'
class RawGpsDataSerializer(serializers.ModelSerializer):
    """Serializer for RawGpsData model"""
    class Meta:
        model = RawGpsData
        fields = '__all__'
class UserDeviceSerializer(serializers.ModelSerializer):
    """Serializer for UserDevice model"""
    user = UserSerializer(read_only=True)
    device = DeviceSerializer(read_only=True)
    
    class Meta:
        model = UserDevice
        fields = '__all__'
class ApiKeySerializer(serializers.ModelSerializer):
    """Serializer for ApiKey model"""
    class Meta:
        model = ApiKey
        fields = '__all__'
        extra_kwargs = {'api_key': {'write_only': True}}

    if False:
        """Serializer for PaymentRecord model"""
        subscription = SubscriptionSerializer(read_only=True)

        class Meta:
            model = PaymentRecord
            fields = '__all__'