import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from apps.products.models import Category, Product
from apps.accounts.models import Address
from apps.orders.models import Order
from apps.payments.models import Payment, CardToCardTransfer, PaymentGatewayConfig


class PaymentModelTest(TestCase):
    """Test cases for Payment model"""

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
        self.address = Address.objects.create(
            user=self.user,
            address_type='shipping',
            street_address='123 Test St',
            city='Tehran',
            state='Tehran',
            postal_code='12345'
        )
        self.order = Order.objects.create(
            user=self.user,
            total_amount=Decimal('1000000.00'),
            shipping_address=self.address
        )

    def test_payment_creation(self):
        """Test creating a payment"""
        payment = Payment.objects.create(
            order=self.order,
            payment_method='zarinpal',
            amount=Decimal('1000000.00')
        )
        self.assertEqual(payment.order, self.order)
        self.assertEqual(payment.status, 'pending')
        self.assertEqual(str(payment), f"Payment for Order {self.order.order_number}")

    def test_payment_mark_completed(self):
        """Test marking payment as completed"""
        payment = Payment.objects.create(
            order=self.order,
            payment_method='zarinpal',
            amount=Decimal('1000000.00')
        )

        payment.mark_completed('TXN123456')
        self.assertEqual(payment.status, 'completed')
        self.assertEqual(payment.transaction_id, 'TXN123456')
        self.assertIsNotNone(payment.payment_date)

    def test_payment_mark_failed(self):
        """Test marking payment as failed"""
        payment = Payment.objects.create(
            order=self.order,
            payment_method='zarinpal',
            amount=Decimal('1000000.00')
        )

        payment.mark_failed()
        self.assertEqual(payment.status, 'failed')

    def test_payment_can_retry(self):
        """Test payment retry logic"""
        payment = Payment.objects.create(
            order=self.order,
            payment_method='zarinpal',
            amount=Decimal('1000000.00')
        )

        # Can retry pending payment
        self.assertTrue(payment.can_retry())

        # Can retry failed payment
        payment.status = 'failed'
        payment.save()
        self.assertTrue(payment.can_retry())

        # Cannot retry completed payment
        payment.status = 'completed'
        payment.save()
        self.assertFalse(payment.can_retry())


class CardToCardTransferModelTest(TestCase):
    """Test cases for CardToCardTransfer model"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@example.com',
            password='admin123'
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
        self.address = Address.objects.create(
            user=self.user,
            address_type='shipping',
            street_address='123 Test St',
            city='Tehran',
            state='Tehran',
            postal_code='12345'
        )
        self.order = Order.objects.create(
            user=self.user,
            total_amount=Decimal('1000000.00'),
            shipping_address=self.address
        )
        self.payment = Payment.objects.create(
            order=self.order,
            payment_method='card_to_card',
            amount=Decimal('1000000.00')
        )

    def test_card_transfer_creation(self):
        """Test creating a card to card transfer"""
        transfer = CardToCardTransfer.objects.create(
            payment=self.payment,
            payer_name='John Doe',
            payer_card_number='1234-5678-9012-3456',
            transfer_amount=Decimal('1000000.00'),
            transfer_date=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(hours=24)
        )
        self.assertEqual(transfer.status, 'pending')
        self.assertEqual(str(transfer), f"Card transfer for {self.order.order_number}")

    def test_transfer_approval(self):
        """Test approving a transfer"""
        transfer = CardToCardTransfer.objects.create(
            payment=self.payment,
            payer_name='John Doe',
            payer_card_number='1234-5678-9012-3456',
            transfer_amount=Decimal('1000000.00'),
            transfer_date=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(hours=24)
        )

        transfer.approve(self.admin)
        self.assertEqual(transfer.status, 'approved')
        self.assertEqual(transfer.verified_by, self.admin)
        self.assertEqual(self.payment.status, 'completed')

    def test_transfer_rejection(self):
        """Test rejecting a transfer"""
        transfer = CardToCardTransfer.objects.create(
            payment=self.payment,
            payer_name='John Doe',
            payer_card_number='1234-5678-9012-3456',
            transfer_amount=Decimal('1000000.00'),
            transfer_date=timezone.now(),
            expires_at=timezone.now() + timezone.timedelta(hours=24)
        )

        transfer.reject(self.admin, 'Invalid transfer')
        self.assertEqual(transfer.status, 'rejected')
        self.assertEqual(transfer.verified_by, self.admin)
        self.assertEqual(transfer.admin_notes, 'Invalid transfer')
        self.assertEqual(self.payment.status, 'failed')

    def test_transfer_expiry_check(self):
        """Test checking if transfer is expired"""
        future_date = timezone.now() + timezone.timedelta(days=1)
        transfer = CardToCardTransfer.objects.create(
            payment=self.payment,
            payer_name='John Doe',
            payer_card_number='1234-5678-9012-3456',
            transfer_amount=Decimal('1000000.00'),
            transfer_date=timezone.now(),
            expires_at=future_date
        )

        self.assertFalse(transfer.is_expired())

        # Set expiry to past
        transfer.expires_at = timezone.now() - timezone.timedelta(hours=1)
        transfer.save()
        self.assertTrue(transfer.is_expired())


class PaymentGatewayConfigModelTest(TestCase):
    """Test cases for PaymentGatewayConfig model"""

    def test_gateway_config_creation(self):
        """Test creating a payment gateway configuration"""
        config = PaymentGatewayConfig.objects.create(
            name='Zarinpal Test',
            gateway_type='zarinpal',
            merchant_id='test_merchant_123',
            api_key='test_api_key',
            min_amount=Decimal('1000.00'),
            max_amount=Decimal('50000000.00')
        )
        self.assertEqual(config.name, 'Zarinpal Test')
        self.assertEqual(str(config), 'Zarinpal Test (zarinpal)')
        self.assertTrue(config.is_active)

    def test_gateway_config_limits(self):
        """Test gateway amount limits"""
        config = PaymentGatewayConfig.objects.create(
            name='Test Gateway',
            gateway_type='zarinpal',
            min_amount=Decimal('10000.00'),
            max_amount=Decimal('1000000.00')
        )

        # Should be within limits
        self.assertGreaterEqual(Decimal('50000.00'), config.min_amount)
        self.assertLessEqual(Decimal('50000.00'), config.max_amount)
