from django.db import models
from django.utils.text import slugify

class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name='نام دسته‌بندی')
    slug = models.SlugField(unique=True, allow_unicode=True, verbose_name='اسلاگ')
    image = models.ImageField(upload_to='categories/', blank=True, null=True, verbose_name='تصویر')
    description = models.TextField(blank=True, verbose_name='توضیحات')
    is_active = models.BooleanField(default=True, verbose_name='فعال')

    class Meta:
        verbose_name = 'دسته‌بندی'
        verbose_name_plural = 'دسته‌بندی‌ها'

    def __str__(self):
        return self.name

class Product(models.Model):
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE, verbose_name='دسته‌بندی')
    name = models.CharField(max_length=200, verbose_name='نام محصول')
    slug = models.SlugField(unique=True, allow_unicode=True, verbose_name='اسلاگ')
    price = models.DecimalField(max_digits=10, decimal_places=0, verbose_name='قیمت')
    discount_price = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True, verbose_name='قیمت با تخفیف')
    description = models.TextField(verbose_name='توضیحات')
    image = models.ImageField(upload_to='products/', verbose_name='تصویر اصلی')
    is_featured = models.BooleanField(default=False, verbose_name='محصول ویژه')
    is_active = models.BooleanField(default=True, verbose_name='فعال')
    stock = models.PositiveIntegerField(default=0, verbose_name='موجودی')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ایجاد')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='تاریخ بروزرسانی')

    class Meta:
        verbose_name = 'محصول'
        verbose_name_plural = 'محصولات'

    def __str__(self):
        return self.name

    @property
    def is_in_stock(self):
        return self.stock > 0

    def get_average_rating(self):
        # Placeholder for rating system
        return 5
