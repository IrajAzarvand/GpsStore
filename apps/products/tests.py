import pytest
from django.test import TestCase
from apps.accounts.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from decimal import Decimal
from apps.products.models import Category, Product, ProductImage, Review


class CategoryModelTest(TestCase):
    """Test cases for Category model"""

    def test_category_creation(self):
        """Test creating a category"""
        category = Category.objects.create(
            name='GPS Trackers',
            slug='gps-trackers',
            description='GPS tracking devices'
        )
        self.assertEqual(category.name, 'GPS Trackers')
        self.assertEqual(str(category), 'GPS Trackers')

    def test_category_hierarchy(self):
        """Test category parent-child relationships"""
        parent = Category.objects.create(
            name='Electronics',
            slug='electronics'
        )
        child = Category.objects.create(
            name='GPS Devices',
            slug='gps-devices',
            parent=parent
        )
        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.subcategories.all())


class ProductModelTest(TestCase):
    """Test cases for Product model"""

    def setUp(self):
        self.category = Category.objects.create(
            name='GPS Trackers',
            slug='gps-trackers'
        )
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_product_creation(self):
        """Test creating a product"""
        product = Product.objects.create(
            name='GPS Tracker Pro',
            slug='gps-tracker-pro',
            description='Professional GPS tracker',
            category=self.category,
            price=Decimal('1000000.00'),
            stock_quantity=50
        )
        self.assertEqual(product.name, 'GPS Tracker Pro')
        self.assertEqual(str(product), 'GPS Tracker Pro')
        self.assertTrue(product.is_in_stock())
        self.assertEqual(product.get_discounted_price(), Decimal('1000000.00'))

    def test_product_with_discount(self):
        """Test product with discount price"""
        product = Product.objects.create(
            name='GPS Tracker Pro',
            slug='gps-tracker-pro',
            category=self.category,
            price=Decimal('1000000.00'),
            discount_price=Decimal('800000.00'),
            stock_quantity=50
        )
        self.assertEqual(product.get_discounted_price(), Decimal('800000.00'))

    def test_product_out_of_stock(self):
        """Test out of stock product"""
        product = Product.objects.create(
            name='GPS Tracker Pro',
            slug='gps-tracker-pro',
            category=self.category,
            price=Decimal('1000000.00'),
            stock_quantity=0
        )
        self.assertFalse(product.is_in_stock())

    def test_product_rating_calculation(self):
        """Test average rating calculation"""
        product = Product.objects.create(
            name='GPS Tracker Pro',
            slug='gps-tracker-pro',
            category=self.category,
            price=Decimal('1000000.00'),
            stock_quantity=50
        )

        # Create reviews
        Review.objects.create(
            product=product,
            user=self.user,
            rating=5,
            title='Great product',
            comment='Excellent GPS tracker'
        )
        Review.objects.create(
            product=product,
            user=User.objects.create_user('user2', 'user2@example.com', 'pass'),
            rating=3,
            title='Good product',
            comment='Decent GPS tracker'
        )

        self.assertEqual(product.get_average_rating(), 4.0)


class ProductImageModelTest(TestCase):
    """Test cases for ProductImage model"""

    def setUp(self):
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

    def test_product_image_creation(self):
        """Test creating a product image"""
        # Create a simple test image
        image_file = SimpleUploadedFile(
            "test_image.jpg",
            b"file_content",
            content_type="image/jpeg"
        )

        image = ProductImage.objects.create(
            product=self.product,
            image=image_file,
            alt_text='GPS Tracker Image',
            is_primary=True
        )
        self.assertEqual(str(image), f"Image for {self.product.name}")
        self.assertTrue(image.is_primary)

    def test_unique_primary_image_constraint(self):
        """Test that only one primary image per product is allowed"""
        # Create first primary image
        image_file1 = SimpleUploadedFile(
            "test_image1.jpg",
            b"file_content1",
            content_type="image/jpeg"
        )
        ProductImage.objects.create(
            product=self.product,
            image=image_file1,
            is_primary=True
        )

        # Try to create second primary image - should fail
        image_file2 = SimpleUploadedFile(
            "test_image2.jpg",
            b"file_content2",
            content_type="image/jpeg"
        )
        with self.assertRaises(Exception):  # IntegrityError
            ProductImage.objects.create(
                product=self.product,
                image=image_file2,
                is_primary=True
            )


class ReviewModelTest(TestCase):
    """Test cases for Review model"""

    def setUp(self):
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
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_review_creation(self):
        """Test creating a review"""
        review = Review.objects.create(
            product=self.product,
            user=self.user,
            rating=5,
            title='Excellent Product',
            comment='This GPS tracker works perfectly!'
        )
        self.assertEqual(review.rating, 5)
        self.assertEqual(str(review), f"Review by {self.user.username} for {self.product.name}")

    def test_unique_review_constraint(self):
        """Test that one user can only review a product once"""
        Review.objects.create(
            product=self.product,
            user=self.user,
            rating=5,
            title='Great',
            comment='Excellent'
        )

        # Try to create another review for same user-product - should fail
        with self.assertRaises(Exception):  # IntegrityError
            Review.objects.create(
                product=self.product,
                user=self.user,
                rating=4,
                title='Good',
                comment='Still good'
            )
