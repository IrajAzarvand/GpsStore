# مستندات جامع پروژه GpsStore

این فایل شامل تمام اطلاعات فنی، ساختار پروژه، دیتابیس، نحوه دیپلوی و عیب‌یابی پروژه GpsStore است. این سیستم یک پلتفرم ردیابی GPS پیشرفته مبتنی بر وب است که از فناوری‌های مدرن Django، PostgreSQL، Docker و WebSocket استفاده می‌کند.

---

## فهرست مطالب
1. [معرفی پروژه](#معرفی-پروژه)
2. [معماری کلی سیستم](#معماری-کلی-سیستم)
3. [ساختار فایل‌ها](#ساختار-فایل‌ها)
4. [اپلیکیشن‌های Django](#اپلیکیشن‌های-django)
5. [مدل‌های داده](#مدل‌های-داده)
6. [نمایش‌ها و APIها](#نمایش‌ها-و-apiها)
7. [پردازش داده‌های GPS](#پردازش-داده‌های-gps)
8. [دیپلوی و زیرساخت](#دیپلوی-و-زیرساخت)
9. [راهنمای دیپلوی روی سرور](#راهنمای-دیپلوی-روی-سرور)
10. [عیب‌یابی](#عیب‌یابی)

---

## معرفی پروژه

پروژه **GpsStore** یک سیستم ردیابی GPS پیشرفته است که برای مدیریت و نظارت بر دستگاه‌های ردیابی GPS طراحی شده است. این سیستم قابلیت‌های زیر را ارائه می‌دهد:

### ویژگی‌های اصلی
- **پشتیبانی از چندین پروتکل GPS**: HQ، GT06، JT808
- **نمایش زنده موقعیت**: با استفاده از WebSocket و نقشه نشان
- **مدیریت کاربران سلسله‌مراتبی**: کاربر اصلی، زیرکاربران و دستگاه‌ها
- **Map Matching**: تصحیح مسیرها با استفاده از API نشان
- **Reverse Geocoding**: تبدیل مختصات به آدرس
- **سیستم هشدار**: SOS، سرعت غیرمجاز، ژئوفنس
- **API کامل**: REST API برای دسترسی برنامه‌نویسی
- **امنیت پیشرفته**: فیلترینگ داده‌های مخرب، محدودیت نرخ
- **دیپلوی داکر**: کاملاً کانتینری شده

### فناوری‌های استفاده شده
- **Backend**: Django 5.2، Django Channels، PostgreSQL
- **Frontend**: HTML، CSS، JavaScript، Leaflet، نقشه نشان
- **زیرساخت**: Docker، Docker Compose، Nginx، Redis
- **امنیت**: SSL/TLS، CORS، Rate Limiting
- **APIها**: REST Framework، JWT Authentication

---

## معماری کلی سیستم

### معماری لایه‌ای
```
┌─────────────────┐
│   Frontend      │ ← HTML/CSS/JS + Leaflet Maps
├─────────────────┤
│   WebSocket     │ ← Django Channels + Redis
├─────────────────┤
│   REST API      │ ← Django REST Framework
├─────────────────┤
│   Business      │ ← GPS Processing, Map Matching
│   Logic         │
├─────────────────┤
│   Database      │ ← PostgreSQL + PostGIS
├─────────────────┤
│   Infrastructure│ ← Docker + Nginx + Redis
└─────────────────┘
```

### جریان داده
1. **دریافت داده**: دستگاه‌های GPS داده را به پورت 5000 ارسال می‌کنند
2. **پردازش**: داده‌ها توسط دیکدرهای مربوطه پارس می‌شوند
3. **اعتبارسنجی**: بررسی امنیت و فیلترینگ داده‌های مخرب
4. **ذخیره‌سازی**: ذخیره در PostgreSQL با Map Matching
5. **نمایش زنده**: ارسال به کلاینت‌های WebSocket
6. **API**: ارائه داده‌ها از طریق REST API

### کامپوننت‌های کلیدی
- **GPS Receiver**: دریافت و پردازش داده‌های GPS
- **WebSocket Server**: ارتباط زنده با کلاینت‌ها
- **Map Matching Service**: تصحیح مسیرها
- **Reverse Geocoding**: تبدیل مختصات به آدرس
- **Security Layer**: فیلترینگ و محدودیت نرخ

---

## ساختار فایل‌ها

```
GpsStore/
├── .env.local                    # متغیرهای محیطی محلی
├── .env.production              # متغیرهای محیطی تولید
├── docker-compose.yml           # تعریف سرویس‌های داکر
├── Dockerfile                   # دستور ساخت ایمیج داکر
├── docker-entrypoint.sh         # اسکریپت راه‌اندازی کانتینر
├── full_setup.sh               # اسکریپت جامع راه‌اندازی
├── manage.py                   # ابزار مدیریت Django
├── gunicorn.conf.py            # تنظیمات Gunicorn
├── requirements.txt            # وابستگی‌های پایتون
├── pytest.ini                  # تنظیمات تست
├── gps_store/                  # تنظیمات اصلی Django
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
├── apps/                       # اپلیکیشن‌های Django
│   ├── accounts/               # مدیریت کاربران
│   ├── admin_panel/            # پنل مدیریت
│   ├── api/                    # APIهای REST
│   ├── cart/                   # سبد خرید (در حال توسعه)
│   ├── gps_devices/            # مدیریت دستگاه‌های GPS
│   │   ├── decoders/           # دیکدرهای پروتکل
│   │   ├── handlers/           # کنترل‌کننده‌های ارتباطی
│   │   ├── management/commands/# دستورات مدیریتی
│   │   ├── models.py           # مدل‌های GPS
│   │   ├── services/           # سرویس‌های جانبی
│   │   ├── views.py            # نمایش‌ها
│   │   └── consumers.py        # WebSocket consumers
│   ├── orders/                 # سفارشات (در حال توسعه)
│   ├── payments/               # پرداخت‌ها (در حال توسعه)
│   ├── products/               # محصولات
│   ├── subscriptions/          # اشتراک‌ها (در حال توسعه)
│   └── tracking/               # ردیابی (در حال توسعه)
├── nginx/                      # تنظیمات وب‌سرور
│   ├── nginx.conf
│   └── sites-enabled/
├── scripts/                    # اسکریپت‌های کمکی
├── ssl/                        # گواهی‌های SSL
├── logs/                       # فایل‌های لاگ
├── media/                      # فایل‌های رسانه‌ای
├── static/                     # فایل‌های استاتیک
├── staticfiles/                # فایل‌های استاتیک جمع‌آوری شده
├── backup/                     # فایل‌های پشتیبان
└── monitoring/                 # تنظیمات مانیتورینگ
```

---

## اپلیکیشن‌های Django

### 1. accounts (مدیریت کاربران)
**مسئولیت**: مدیریت کاربران، احراز هویت و دسترسی‌ها

**ویژگی‌ها**:
- مدل کاربر سفارشی بر پایه AbstractUser
- سیستم سلسله‌مراتبی کاربران (کاربر اصلی ← زیرکاربران)
- مدیریت دسترسی دستگاه‌ها
- پشتیبانی از شماره تلفن و آدرس

### 2. admin_panel (پنل مدیریت)
**مسئولیت**: رابط مدیریتی سیستم

**وضعیت**: در حال توسعه - فعلاً خالی

### 3. api (APIهای REST)
**مسئولیت**: ارائه APIهای برنامه‌نویسی

**ویژگی‌ها**:
- مدل ApiKey برای کلیدهای API
- مدیریت دسترسی و محدودیت نرخ
- لاگ‌گیری استفاده از API

### 4. cart (سبد خرید)
**مسئولیت**: مدیریت سبد خرید کاربران

**وضعیت**: در حال توسعه - فعلاً خالی

### 5. gps_devices (مدیریت دستگاه‌های GPS)
**مسئولیت**: هسته اصلی سیستم - مدیریت دستگاه‌ها و داده‌های GPS

**ویژگی‌ها**:
- مدل‌های دستگاه، موقعیت مکانی، وضعیت
- دیکدرهای پروتکل GPS
- پردازش داده‌های زنده
- WebSocket برای نمایش زنده
- Map Matching و Reverse Geocoding

### 6. orders (سفارشات)
**مسئولیت**: مدیریت سفارشات محصولات

**وضعیت**: در حال توسعه - فعلاً خالی

### 7. payments (پرداخت‌ها)
**مسئولیت**: مدیریت پرداخت‌ها

**وضعیت**: در حال توسعه - فعلاً خالی

### 8. products (محصولات)
**مسئولیت**: مدیریت محصولات فروشگاه

**ویژگی‌ها**:
- دسته‌بندی محصولات
- مدیریت موجودی و قیمت
- تصاویر محصولات

### 9. subscriptions (اشتراک‌ها)
**مسئولیت**: مدیریت اشتراک‌های کاربران

**وضعیت**: در حال توسعه - فعلاً خالی

### 10. tracking (ردیابی)
**مسئولیت**: سیستم ردیابی پیشرفته

**وضعیت**: در حال توسعه - فعلاً خالی

---

## مدل‌های داده

### accounts/models.py

#### User (کاربر)
```python
class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_subuser_of = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    subscription_start = models.DateTimeField(null=True, blank=True)
    subscription_end = models.DateTimeField(null=True, blank=True)
    is_premium = models.BooleanField(default=False)
```

**فیلدها**:
- `phone`: شماره تلفن
- `address`: آدرس
- `is_subuser_of`: کاربر والد (برای ساختار سلسله‌مراتبی)
- `subscription_start/end`: دوره اشتراک
- `is_premium`: وضعیت پریمیوم

#### UserDevice (دسترسی کاربر به دستگاه)
```python
class UserDevice(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    device = models.ForeignKey('gps_devices.Device', on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_owner = models.BooleanField(default=False)
    can_view = models.BooleanField(default=True)
    can_control = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
```

**فیلدها**:
- مدیریت دسترسی کاربران به دستگاه‌های GPS
- کنترل سطح دسترسی (مشاهده، کنترل)
- تاریخ انقضا دسترسی

### api/models.py

#### ApiKey (کلید API)
```python
class ApiKey(models.Model):
    api_key = models.CharField(max_length=64, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    usage_count = models.IntegerField(default=0)
    rate_limit_per_minute = models.IntegerField(default=60)
    allowed_ips = models.JSONField(default=list, blank=True)
```

**فیلدها**:
- کلید API منحصر به فرد
- محدودیت نرخ و IPهای مجاز
- آمار استفاده

### gps_devices/models.py

#### State (وضعیت دستگاه)
```python
class State(models.Model):
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True, null=True)
```

**وضعیت‌های ممکن**: Moving, Stopped, Idle, Parked

#### Model (مدل دستگاه)
```python
class Model(models.Model):
    PROTOCOL_CHOICES = [('TCP', 'TCP'), ('UDP', 'UDP'), ('HTTP', 'HTTP'), ('MQTT', 'MQTT')]
    
    model_name = models.CharField(max_length=100)
    manufacturer = models.CharField(max_length=100)
    protocol_type = models.CharField(max_length=20, choices=PROTOCOL_CHOICES)
    default_config = models.JSONField(default=dict, blank=True)
    image_url = models.URLField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
```

**فیلدها**:
- اطلاعات مدل دستگاه GPS
- پروتکل ارتباطی پیش‌فرض
- تنظیمات کانفیگ

#### Device (دستگاه)
```python
class Device(models.Model):
    STATUS_CHOICES = [('active', 'فعال'), ('inactive', 'غیرفعال'), ('maintenance', 'در تعمیر')]
    
    imei = models.CharField(max_length=20, unique=True)
    sim_no = models.CharField(max_length=20, blank=True, null=True)
    model = models.ForeignKey(Model, on_delete=models.PROTECT)
    driver_name = models.CharField(max_length=100, blank=True, null=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    consecutive_count = models.JSONField(default=dict, blank=True)
```

**فیلدها**:
- `imei`: شناسه منحصر به فرد دستگاه
- `sim_no`: شماره سیم‌کارت
- `model`: مدل دستگاه
- `owner`: مالک دستگاه
- `consecutive_count`: شمارنده‌های متوالی برای منطق وضعیت

#### LocationData (داده‌های مکانی)
```python
class LocationData(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    
    # Map Matching
    original_latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    original_longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    is_map_matched = models.BooleanField(default=False)
    matched_geometry = models.TextField(blank=True, null=True)
    
    speed = models.FloatField(default=0)
    heading = models.FloatField(default=0)
    altitude = models.FloatField(default=0)
    accuracy = models.FloatField(default=0)
    satellites = models.IntegerField(default=0, null=True)
    battery_level = models.IntegerField(default=0, null=True, blank=True)
    signal_strength = models.IntegerField(default=0, null=True)
    
    # LBS Data
    gsm_operator = models.CharField(max_length=50, blank=True, null=True)
    mcc = models.IntegerField(null=True, default=None)
    mnc = models.IntegerField(null=True, default=None)
    lac = models.IntegerField(null=True, default=None)
    cid = models.IntegerField(null=True, default=None)
    
    packet_type = models.CharField(max_length=20, blank=True, null=True)
    location_source = models.CharField(max_length=20, default='GPS')
    is_alarm = models.BooleanField(default=False)
    alarm_type = models.CharField(max_length=50, null=True, blank=True)
    raw_data = models.TextField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_valid = models.BooleanField(default=True)
```

**فیلدهای کلیدی**:
- مختصات اصلی و تصحیح شده (Map Matching)
- اطلاعات سرعت، جهت، ارتفاع
- داده‌های ماهواره و سیگنال
- اطلاعات LBS (MCC, MNC, LAC, CID)
- نوع پکت و منبع موقعیت

#### DeviceState (وضعیت دستگاه)
```python
class DeviceState(models.Model):
    device = models.ForeignKey(Device, on_delete=models.CASCADE)
    state = models.ForeignKey(State, on_delete=models.PROTECT)
    timestamp = models.DateTimeField(auto_now_add=True)
    location_data = models.ForeignKey(LocationData, on_delete=models.SET_NULL, null=True, blank=True)
```

**پیگیری تغییرات وضعیت دستگاه**

#### RawGpsData (داده‌های خام GPS)
```python
class RawGpsData(models.Model):
    STATUS_CHOICES = [('pending', 'در انتظار'), ('processed', 'پردازش شده'), ('rejected', 'رد شده'), ('blocked', 'مسدود شده')]
    
    raw_data = models.TextField()
    ip_address = models.GenericIPAddressField()
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, null=True)
```

**ذخیره داده‌های خام برای دیباگ و بازپخش**

#### MaliciousPattern (الگوهای مخرب)
```python
class MaliciousPattern(models.Model):
    pattern = models.TextField(unique=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    pattern_type = models.CharField(max_length=20, choices=[
        ('exact', 'تطابق دقیق'), ('startswith', 'شروع با'), ('contains', 'شامل'), ('regex', 'عبارت منظم')
    ], default='contains')
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    hit_count = models.IntegerField(default=0)
    last_hit = models.DateTimeField(null=True, blank=True)
```

**سیستم امنیتی برای فیلترینگ داده‌های مخرب**

### products/models.py

#### Category (دسته‌بندی)
```python
class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name='نام دسته‌بندی')
    slug = models.SlugField(unique=True, allow_unicode=True)
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
```

#### Product (محصول)
```python
class Product(models.Model):
    category = models.ForeignKey(Category, related_name='products', on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, allow_unicode=True)
    price = models.DecimalField(max_digits=10, decimal_places=0)
    discount_price = models.DecimalField(max_digits=10, decimal_places=0, blank=True, null=True)
    description = models.TextField()
    image = models.ImageField(upload_to='products/')
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    stock = models.PositiveIntegerField(default=0)
```

---

## نمایش‌ها و APIها

### gps_devices/views.py

#### map_v2 (نمایش نقشه زنده)
```python
@login_required
def map_v2(request):
    """
    نمایش نقشه با دستگاه‌های فعال
    """
```
**ویژگی‌ها**:
- احراز هویت مبتنی بر JWT برای WebSocket
- ساختار سلسله‌مراتبی کاربران
- نمایش زنده موقعیت‌ها
- فیلترینگ بر اساس دسترسی کاربر

#### report (گزارش‌گیری)
```python
@login_required
def report(request):
    """
    نمایش صفحه گزارش دستگاه‌ها
    """
```
**ویژگی‌ها**:
- گزارش دوره‌ای موقعیت‌ها
- تبدیل تاریخ شمسی به میلادی
- نمایش روی نقشه

#### get_device_report (API گزارش دستگاه)
```python
@login_required
def get_device_report(request):
    """
    API endpoint برای دریافت گزارش دستگاه به صورت JSON
    """
```
**پارامترها**:
- `device_id`: شناسه دستگاه
- `start_date`, `start_time`: تاریخ شروع
- `end_date`, `end_time`: تاریخ پایان

**خروجی**: آمار سفر، مسافت، سرعت، نقاط مکانی

### gps_devices/urls.py
```python
urlpatterns = [
    path('map/', views.map_v2, name='map_v2'),
    path('report/', views.report, name='report'),
    path('api/report/', views.get_device_report, name='get_device_report'),
]
```

### WebSocket Consumers

#### DeviceUpdateConsumer (gps_devices/consumers.py)
```python
class DeviceUpdateConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer برای آپدیت‌های زنده دستگاه
    """
```
**ویژگی‌ها**:
- احراز هویت JWT
- گروه‌بندی کاربران (admins_group, user_group_{id})
- پخش آپدیت‌های موقعیت به کلاینت‌ها

### gps_devices/routing.py
```python
websocket_urlpatterns = [
    re_path(r'ws/device-updates/$', consumers.DeviceUpdateConsumer.as_asgi()),
]
```

---

## پردازش داده‌های GPS

### دیکدرهای پروتکل

#### HQ_Decoder.py (پروتکل HQ)
**پشتیبانی از پکت‌های**:
- **V1**: موقعیت GPS کامل
- **V0**: موقعیت LBS (دکل مخابراتی)
- **V2**: هشدار/وضعیت
- **SOS**: هشدار اضطراری
- **HB**: Heartbeat
- **UPLOAD**: آپلود دسته‌ای

**ویژگی‌های کلیدی**:
- تبدیل مختصات DDMM.MMMM به درجه اعشاری
- پارس کردن فلگ‌های وضعیت (32 بیت)
- پشتیبانی از LBS با OpenCellID و Mozilla Location Service
- تشخیص خودکار پروتکل

#### GT06_Decoder.py (پروتکل GT06)
**پشتیبانی از دستگاه‌های**:
- Concox GT06
- پروتکل باینری

#### JT808_Decoder.py (استاندارد چینی JT808)
**پشتیبانی از**:
- استاندارد ملی چین برای ردیابی وسایل نقلیه
- پروتکل TCP پیشرفته

### سرویس‌های جانبی

#### MapMatchingService (gps_devices/services/map_matching.py)
```python
class MapMatchingService:
    """
    سرویس Map Matching نشان
    """
```
**ویژگی‌ها**:
- اتصال به API نشان برای تصحیح مسیر
- کش‌گذاری نتایج
- مدیریت خطاها و retry logic
- محدودیت نرخ درخواست

#### ReverseGeocodingService (gps_devices/services/reverse_geocoding.py)
```python
class ReverseGeocodingService:
    """
    سرویس تبدیل مختصات به آدرس
    """
```
**پشتیبانی از providerهای**:
- **Nominatim**: OpenStreetMap (رایگان)
- **OpenCage**: API تجاری
- **Load Balancing**: توزیع بار بین providerها
- **کش‌گذاری**: جلوگیری از درخواست‌های تکراری

### گیرنده GPS (gps_receiver.py)

#### ویژگی‌های اصلی
- **پورت 5000**: گوش دادن به TCP/UDP/MQTT
- **Thread Pool**: حداکثر 20 ترد همزمان
- **Security Layer**: فیلترینگ IP و الگوهای مخرب
- **Rate Limiting**: حداکثر 20 درخواست در دقیقه per IP
- **Connection Management**: جلوگیری از نشت اتصال دیتابیس

#### منطق پردازش
1. **دریافت داده**: از TCP/UDP/MQTT
2. **شناسایی پروتکل**: بررسی هدر بسته
3. **دیکد کردن**: استفاده از دیکدر مناسب
4. **اعتبارسنجی**: بررسی امنیت و نرخ
5. **پردازش**: ذخیره در دیتابیس با Map Matching
6. **پخش زنده**: ارسال به WebSocket clients

#### مدیریت وضعیت دستگاه
- **Moving**: سرعت > 0 و حرکت معنی‌دار
- **Stopped**: سرعت = 0 و 3 پکت متوالی
- **Idle**: 3 Heartbeat متوالی
- **Parked**: ACC خاموش + عدم حرکت

---

## دیپلوی و زیرساخت

### Docker Configuration

#### docker-compose.yml
```yaml
services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: ${DATABASE_NAME}
      POSTGRES_USER: ${DATABASE_USER}
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"

  web:
    build: .
    ports:
      - "8000:8000"
      - "5000:5000"
    environment:
      DEBUG: ${DEBUG}
      SECRET_KEY: ${SECRET_KEY}
      # ... سایر متغیرها
    volumes:
      - ./media:/app/media
      - ./staticfiles:/app/staticfiles
    depends_on:
      - db
      - redis

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/sites-enabled:/etc/nginx/sites-enabled
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - web
```

#### Dockerfile
```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=gps_store.settings

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc postgresql-client libpq-dev nginx supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY manage.py gps_store/ apps/ templates/ static/ *.py *.sh \
     apps/gps_devices/decoders/ ./apps/gps_devices/decoders/

# Create directories
RUN mkdir -p /app/staticfiles /app/media /app/logs

# Copy entrypoint
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app \
    && chmod -R 755 /app/logs /app/staticfiles /app/media

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["gunicorn", "--config", "gunicorn.conf.py", "gps_store.asgi:application"]
```

### Nginx Configuration

#### nginx.conf (اصلی)
```nginx
user nginx;
worker_processes auto;
error_log /var/log/nginx/error.log;
pid /run/nginx.pid;

events {
    worker_connections 1024;
}

http {
    include /etc/nginx/mime.types;
    default_type application/octet-stream;
    
    log_format main '$remote_addr - $remote_user [$time_local] "$request" '
                    '$status $body_bytes_sent "$http_referer" '
                    '"$http_user_agent" "$http_x_forwarded_for"';
    
    access_log /var/log/nginx/access.log main;
    
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    keepalive_timeout 65;
    types_hash_max_size 2048;
    
    # Gzip Settings
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json;
    
    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/s;
    
    include /etc/nginx/sites-enabled/*;
}
```

#### sites-enabled/gpsstore (کانفیگ سایت)
```nginx
upstream django_app {
    server web:8000;
}

server {
    listen 80;
    server_name 91.107.135.136 bruna.ir;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name 91.107.135.136 bruna.ir;
    
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES256-GCM-SHA384;
    
    # Static files
    location /static/ {
        alias /app/staticfiles/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Media files
    location /media/ {
        alias /app/media/;
        expires 30d;
        add_header Cache-Control "public";
    }
    
    # API endpoints with rate limiting
    location /api/ {
        limit_req zone=api burst=20 nodelay;
        proxy_pass http://django_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # WebSocket connections
    location /ws/ {
        proxy_pass http://django_app;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_read_timeout 86400;
    }
    
    # Main application
    location / {
        proxy_pass http://django_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
    }
    
    # Security headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
```

### تنظیمات Django (settings.py)

#### تنظیمات کلیدی
```python
# Security
SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Database
DATABASES = {
    'default': {
        'ENGINE': os.getenv('DATABASE_ENGINE', 'django.db.backends.postgresql'),
        'NAME': os.getenv('DATABASE_NAME'),
        'USER': os.getenv('DATABASE_USER'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD'),
        'HOST': os.getenv('DATABASE_HOST', 'db'),
        'PORT': os.getenv('DATABASE_PORT', '5432'),
    }
}

# Channels (WebSocket)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [(os.getenv('REDIS_HOST', 'redis'), 6379)],
        },
    },
}

# REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour',
    }
}

# JWT Settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# CORS
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:3000').split(',')

# Email
EMAIL_BACKEND = os.getenv('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'

# Neshan API Keys
NESHAN_MAP_API_KEY = os.getenv('NESHAN_MAP_API_KEY')
NESHAN_SERVICE_API_KEY = os.getenv('NESHAN_SERVICE_API_KEY')

# Reverse Geocoding
NOMINATIM_BASE_URL = os.getenv('NOMINATIM_BASE_URL', 'https://nominatim.openstreetmap.org/reverse')
OPENCAGE_API_KEY = os.getenv('OPENCAGE_API_KEY')
```

---

## راهنمای دیپلوی روی سرور

### پیش‌نیازها
- سرور Ubuntu/Debian
- دسترسی root یا sudo
- حداقل 2GB RAM، 20GB فضای دیسک

### مراحل نصب سریع

#### 1. اتصال به سرور
```bash
ssh root@91.107.135.136
```

#### 2. انتقال فایل‌ها
```bash
# از سیستم محلی
scp -r GpsStore/ root@91.107.135.136:~
```

#### 3. اجرای اسکریپت نصب
```bash
cd GpsStore
chmod +x full_setup.sh
./full_setup.sh
```

### اسکریپت full_setup.sh

#### عملکردهای کلیدی
1. **نصب Docker و Docker Compose**
2. **ایجاد فایل .env با تنظیمات امنیتی**
3. **ساخت ایمیج‌های داکر**
4. **راه‌اندازی کانتینرها**
5. **اجرای Migrationهای دیتابیس**
6. **ایجاد superuser**
7. **جمع‌آوری فایل‌های استاتیک**
8. **تنظیم فایروال UFW**
9. **راه‌اندازی سرویس GPS receiver**

#### متغیرهای محیطی (.env)
```bash
# Django Configuration
DEBUG=False
SECRET_KEY=<generated-random-key>
ALLOWED_HOSTS=91.107.135.136,bruna.ir,www.bruna.ir
CSRF_TRUSTED_ORIGINS=https://bruna.ir,https://www.bruna.ir

# Database Configuration
DATABASE_ENGINE=django.db.backends.postgresql
DATABASE_NAME=gpsstore_prod
DATABASE_USER=gpsstore_user
DATABASE_PASSWORD=iraj66100
DATABASE_HOST=db
DATABASE_PORT=5432

# Redis Configuration
REDIS_URL=redis://redis:6379/1

# CORS Configuration
CORS_ALLOWED_ORIGINS=https://bruna.ir

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=noreply@gpsstore.com

# Neshan Map API
NESHAN_MAP_API_KEY=web.67f5a720d42541cfae21115f05a637b5
NESHAN_SERVICE_API_KEY=service.eb5fc1ef015e49d187f7abc8a208ce09

# Reverse Geocoding
NOMINATIM_BASE_URL=https://nominatim.openstreetmap.org/reverse
OPENCAGE_API_KEY=701355a7d3d84c66a6dec0e8817804b8

# Superuser Configuration
DJANGO_SUPERUSER_USERNAME=root
DJANGO_SUPERUSER_PASSWORD=iraj66100
DJANGO_SUPERUSER_EMAIL=root@gpsstore.com
```

### دسترسی‌ها
- **وب‌سایت**: `https://bruna.ir`
- **پنل ادمین**: `https://bruna.ir/admin/`
- **نام کاربری ادمین**: `root`
- **رمز عبور ادمین**: `iraj66100`
- **GPS Receiver**: پورت 5000 (TCP/UDP)

### مانیتورینگ (اختیاری)
```bash
# راه‌اندازی Prometheus و Grafana
docker compose -f monitoring/docker-compose.monitoring.yml up -d

# دسترسی‌ها:
# Prometheus: http://your-server:9090
# Grafana: http://your-server:3000 (admin/admin)
```

---

## عیب‌یابی

### مشکلات رایج

#### 1. خطای "Bad Gateway" (502)
**علت**: کانتینر web اجرا نشده یا در حال ریستارت است.

**بررسی**:
```bash
docker compose ps
docker compose logs web --tail=50
```

**راه‌حل**:
- بررسی تنظیمات دیتابیس در .env
- بررسی اتصال به Redis
- ریستارت کانتینرها:
```bash
docker compose restart web
```

#### 2. خطای "Too many clients" در دیتابیس
**علت**: نشت اتصالات دیتابیس توسط تردهای GPS receiver.

**راه‌حل**:
- کد gps_receiver.py بهینه‌سازی شده برای مدیریت اتصالات
- تنظیم `CONN_MAX_AGE = 60` در settings.py
- استفاده از ThreadPoolExecutor با محدودیت 20 ترد
- تنظیم timeout برای اتصالات TCP (10 ثانیه)

#### 3. تغییرات کد اعمال نمی‌شود
**علت**: کانتینرها با کد قدیمی اجرا می‌شوند.

**راه‌حل**:
```bash
# Rebuild با cache جدید
docker compose build --no-cache
docker compose up -d --build
docker compose restart
```

#### 4. دستگاه GPS وصل می‌شود اما داده ثبت نمی‌شود
**بررسی**:
```sql
-- بررسی RawGpsData
SELECT * FROM gps_devices_rawgpsdata 
WHERE status = 'pending' 
ORDER BY created_at DESC LIMIT 10;
```

**علل ممکن**:
- پروتکل دستگاه پشتیبانی نمی‌شود
- فرمت داده نامعتبر
- خطای دیکدر

#### 5. WebSocket کار نمی‌کند
**بررسی**:
- تنظیمات CHANNEL_LAYERS در settings.py
- اتصال Redis
- CORS settings
- SSL certificate برای WSS

#### 6. Map Matching شکست می‌خورد
**بررسی**:
- NESHAN_SERVICE_API_KEY در .env
- اتصال اینترنت
- محدودیت نرخ API نشان

#### 7. Reverse Geocoding کار نمی‌کند
**بررسی**:
- OPENCAGE_API_KEY یا Nominatim
- Rate limiting
- Cache Redis

### دستورات مفید

#### مدیریت کانتینرها
```bash
# وضعیت کانتینرها
docker compose ps

# لاگ‌ها
docker compose logs -f web
docker compose logs -f db

# ریستارت
docker compose restart web

# پاکسازی کامل
docker compose down -v
docker system prune -a
```

#### مدیریت GPS Receiver
```bash
# بررسی سرویس
sudo systemctl status gps-receiver.service

# ریستارت سرویس
sudo systemctl restart gps-receiver.service

# لاگ سرویس
sudo journalctl -u gps-receiver.service -f
```

#### پشتیبان‌گیری
```bash
# پشتیبان دیتابیس
docker compose exec db pg_dump -U gpsstore_user gpsstore_prod > backup.sql

# پشتیبان فایل‌ها
tar -czf backup_media.tar.gz media/
```

#### مانیتورینگ عملکرد
```bash
# استفاده CPU/RAM
docker stats

# اتصالات دیتابیس
docker compose exec db psql -U gpsstore_user -d gpsstore_prod -c "SELECT count(*) FROM pg_stat_activity;"

# اندازه دیتابیس
docker compose exec db psql -U gpsstore_user -d gpsstore_prod -c "SELECT pg_size_pretty(pg_database_size('gpsstore_prod'));"
```

### استراتژی‌های بهینه‌سازی

#### 1. Database Optimization
- ایندکس‌گذاری مناسب روی LocationData
- Partitioning برای جداول بزرگ
- Connection pooling

#### 2. GPS Receiver Optimization
- استفاده از asyncio برای I/O غیرمستقیم
- Batch processing برای ذخیره داده‌ها
- Memory pooling برای کاهش GC

#### 3. Caching Strategy
- Redis برای session و cache
- Database query caching
- API response caching

#### 4. Monitoring
- Prometheus metrics
- Grafana dashboards
- Alerting rules

---

این مستندات به صورت کامل و جامع سیستم GpsStore را پوشش می‌دهد. برای اطلاعات بیشتر یا سوالات فنی، لطفاً با تیم توسعه تماس بگیرید.
