import pytest
from django.test import TestCase
from apps.accounts.models import User
from django.utils import timezone
from decimal import Decimal
from apps.products.models import Category, Product
from apps.gps_devices.models import DeviceType, Protocol, Device
from apps.tracking.models import LocationData, Geofence, Alert


class LocationDataModelTest(TestCase):
    """Test cases for LocationData model"""

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
            slug='vehicle-tracker'
        )
        self.protocol = Protocol.objects.create(
            name='MQTT Protocol',
            protocol_type='mqtt'
        )
        self.device = Device.objects.create(
            user=self.user,
            product=self.product,
            device_type=self.device_type,
            imei='123456789012345',
            serial_number='SN123456789',
            name='My Car Tracker',
            protocol=self.protocol
        )

    def test_location_data_creation(self):
        """Test creating location data"""
        location = LocationData.objects.create(
            device=self.device,
            latitude=Decimal('35.6892'),
            longitude=Decimal('51.3890'),
            altitude=Decimal('100.5'),
            speed=Decimal('50.0'),
            heading=Decimal('90.0'),
            accuracy=Decimal('5.0'),
            battery_level=85,
            signal_strength=80
        )
        self.assertEqual(location.device, self.device)
        self.assertEqual(str(location), f"{self.device.name} at (35.6892, 51.3890)")

    def test_location_data_validation(self):
        """Test latitude and longitude validation"""
        # Valid coordinates
        location = LocationData(
            device=self.device,
            latitude=Decimal('35.6892'),
            longitude=Decimal('51.3890')
        )
        location.full_clean()  # Should not raise ValidationError

        # Invalid latitude (out of range)
        location_invalid_lat = LocationData(
            device=self.device,
            latitude=Decimal('95.6892'),  # > 90
            longitude=Decimal('51.3890')
        )
        with self.assertRaises(Exception):  # ValidationError
            location_invalid_lat.full_clean()

        # Invalid longitude (out of range)
        location_invalid_lng = LocationData(
            device=self.device,
            latitude=Decimal('35.6892'),
            longitude=Decimal('181.3890')  # > 180
        )
        with self.assertRaises(Exception):  # ValidationError
            location_invalid_lng.full_clean()


class GeofenceModelTest(TestCase):
    """Test cases for Geofence model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_circle_geofence_creation(self):
        """Test creating a circle geofence"""
        geofence = Geofence.objects.create(
            user=self.user,
            name='Home Zone',
            description='Home safety zone',
            shape='circle',
            center_lat=Decimal('35.6892'),
            center_lng=Decimal('51.3890'),
            radius=Decimal('1000.0'),  # 1km radius
            alert_on_enter=True,
            alert_on_exit=True
        )
        self.assertEqual(geofence.shape, 'circle')
        self.assertEqual(str(geofence), 'Home Zone (circle)')

    def test_polygon_geofence_creation(self):
        """Test creating a polygon geofence"""
        polygon_points = [
            [35.6892, 51.3890],
            [35.7000, 51.4000],
            [35.6800, 51.4100],
            [35.6892, 51.3890]  # Close the polygon
        ]
        geofence = Geofence.objects.create(
            user=self.user,
            name='Complex Zone',
            shape='polygon',
            polygon_points=polygon_points
        )
        self.assertEqual(geofence.shape, 'polygon')

    def test_point_in_circle_geofence(self):
        """Test checking if point is inside circle geofence"""
        geofence = Geofence.objects.create(
            user=self.user,
            name='Home Zone',
            shape='circle',
            center_lat=Decimal('35.6892'),
            center_lng=Decimal('51.3890'),
            radius=Decimal('1000.0')  # 1km radius
        )

        # Point inside circle (very close to center)
        self.assertTrue(geofence.contains_point(35.6892, 51.3890))

        # Point outside circle (far away)
        self.assertFalse(geofence.contains_point(35.8000, 51.5000))

    def test_point_in_polygon_geofence(self):
        """Test checking if point is inside polygon geofence"""
        polygon_points = [
            [35.6800, 51.3800],
            [35.7000, 51.3800],
            [35.7000, 51.4000],
            [35.6800, 51.4000],
            [35.6800, 51.3800]  # Close the polygon
        ]
        geofence = Geofence.objects.create(
            user=self.user,
            name='Rectangle Zone',
            shape='polygon',
            polygon_points=polygon_points
        )

        # Point inside polygon (using correct winding order)
        self.assertTrue(geofence.contains_point(35.6900, 51.3900))

        # Point outside polygon
        self.assertFalse(geofence.contains_point(35.7500, 51.4500))


class AlertModelTest(TestCase):
    """Test cases for Alert model"""

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
            slug='vehicle-tracker'
        )
        self.protocol = Protocol.objects.create(
            name='MQTT Protocol',
            protocol_type='mqtt'
        )
        self.device = Device.objects.create(
            user=self.user,
            product=self.product,
            device_type=self.device_type,
            imei='123456789012345',
            serial_number='SN123456789',
            name='My Car Tracker',
            protocol=self.protocol
        )
        self.location = LocationData.objects.create(
            device=self.device,
            latitude=Decimal('35.6892'),
            longitude=Decimal('51.3890')
        )

    def test_alert_creation(self):
        """Test creating an alert"""
        alert = Alert.objects.create(
            device=self.device,
            alert_type='geofence_enter',
            message='Device entered geofence zone',
            location_data=self.location,
            severity='high'
        )
        self.assertEqual(alert.alert_type, 'geofence_enter')
        self.assertEqual(str(alert), f"{self.device.name}: ورود به منطقه محدود")
        self.assertFalse(alert.is_read)
        self.assertFalse(alert.is_resolved)

    def test_alert_resolve(self):
        """Test resolving an alert"""
        alert = Alert.objects.create(
            device=self.device,
            alert_type='low_battery',
            message='Battery level is low',
            severity='medium'
        )

        alert.resolve()
        self.assertTrue(alert.is_resolved)
        self.assertIsNotNone(alert.resolved_at)

    def test_alert_types(self):
        """Test different alert types"""
        alert_types = [
            'geofence_enter',
            'geofence_exit',
            'low_battery',
            'device_offline',
            'sos_button',
            'speed_limit'
        ]

        for alert_type in alert_types:
            alert = Alert.objects.create(
                device=self.device,
                alert_type=alert_type,
                message=f'Test {alert_type} alert'
            )
            self.assertEqual(alert.alert_type, alert_type)
