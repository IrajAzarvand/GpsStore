import pytest
from django.test import TestCase
from django.contrib.auth.models import User
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from decimal import Decimal
from apps.products.models import Category, Product
from apps.cart.models import Cart, CartItem


class CartModelTest(TestCase):
    """Test cases for Cart model"""

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

    def test_cart_creation_for_user(self):
        """Test creating a cart for authenticated user"""
        cart = Cart.objects.create(user=self.user)
        self.assertEqual(cart.user, self.user)
        self.assertEqual(str(cart), f"Cart for {self.user.username}")

    def test_cart_creation_for_anonymous(self):
        """Test creating a cart for anonymous user"""
        cart = Cart.objects.create(session_key='abc123')
        self.assertIsNone(cart.user)
        self.assertEqual(cart.session_key, 'abc123')
        self.assertEqual(str(cart), "Cart for Anonymous")

    def test_cart_total_price_calculation(self):
        """Test calculating total price of cart"""
        cart = Cart.objects.create(user=self.user)

        # Add items to cart
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=2
        )

        # Create another product
        product2 = Product.objects.create(
            name='GPS Tracker Basic',
            slug='gps-tracker-basic',
            category=self.category,
            price=Decimal('500000.00'),
            stock_quantity=30,
            sku='GPS-BASIC-001'
        )

        CartItem.objects.create(
            cart=cart,
            product=product2,
            quantity=1
        )

        expected_total = (Decimal('1000000.00') * 2) + Decimal('500000.00')
        self.assertEqual(cart.get_total_price(), expected_total)

    def test_cart_total_items_calculation(self):
        """Test calculating total number of items in cart"""
        cart = Cart.objects.create(user=self.user)

        CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=3
        )

        CartItem.objects.create(
            cart=cart,
            product=Product.objects.create(
                name='GPS Tracker Basic',
                slug='gps-tracker-basic',
                category=self.category,
                price=Decimal('500000.00'),
                stock_quantity=30,
                sku='GPS-BASIC-002'
            ),
            quantity=2
        )

        self.assertEqual(cart.get_total_items(), 5)

    def test_cart_clear(self):
        """Test clearing all items from cart"""
        cart = Cart.objects.create(user=self.user)

        CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=2
        )

        self.assertEqual(cart.items.count(), 1)

        cart.clear_cart()
        self.assertEqual(cart.items.count(), 0)


class CartItemModelTest(TestCase):
    """Test cases for CartItem model"""

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
        self.cart = Cart.objects.create(user=self.user)

    def test_cart_item_creation(self):
        """Test creating a cart item"""
        item = CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=2
        )
        self.assertEqual(item.quantity, 2)
        self.assertEqual(str(item), f"2 x {self.product.name}")
        self.assertEqual(item.get_total_price(), Decimal('2000000.00'))

    def test_cart_item_with_discount(self):
        """Test cart item with discounted product"""
        self.product.discount_price = Decimal('800000.00')
        self.product.save()

        item = CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=2
        )
        self.assertEqual(item.get_total_price(), Decimal('1600000.00'))

    def test_cart_item_stock_limitation(self):
        """Test that cart item quantity is limited by stock"""
        # Product has 50 stock
        item = CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=60  # More than available stock
        )
        item.save()  # Should adjust quantity to stock level
        self.assertEqual(item.quantity, 50)

    def test_unique_cart_product_constraint(self):
        """Test that same product can't be added twice to same cart"""
        CartItem.objects.create(
            cart=self.cart,
            product=self.product,
            quantity=1
        )

        # Try to add same product again - should fail
        with self.assertRaises(Exception):  # IntegrityError
            CartItem.objects.create(
                cart=self.cart,
                product=self.product,
                quantity=1
            )
