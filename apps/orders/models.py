from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from apps.products.models import Product
from apps.accounts.models import Address


class Order(models.Model):
    """
    Customer orders with status tracking
    """
    STATUS_CHOICES = [
        ('pending', 'در انتظار پرداخت'),
        ('confirmed', 'تأیید شده'),
        ('shipped', 'ارسال شده'),
        ('delivered', 'تحویل داده شده'),
        ('cancelled', 'لغو شده'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    shipping_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, related_name='shipping_orders')
    billing_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, related_name='billing_orders')
    shipping_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order {self.order_number}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f"ORD{self.pk:06d}" if self.pk else "TEMP"
        super().save(*args, **kwargs)

    def get_total_with_shipping(self):
        return self.total_amount + self.shipping_cost

    def get_final_total(self):
        return self.get_total_with_shipping() - self.discount_amount + self.tax_amount

    def can_cancel(self):
        return self.status in ['pending', 'confirmed']

    def can_ship(self):
        return self.status == 'confirmed'

    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']


class OrderItem(models.Model):
    """
    Items within an order
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Price at time of order
    discount = models.DecimalField(max_digits=8, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.quantity} x {self.product.name} in Order {self.order.order_number}"

    def get_total_price(self):
        return (self.price - self.discount) * self.quantity

    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'


class ShippingMethod(models.Model):
    """
    Available shipping methods
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=8, decimal_places=2)
    estimated_days = models.PositiveIntegerField(help_text="Estimated delivery days")
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Shipping Method'
        verbose_name_plural = 'Shipping Methods'
        ordering = ['sort_order', 'cost']
