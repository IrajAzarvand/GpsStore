from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from apps.products.models import Category, Product
from apps.gps_devices.models import DeviceType, Protocol, Device
from apps.gps_devices.views import parse_gps_data


class DeviceTypeModelTest(TestCase):
    """Test cases for DeviceType model"""

    def test_device_type_creation(self):
        """Test creating a device type"""
        device_type = DeviceType.objects.create(
            name='Vehicle Tracker',
            slug='vehicle-tracker',
            description='GPS tracker for vehicles',
            battery_life_hours=48,
            connectivity_type='GPS, GSM',
            waterproof_rating='IP67'
        )
        self.assertEqual(device_type.name, 'Vehicle Tracker')
        self.assertEqual(str(device_type), 'Vehicle Tracker')
        self.assertTrue(device_type.is_active)

    def test_device_type_features(self):
        """Test device type features"""
        device_type = DeviceType.objects.create(
            name='Personal Tracker',
            slug='personal-tracker',
            supports_geofencing=True,
            supports_real_time_tracking=True,
            has_sos_button=True,
            has_motion_sensor=True
        )
        self.assertTrue(device_type.supports_geofencing)
        self.assertTrue(device_type.has_sos_button)


class ProtocolModelTest(TestCase):
    """Test cases for Protocol model"""

    def test_protocol_creation(self):
        """Test creating a communication protocol"""
        protocol = Protocol.objects.create(
            name='MQTT Protocol',
            protocol_type='mqtt',
            description='MQTT for real-time communication',
            default_port=1883,
            requires_authentication=True,
            supports_encryption=True,
            update_frequency_seconds=30
        )
        self.assertEqual(protocol.name, 'MQTT Protocol')
        self.assertEqual(str(protocol), 'MQTT Protocol (mqtt)')
        self.assertTrue(protocol.is_active)

    def test_protocol_message_format(self):
        """Test protocol message format storage"""
        message_format = {
            "latitude": "float",
            "longitude": "float",
            "timestamp": "datetime"
        }
        protocol = Protocol.objects.create(
            name='HTTP Protocol',
            protocol_type='http',
            message_format=message_format
        )
        self.assertEqual(protocol.message_format, message_format)


