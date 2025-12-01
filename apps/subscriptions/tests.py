import pytest
from django.test import TestCase
from apps.accounts.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from apps.products.models import Category, Product
from apps.gps_devices.models import DeviceType, Protocol, Device
from apps.subscriptions.models import SubscriptionPlan, Subscription, PaymentRecord


class SubscriptionPlanModelTest(TestCase):
    """Test cases for SubscriptionPlan model"""

    def test_subscription_plan_creation(self):
        """Test creating a subscription plan"""
        plan = SubscriptionPlan.objects.create(
            name='Premium Plan',
            plan_type='premium',
            description='Premium GPS tracking plan',
            price_per_year=Decimal('1200000.00'),
            price_per_month=Decimal('120000.00'),
            max_devices=5,
            storage_days=90,
            real_time_updates=True,
            geofencing_alerts=True,
            sms_alerts=True,
            email_alerts=True,
            api_access=True,
            trial_days=7
        )
        self.assertEqual(plan.name, 'Premium Plan')
        self.assertEqual(str(plan), "Premium Plan (پریمیوم)")
        self.assertTrue(plan.is_active)

    def test_subscription_plan_price_calculation(self):
        """Test price calculation based on billing cycle"""
        plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            price_per_year=Decimal('600000.00'),
            price_per_month=Decimal('60000.00')
        )

        self.assertEqual(plan.get_price('yearly'), Decimal('600000.00'))
        self.assertEqual(plan.get_price('monthly'), Decimal('60000.00'))
        self.assertEqual(plan.get_price(), Decimal('600000.00'))  # Default is yearly


class SubscriptionModelTest(TestCase):
    """Test cases for Subscription model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            price_per_year=Decimal('600000.00'),
            max_devices=3
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

    def test_subscription_creation(self):
        """Test creating a subscription"""
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            billing_cycle='yearly'
        )
        self.assertEqual(subscription.status, 'trial')
        self.assertEqual(str(subscription), f"{self.user.username}'s Basic Plan subscription")

    def test_subscription_activation(self):
        """Test activating a subscription"""
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan
        )

        subscription.activate()
        self.assertEqual(subscription.status, 'active')
        self.assertIsNotNone(subscription.end_date)

    def test_subscription_renewal(self):
        """Test renewing a subscription"""
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='active',
            end_date=timezone.now() + timedelta(days=30)
        )

        original_end_date = subscription.end_date
        subscription.renew()

        # Should extend by billing cycle
        expected_end_date = original_end_date + timedelta(days=365)  # yearly
        self.assertEqual(subscription.end_date, expected_end_date)

    def test_subscription_cancellation(self):
        """Test cancelling a subscription"""
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='active',
            auto_renew=True
        )

        subscription.cancel()
        self.assertEqual(subscription.status, 'cancelled')
        self.assertFalse(subscription.auto_renew)

    def test_subscription_is_active(self):
        """Test checking if subscription is active"""
        # Active subscription
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='active',
            end_date=timezone.now() + timedelta(days=30)
        )
        self.assertTrue(subscription.is_active())

        # Expired subscription
        subscription.end_date = timezone.now() - timedelta(days=1)
        subscription.save()
        self.assertFalse(subscription.is_active())

        # Trial subscription
        subscription.status = 'trial'
        subscription.trial_end_date = timezone.now() + timedelta(days=7)
        subscription.save()
        self.assertTrue(subscription.is_active())

    def test_subscription_trial_status(self):
        """Test trial period checking"""
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='trial',
            trial_end_date=timezone.now() + timedelta(days=7)
        )
        self.assertTrue(subscription.is_trial_active())

        # Expired trial
        subscription.trial_end_date = timezone.now() - timedelta(days=1)
        subscription.save()
        self.assertFalse(subscription.is_trial_active())

    def test_subscription_days_remaining(self):
        """Test calculating days remaining"""
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan,
            status='active',
            end_date=timezone.now() + timedelta(days=10)
        )
        self.assertEqual(subscription.days_remaining(), 10)

        # Expired
        subscription.end_date = timezone.now() - timedelta(days=5)
        subscription.save()
        self.assertEqual(subscription.days_remaining(), 0)

    def test_subscription_device_management(self):
        """Test device management in subscription"""
        subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan
        )

        # Create devices
        device1 = Device.objects.create(
            user=self.user,
            product=self.product,
            device_type=self.device_type,
            imei='123456789012345',
            serial_number='SN123456789',
            name='Device 1',
            protocol=self.protocol
        )
        device2 = Device.objects.create(
            user=self.user,
            product=self.product,
            device_type=self.device_type,
            imei='123456789012346',
            serial_number='SN123456790',
            name='Device 2',
            protocol=self.protocol
        )

        # Add devices to subscription
        subscription.devices.add(device1, device2)
        self.assertEqual(subscription.devices.count(), 2)

        # Check if can add more devices
        self.assertFalse(subscription.can_add_device())  # Already at max (3)

        # Remove one device
        subscription.devices.remove(device1)
        self.assertTrue(subscription.can_add_device())  # Now can add more


class PaymentRecordModelTest(TestCase):
    """Test cases for PaymentRecord model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.plan = SubscriptionPlan.objects.create(
            name='Basic Plan',
            price_per_year=Decimal('600000.00')
        )
        self.subscription = Subscription.objects.create(
            user=self.user,
            plan=self.plan
        )

    def test_payment_record_creation(self):
        """Test creating a payment record"""
        payment = PaymentRecord.objects.create(
            subscription=self.subscription,
            payment_type='subscription',
            amount=Decimal('600000.00'),
            transaction_id='TXN123456789',
            payment_method='zarinpal',
            is_successful=True
        )
        self.assertEqual(payment.amount, Decimal('600000.00'))
        self.assertEqual(str(payment), 'Payment TXN123456789 - 600000.00 IRR')
        self.assertTrue(payment.is_successful)

    def test_payment_record_types(self):
        """Test different payment types"""
        payment_types = ['subscription', 'renewal', 'upgrade']

        for p_type in payment_types:
            payment = PaymentRecord.objects.create(
                subscription=self.subscription,
                payment_type=p_type,
                amount=Decimal('600000.00'),
                transaction_id=f'TXN{p_type}123',
                is_successful=True
            )
            self.assertEqual(payment.payment_type, p_type)
