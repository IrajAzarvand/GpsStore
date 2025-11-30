from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from apps.gps_devices.models import Device


class SubscriptionPlan(models.Model):
    """
    Predefined subscription plans for GPS services
    """
    PLAN_TYPES = [
        ('basic', 'پایه'),
        ('premium', 'پریمیوم'),
        ('enterprise', 'سازمانی'),
    ]

    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES, default='basic')
    description = models.TextField(blank=True)

    # Pricing
    price_per_year = models.DecimalField(max_digits=10, decimal_places=2)
    price_per_month = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    # Features
    max_devices = models.PositiveIntegerField(default=1, help_text="Maximum number of devices allowed")
    storage_days = models.PositiveIntegerField(default=30, help_text="Historical data storage in days")
    real_time_updates = models.BooleanField(default=True)
    geofencing_alerts = models.BooleanField(default=True)
    sms_alerts = models.BooleanField(default=False)
    email_alerts = models.BooleanField(default=True)
    api_access = models.BooleanField(default=False)

    # Billing
    billing_cycle = models.CharField(max_length=10, choices=[('monthly', 'ماهانه'), ('yearly', 'سالانه')], default='yearly')
    trial_days = models.PositiveIntegerField(default=0, help_text="Free trial period in days")

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_plan_type_display()})"

    def get_price(self, cycle='yearly'):
        """Get price based on billing cycle"""
        if cycle == 'monthly' and self.price_per_month:
            return self.price_per_month
        return self.price_per_year

    class Meta:
        verbose_name = 'Subscription Plan'
        verbose_name_plural = 'Subscription Plans'
        ordering = ['price_per_year']


class Subscription(models.Model):
    """
    User subscriptions to GPS services
    """
    STATUS_CHOICES = [
        ('trial', 'دوره آزمایشی'),
        ('active', 'فعال'),
        ('expired', 'منقضی شده'),
        ('cancelled', 'لغو شده'),
        ('suspended', 'معلق'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE, related_name='subscriptions')

    # Subscription details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial')
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    trial_end_date = models.DateTimeField(null=True, blank=True)

    # Billing
    billing_cycle = models.CharField(max_length=10, choices=[('monthly', 'ماهانه'), ('yearly', 'سالانه')], default='yearly')
    next_billing_date = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)

    # Device associations
    devices = models.ManyToManyField(Device, related_name='subscriptions', blank=True)

    # Payment tracking
    last_payment_date = models.DateTimeField(null=True, blank=True)
    total_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s {self.plan.name} subscription"

    def activate(self):
        """Activate subscription"""
        from django.utils import timezone
        self.status = 'active'
        if not self.end_date:
            # Set end date based on billing cycle
            if self.billing_cycle == 'yearly':
                self.end_date = timezone.now() + timezone.timedelta(days=365)
            else:
                self.end_date = timezone.now() + timezone.timedelta(days=30)
        self.save()

    def renew(self):
        """Renew subscription for another billing cycle"""
        from django.utils import timezone
        if self.billing_cycle == 'yearly':
            self.end_date = self.end_date + timezone.timedelta(days=365)
            self.next_billing_date = self.end_date
        else:
            self.end_date = self.end_date + timezone.timedelta(days=30)
            self.next_billing_date = self.end_date
        self.save()

    def cancel(self):
        """Cancel subscription"""
        self.status = 'cancelled'
        self.auto_renew = False
        self.save()

    def is_active(self):
        """Check if subscription is currently active"""
        from django.utils import timezone
        return (self.status in ['trial', 'active'] and
                (not self.end_date or self.end_date > timezone.now()))

    def is_trial_active(self):
        """Check if trial period is active"""
        from django.utils import timezone
        return (self.status == 'trial' and
                self.trial_end_date and
                self.trial_end_date > timezone.now())

    def days_remaining(self):
        """Get days remaining in subscription"""
        from django.utils import timezone
        if not self.end_date:
            return 0
        remaining = self.end_date - timezone.now()
        return max(0, remaining.days)

    def can_add_device(self):
        """Check if user can add more devices"""
        return self.devices.count() < self.plan.max_devices

    class Meta:
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'
        ordering = ['-created_at']
        unique_together = ('user', 'plan')  # One subscription per user per plan


class PaymentRecord(models.Model):
    """
    Payment records for subscriptions
    """
    PAYMENT_TYPES = [
        ('subscription', 'اشتراک'),
        ('renewal', 'تمدید'),
        ('upgrade', 'ارتقا'),
    ]

    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='payments')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPES, default='subscription')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='IRR')

    # Payment details
    transaction_id = models.CharField(max_length=100, unique=True)
    payment_method = models.CharField(max_length=50, help_text="e.g., zarinpal, card_to_card")

    # Status
    is_successful = models.BooleanField(default=False)
    failure_reason = models.TextField(blank=True)

    # Dates
    payment_date = models.DateTimeField(auto_now_add=True)
    effective_date = models.DateTimeField(null=True, blank=True, help_text="When subscription was extended")

    def __str__(self):
        return f"Payment {self.transaction_id} - {self.amount} {self.currency}"

    class Meta:
        verbose_name = 'Payment Record'
        verbose_name_plural = 'Payment Records'
        ordering = ['-payment_date']
