import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
from apps.products.models import Category, Product
from apps.accounts.models import Address
from apps.orders.models import Order, OrderItem, ShippingMethod


class OrderModelTest(TestCase):
    """Test cases for Order model"""

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

    def test_order_creation(self):
        """Test creating an order"""
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal('1000000.00'),
            shipping_address=self.address,
            billing_address=self.address,
            shipping_cost=Decimal('50000.00')
        )
        self.assertEqual(order.user, self.user)
        self.assertEqual(order.status, 'pending')
        self.assertTrue(order.order_number.startswith('ORD') or order.order_number == 'TEMP')
        self.assertEqual(str(order), f"Order {order.order_number}")

    def test_order_total_with_shipping(self):
        """Test calculating total with shipping"""
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal('1000000.00'),
            shipping_address=self.address,
            shipping_cost=Decimal('50000.00'),
            tax_amount=Decimal('100000.00')
        )
        expected_total = Decimal('1000000.00') + Decimal('50000.00')
        self.assertEqual(order.get_total_with_shipping(), expected_total)

    def test_order_final_total(self):
        """Test calculating final total with all costs"""
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal('1000000.00'),
            shipping_address=self.address,
            shipping_cost=Decimal('50000.00'),
            discount_amount=Decimal('100000.00'),
            tax_amount=Decimal('100000.00')
        )
        expected_final = (Decimal('1000000.00') + Decimal('50000.00') -
                         Decimal('100000.00') + Decimal('100000.00'))
        self.assertEqual(order.get_final_total(), expected_final)

    def test_order_status_methods(self):
        """Test order status checking methods"""
        order = Order.objects.create(
            user=self.user,
            total_amount=Decimal('1000000.00'),
            shipping_address=self.address
        )

        # Test can_cancel
        self.assertTrue(order.can_cancel())
        order.status = 'confirmed'
        order.save()
        self.assertTrue(order.can_cancel())
        order.status = 'shipped'
        order.save()
        self.assertFalse(order.can_cancel())

        # Test can_ship
        order.status = 'confirmed'
        order.save()
        self.assertTrue(order.can_ship())
        order.status = 'pending'
        order.save()
        self.assertFalse(order.can_ship())


class OrderItemModelTest(TestCase):
    """Test cases for OrderItem model"""

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
            total_amount=Decimal('2000000.00'),
            shipping_address=self.address
        )

    def test_order_item_creation(self):
        """Test creating an order item"""
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price=Decimal('1000000.00')
        )
        self.assertEqual(item.quantity, 2)
        self.assertEqual(str(item), f"2 x {self.product.name} in Order {self.order.order_number}")
        self.assertEqual(item.get_total_price(), Decimal('2000000.00'))

    def test_order_item_with_discount(self):
        """Test order item with discount"""
        item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price=Decimal('1000000.00'),
            discount=Decimal('100000.00')
        )
        # (price - discount) * quantity = (1000000 - 100000) * 2 = 1800000
        self.assertEqual(item.get_total_price(), Decimal('1800000.00'))


class ShippingMethodModelTest(TestCase):
    """Test cases for ShippingMethod model"""

    def test_shipping_method_creation(self):
        """Test creating a shipping method"""
        method = ShippingMethod.objects.create(
            name='Standard Shipping',
            description='Delivery within 3-5 business days',
            cost=Decimal('50000.00'),
            estimated_days=5
        )
        self.assertEqual(method.name, 'Standard Shipping')
        self.assertEqual(str(method), 'Standard Shipping')
        self.assertTrue(method.is_active)

    def test_shipping_method_ordering(self):
        """Test shipping methods are ordered by sort_order"""
        method1 = ShippingMethod.objects.create(
            name='Express',
            cost=Decimal('100000.00'),
            estimated_days=1,
            sort_order=1
        )
        method2 = ShippingMethod.objects.create(
            name='Standard',
            cost=Decimal('50000.00'),
            estimated_days=3,
            sort_order=2
        )

        methods = list(ShippingMethod.objects.all())
        self.assertEqual(methods[0], method1)
        self.assertEqual(methods[1], method2)
