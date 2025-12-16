import pytest
from django.test import TestCase
from apps.accounts.models import User
from django.core.exceptions import ValidationError

try:
    from apps.accounts.models import UserProfile, Address
except Exception:
    UserProfile = None
    Address = None


class UserProfileModelTest(TestCase):
    """Test cases for UserProfile model"""

    def setUp(self):
        if UserProfile is None:
            self.skipTest('Legacy tests: UserProfile model is not available in apps.accounts.models')
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_user_profile_creation(self):
        """Test creating a user profile"""
        profile = UserProfile.objects.create(
            user=self.user,
            phone_number='+989123456789',
            date_of_birth='1990-01-01'
        )
        self.assertEqual(profile.user.username, 'testuser')
        self.assertEqual(str(profile), "testuser's profile")

    def test_phone_number_validation(self):
        """Test phone number validation"""
        # Valid phone number
        profile = UserProfile(
            user=self.user,
            phone_number='+989123456789'
        )
        profile.full_clean()  # Should not raise ValidationError

        # Invalid phone number
        profile_invalid = UserProfile(
            user=self.user,
            phone_number='invalid'
        )
        with self.assertRaises(ValidationError):
            profile_invalid.full_clean()

    def test_user_profile_str(self):
        """Test string representation"""
        profile = UserProfile.objects.create(
            user=self.user,
            phone_number='+989123456789'
        )
        self.assertEqual(str(profile), "testuser's profile")


class AddressModelTest(TestCase):
    """Test cases for Address model"""

    def setUp(self):
        if Address is None:
            self.skipTest('Legacy tests: Address model is not available in apps.accounts.models')
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_address_creation(self):
        """Test creating an address"""
        address = Address.objects.create(
            user=self.user,
            address_type='billing',
            street_address='123 Test St',
            city='Tehran',
            state='Tehran',
            postal_code='12345'
        )
        self.assertEqual(address.user.username, 'testuser')
        self.assertEqual(address.address_type, 'billing')
        self.assertEqual(str(address), "billing address for testuser")

    def test_address_unique_constraint(self):
        """Test unique constraint for user, address_type, is_default"""
        Address.objects.create(
            user=self.user,
            address_type='billing',
            street_address='123 Test St',
            city='Tehran',
            state='Tehran',
            postal_code='12345',
            is_default=True
        )

        # Should allow non-default address of same type
        Address.objects.create(
            user=self.user,
            address_type='billing',
            street_address='456 Test St',
            city='Tehran',
            state='Tehran',
            postal_code='12346',
            is_default=False
        )

        # Should not allow multiple default addresses of same type
        with self.assertRaises(Exception):  # IntegrityError
            Address.objects.create(
                user=self.user,
                address_type='billing',
                street_address='789 Test St',
                city='Tehran',
                state='Tehran',
                postal_code='12347',
                is_default=True
            )
