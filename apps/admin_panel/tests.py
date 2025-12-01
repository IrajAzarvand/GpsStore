import pytest
from django.test import TestCase
from apps.accounts.models import User
from apps.admin_panel.models import AdminNotification, SystemSetting


class AdminNotificationModelTest(TestCase):
    """Test cases for AdminNotification model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='admin123',
            is_staff=True,
            is_superuser=True
        )

    def test_admin_notification_creation(self):
        """Test creating an admin notification"""
        notification = AdminNotification.objects.create(
            user=self.user,
            title='New Order Received',
            message='A new order has been placed by customer.',
            notification_type='order',
            action_url='/admin/orders/123/',
            metadata={'order_id': 123, 'amount': '1000000.00'}
        )
        self.assertEqual(notification.title, 'New Order Received')
        self.assertEqual(str(notification), f"New Order Received - {self.user.username}")
        self.assertFalse(notification.is_read)

    def test_admin_notification_mark_as_read(self):
        """Test marking notification as read"""
        notification = AdminNotification.objects.create(
            user=self.user,
            title='Test Notification',
            message='Test message',
            notification_type='system'
        )

        self.assertFalse(notification.is_read)
        notification.mark_as_read()
        self.assertTrue(notification.is_read)

    def test_admin_notification_types(self):
        """Test different notification types"""
        notification_types = ['order', 'payment', 'device', 'alert', 'system']

        for n_type in notification_types:
            notification = AdminNotification.objects.create(
                user=self.user,
                title=f'{n_type.title()} Notification',
                message=f'Test {n_type} notification',
                notification_type=n_type
            )
            self.assertEqual(notification.notification_type, n_type)


class SystemSettingModelTest(TestCase):
    """Test cases for SystemSetting model"""

    def test_system_setting_creation(self):
        """Test creating a system setting"""
        setting = SystemSetting.objects.create(
            key='maintenance_mode',
            value='false',
            description='Enable maintenance mode for the website',
            is_public=False
        )
        self.assertEqual(setting.key, 'maintenance_mode')
        self.assertEqual(str(setting), 'maintenance_mode')

    def test_system_setting_public_access(self):
        """Test public vs private settings"""
        public_setting = SystemSetting.objects.create(
            key='site_name',
            value='GPS Store',
            description='Website name',
            is_public=True
        )

        private_setting = SystemSetting.objects.create(
            key='secret_key',
            value='super_secret_key',
            description='Django secret key',
            is_public=False
        )

        self.assertTrue(public_setting.is_public)
        self.assertFalse(private_setting.is_public)

    def test_system_setting_uniqueness(self):
        """Test setting key uniqueness"""
        SystemSetting.objects.create(
            key='test_setting',
            value='value1'
        )

        # Should not allow duplicate keys
        with self.assertRaises(Exception):  # IntegrityError
            SystemSetting.objects.create(
                key='test_setting',
                value='value2'
            )
