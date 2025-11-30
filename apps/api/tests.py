import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from apps.api.models import APIKey, APILog, DeviceToken, Webhook


class APIKeyModelTest(TestCase):
    """Test cases for APIKey model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_api_key_creation(self):
        """Test creating an API key"""
        api_key = APIKey.objects.create(
            user=self.user,
            name='Mobile App Key',
            key_type='mobile_android',
            api_key='test_api_key_12345',
            api_secret='test_secret_12345',
            rate_limit_per_hour=500,
            rate_limit_per_day=5000
        )
        self.assertEqual(api_key.name, 'Mobile App Key')
        self.assertEqual(str(api_key), f"{self.user.username} - Mobile App Key (mobile_android)")
        self.assertTrue(api_key.is_active)

    def test_api_key_permissions(self):
        """Test API key permissions"""
        api_key = APIKey.objects.create(
            user=self.user,
            name='Read Only Key',
            api_key='readonly_key',
            can_read_devices=True,
            can_write_devices=False,
            can_read_tracking=True,
            can_write_tracking=False,
            can_manage_geofences=False
        )

        self.assertTrue(api_key.can_access('read_devices'))
        self.assertFalse(api_key.can_access('write_devices'))
        self.assertTrue(api_key.can_access('read_tracking'))
        self.assertFalse(api_key.can_access('write_tracking'))
        self.assertFalse(api_key.can_access('manage_geofences'))

    def test_api_key_expiry(self):
        """Test API key expiry checking"""
        # Non-expired key
        api_key = APIKey.objects.create(
            user=self.user,
            name='Valid Key',
            api_key='valid_key',
            expires_at=timezone.now() + timezone.timedelta(days=30)
        )
        self.assertFalse(api_key.is_expired())

        # Expired key
        api_key.expires_at = timezone.now() - timezone.timedelta(days=1)
        api_key.save()
        self.assertTrue(api_key.is_expired())


class APILogModelTest(TestCase):
    """Test cases for APILog model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.api_key = APIKey.objects.create(
            user=self.user,
            name='Test Key',
            api_key='test_key_123'
        )

    def test_api_log_creation(self):
        """Test creating an API log entry"""
        log = APILog.objects.create(
            api_key=self.api_key,
            user=self.user,
            method='GET',
            endpoint='/api/devices/',
            ip_address='192.168.1.100',
            status_code=200,
            response_size=1024,
            duration_ms=150
        )
        self.assertEqual(log.method, 'GET')
        self.assertEqual(log.status_code, 200)
        self.assertEqual(str(log), 'GET /api/devices/ - 200')

    def test_api_log_without_api_key(self):
        """Test API log without API key (public access)"""
        log = APILog.objects.create(
            user=self.user,
            method='POST',
            endpoint='/api/auth/login/',
            ip_address='192.168.1.101',
            status_code=201,
            duration_ms=200
        )
        self.assertIsNone(log.api_key)
        self.assertEqual(log.user, self.user)


class DeviceTokenModelTest(TestCase):
    """Test cases for DeviceToken model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_device_token_creation(self):
        """Test creating a device token for push notifications"""
        token = DeviceToken.objects.create(
            user=self.user,
            device_id='unique_device_id_123',
            token_type='fcm',
            token='fcm_token_abcdef123456',
            device_model='Samsung Galaxy S21',
            os_version='Android 12',
            app_version='1.2.3'
        )
        self.assertEqual(token.token_type, 'fcm')
        self.assertEqual(str(token), f"{self.user.username} - unique_device_id_123")
        self.assertTrue(token.is_active)

    def test_device_token_uniqueness(self):
        """Test device token uniqueness per device_id"""
        DeviceToken.objects.create(
            user=self.user,
            device_id='device_123',
            token_type='fcm',
            token='token1'
        )

        # Should not allow duplicate device_id
        with self.assertRaises(Exception):  # IntegrityError
            DeviceToken.objects.create(
                user=self.user,
                device_id='device_123',
                token_type='apns',
                token='token2'
            )


class WebhookModelTest(TestCase):
    """Test cases for Webhook model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_webhook_creation(self):
        """Test creating a webhook"""
        webhook = Webhook.objects.create(
            user=self.user,
            name='Location Updates',
            webhook_type='location_update',
            url='https://api.example.com/webhook/location',
            secret='webhook_secret_123',
            headers={'Authorization': 'Bearer token123'},
            retry_count=5,
            timeout_seconds=60
        )
        self.assertEqual(webhook.webhook_type, 'location_update')
        self.assertEqual(str(webhook), f"{self.user.username} - Location Updates")
        self.assertTrue(webhook.is_active)

    def test_webhook_types(self):
        """Test different webhook types"""
        webhook_types = [
            'location_update',
            'geofence_alert',
            'device_status',
            'subscription_update'
        ]

        for w_type in webhook_types:
            webhook = Webhook.objects.create(
                user=self.user,
                name=f'{w_type} Webhook',
                webhook_type=w_type,
                url=f'https://example.com/webhook/{w_type}',
                secret='secret123'
            )
            self.assertEqual(webhook.webhook_type, w_type)