class DeviceModelTest(TestCase):
    """Test cases for Device model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.category = Category.objects.create(
            name='GPS Trackers',
            slug='gps-trackers'
        )
        self.product = Product.objects.create(
            name='GPS Tracker Pro',
            slug='gps-tracker-pro',
            category=self.category,
            price=Decimal('1000000.00'),
            stock_quantity=50
        )
        self.device_type = DeviceType.objects.create(
            name='Vehicle Tracker',
            slug='vehicle-tracker',
            battery_life_hours=48
        )
        self.protocol = Protocol.objects.create(
            name='MQTT Protocol',
            protocol_type='mqtt'
        )

    def test_device_creation(self):
        """Test creating a GPS device"""
        device = Device.objects.create(
            user=self.user,
            product=self.product,
            device_type=self.device_type,
            imei='123456789012345',
            serial_number='SN123456789',
            name='My Car Tracker',
            protocol=self.protocol
        )
        self.assertEqual(device.status, 'inactive')
        self.assertEqual(str(device), 'My Car Tracker (123456789012345)')

    def test_device_activation(self):
        """Test device activation"""
        device = Device.objects.create(
            user=self.user,
            product=self.product,
            device_type=self.device_type,
            imei='123456789012345',
            serial_number='SN123456789',
            name='My Car Tracker',
            protocol=self.protocol
        )

        device.activate()
        self.assertEqual(device.status, 'active')
        self.assertIsNotNone(device.activated_at)

    def test_device_location_update(self):
        """Test updating device location"""
        device = Device.objects.create(
            user=self.user,
            product=self.product,
            device_type=self.device_type,
            imei='123456789012345',
            serial_number='SN123456789',
            name='My Car Tracker',
            protocol=self.protocol
        )

        device.update_location(35.6892, 51.3890)
        self.assertEqual(device.last_location_lat, Decimal('35.6892'))
        self.assertEqual(device.last_location_lng, Decimal('51.3890'))
        self.assertIsNotNone(device.last_location_time)

    def test_device_subscription_status(self):
        """Test device subscription status checking"""
        device = Device.objects.create(
            user=self.user,
            product=self.product,
            device_type=self.device_type,
            imei='123456789012345',
            serial_number='SN123456789',
            name='My Car Tracker',
            protocol=self.protocol,
            status='active'
        )

        # No expiry date - should not be active
        self.assertFalse(device.is_active_subscription())

        # Set future expiry
        device.expires_at = timezone.now() + timezone.timedelta(days=30)
        device.save()
        self.assertTrue(device.is_active_subscription())

        # Set past expiry
        device.expires_at = timezone.now() - timezone.timedelta(days=1)
        device.save()
        self.assertFalse(device.is_active_subscription())

    def test_device_deactivation(self):
        """Test device deactivation"""
        device = Device.objects.create(
            user=self.user,
            product=self.product,
            device_type=self.device_type,
            imei='123456789012345',
            serial_number='SN123456789',
            name='My Car Tracker',
            protocol=self.protocol,
            status='active'
        )

        device.deactivate()
        self.assertEqual(device.status, 'inactive')

    def test_device_imei_validation(self):
        """Test IMEI validation (15 digits)"""
        # Valid IMEI
        device = Device(
            user=self.user,
            product=self.product,
            device_type=self.device_type,
            imei='123456789012345',
            serial_number='SN123456789',
            name='My Car Tracker',
            protocol=self.protocol
        )
        device.full_clean()  # Should not raise ValidationError

        # Invalid IMEI (too short)
        device_invalid = Device(
            user=self.user,
            product=self.product,
            device_type=self.device_type,
            imei='123456789',
            serial_number='SN123456789',
            name='My Car Tracker',
            protocol=self.protocol
        )
        with self.assertRaises(Exception):  # ValidationError
            device_invalid.full_clean()

    def test_device_unique_imei(self):
        """Test IMEI uniqueness"""
        Device.objects.create(
            user=self.user,
            product=self.product,
            device_type=self.device_type,
            imei='123456789012345',
            serial_number='SN123456789',
            name='My Car Tracker',
            protocol=self.protocol
        )

        # Try to create device with same IMEI - should fail
        with self.assertRaises(Exception):  # IntegrityError
            Device.objects.create(
                user=self.user,
                product=self.product,
                device_type=self.device_type,
                imei='123456789012345',
                serial_number='SN123456790',
                name='My Car Tracker 2',
                protocol=self.protocol
            )


class GPSDataParsingTest(TestCase):
    """Test cases for GPS data parsing"""

    def test_parse_valid_gps_data(self):
        """Test parsing valid GPS data with DDMM.MMMM coordinates"""
        data = "*HQ,123456789012345,V1,120000,A,2940.9263,N,05123.4567,E,50.0,180.0,201125,1,12.5,25.0,1000,ABC123#"
        parsed = parse_gps_data(data)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed['imei'], '123456789012345')
        # Latitude: 29 + 40.9263/60 ≈ 29.682105
        self.assertAlmostEqual(parsed['latitude'], 29.682105, places=5)
        # Longitude: 51 + 23.4567/60 ≈ 51.390945
        self.assertAlmostEqual(parsed['longitude'], 51.390945, places=5)
        self.assertEqual(parsed['speed'], 50.0)
        self.assertEqual(parsed['heading'], 180.0)
        self.assertEqual(parsed['unknown_sections'], {'extra_fields': ['ABC123']})

    def test_parse_gps_data_south_west(self):
        """Test parsing GPS data with south and west coordinates"""
        data = "*HQ,123456789012345,V1,120000,A,2940.9263,S,05123.4567,W,0.0,0.0,201125,1,12.5,25.0,1000#"
        parsed = parse_gps_data(data)
        self.assertIsNotNone(parsed)
        # Latitude should be negative for South
        self.assertAlmostEqual(parsed['latitude'], -29.682105, places=5)
        # Longitude should be negative for West
        self.assertAlmostEqual(parsed['longitude'], -51.390945, places=5)
        self.assertEqual(parsed['unknown_sections'], {})

    def test_parse_invalid_header(self):
        """Test parsing data with invalid header"""
        data = "*XX,123456789012345,V1,120000,A,2940.9263,N,05123.4567,E,50.0,180.0,201125,1,12.5,25.0,1000#"
        parsed = parse_gps_data(data)
        self.assertIsNone(parsed)

    def test_parse_insufficient_parts(self):
        """Test parsing data with insufficient parts"""
        data = "*HQ,123456789012345,V1,120000,A,2940.9263,N,05123.4567,E,50.0#"
        parsed = parse_gps_data(data)
        self.assertIsNone(parsed)

    def test_parse_invalid_coordinates(self):
        """Test parsing data with invalid coordinate format"""
        data = "*HQ,123456789012345,V1,120000,A,99999,N,05123.4567,E,50.0,180.0,201125,1,12.5,25.0,1000#"
        parsed = parse_gps_data(data)
        self.assertIsNone(parsed)
