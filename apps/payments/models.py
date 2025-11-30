from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from apps.orders.models import Order


class Payment(models.Model):
    """
    Payment transactions for orders
    """
    PAYMENT_METHODS = [
        ('zarinpal', 'زرین‌پال'),
        ('mellat', 'بانک ملت'),
        ('saderat', 'بانک صادرات'),
        ('parsian', 'بانک پارسیان'),
        ('card_to_card', 'کارت به کارت'),
    ]

    STATUS_CHOICES = [
        ('pending', 'در انتظار پرداخت'),
        ('completed', 'تکمیل شده'),
        ('failed', 'ناموفق'),
        ('refunded', 'بازپرداخت شده'),
        ('cancelled', 'لغو شده'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    transaction_id = models.CharField(max_length=100, unique=True, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_date = models.DateTimeField(null=True, blank=True)

    # Gateway-specific fields
    zarinpal_authority = models.CharField(max_length=100, blank=True, null=True)
    bank_token = models.CharField(max_length=100, blank=True, null=True)
    ref_id = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment for Order {self.order.order_number}"

    def mark_completed(self, transaction_id=None):
        """Mark payment as completed"""
        self.status = 'completed'
        self.payment_date = models.functions.Now()
        if transaction_id:
            self.transaction_id = transaction_id
        self.save()

    def mark_failed(self):
        """Mark payment as failed"""
        self.status = 'failed'
        self.save()

    def can_retry(self):
        """Check if payment can be retried"""
        return self.status in ['pending', 'failed']

    class Meta:
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'


class CardToCardTransfer(models.Model):
    """
    Manual card-to-card transfers for verification
    """
    STATUS_CHOICES = [
        ('pending', 'در انتظار تأیید'),
        ('approved', 'تأیید شده'),
        ('rejected', 'رد شده'),
        ('expired', 'منقضی شده'),
    ]

    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name='card_transfer')
    payer_name = models.CharField(max_length=100)
    payer_card_number = models.CharField(
        max_length=19,
        validators=[RegexValidator(regex=r'^\d{4}-\d{4}-\d{4}-\d{4}$', message="Card number must be in format: XXXX-XXXX-XXXX-XXXX")]
    )
    transfer_amount = models.DecimalField(max_digits=10, decimal_places=2)
    transfer_date = models.DateTimeField()
    description = models.TextField(blank=True)
    receipt_image = models.ImageField(upload_to='card_transfers/', null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    admin_notes = models.TextField(blank=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_transfers')
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"Card transfer for {self.payment.order.order_number}"

    def approve(self, admin_user):
        """Approve the transfer"""
        self.status = 'approved'
        self.verified_by = admin_user
        self.verified_at = models.functions.Now()
        self.save()
        self.payment.mark_completed()

    def reject(self, admin_user, notes=''):
        """Reject the transfer"""
        self.status = 'rejected'
        self.verified_by = admin_user
        self.verified_at = models.functions.Now()
        self.admin_notes = notes
        self.save()
        self.payment.mark_failed()

    def is_expired(self):
        """Check if transfer has expired"""
        from django.utils import timezone
        return timezone.now() > self.expires_at

    class Meta:
        verbose_name = 'Card to Card Transfer'
        verbose_name_plural = 'Card to Card Transfers'
        ordering = ['-created_at']


class PaymentGatewayConfig(models.Model):
    """
    Configuration for different payment gateways
    """
    name = models.CharField(max_length=50, unique=True)
    gateway_type = models.CharField(max_length=20, choices=Payment.PAYMENT_METHODS)
    is_active = models.BooleanField(default=True)

    # Common settings
    merchant_id = models.CharField(max_length=100, blank=True)
    api_key = models.CharField(max_length=200, blank=True)
    api_secret = models.CharField(max_length=200, blank=True)

    # Gateway-specific settings
    callback_url = models.URLField(blank=True)
    success_url = models.URLField(blank=True)
    failure_url = models.URLField(blank=True)

    # Limits and settings
    min_amount = models.DecimalField(max_digits=10, decimal_places=2, default=1000)
    max_amount = models.DecimalField(max_digits=10, decimal_places=2, default=50000000)
    daily_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.gateway_type})"

    class Meta:
        verbose_name = 'Payment Gateway Config'
        verbose_name_plural = 'Payment Gateway Configs'
