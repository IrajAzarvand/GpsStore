# نقشه راه اپ موبایل (GpsStore)

این فایل برای جلوگیری از گم شدن مسیر ساخته شده و باید **بعد از هر تصمیم مهم، تغییر معماری، اضافه شدن قابلیت، یا پایان هر فاز** به‌روز شود.

---

## 1) خلاصه هدف
ساخت اپ موبایل Cross‑Platform برای **پنل ردیابی و گزارش** (بدون بخش فروشگاهی) با پوشش قابلیت‌های نقش‌محور:
- ادمین
- کاربر اصلی (سرگروه)
- زیرکاربر

---

## 2) تصمیم‌های قطعی (Approved Decisions)
- **دامنه اپ**: فقط ردیابی/نقشه/گزارش/عملیات مرتبط (فروشگاه و پرداخت داخل اپ نیست)
- **Login**: `username/password`
- **نقشه**: پشتیبانی از هر دو
  - OpenStreetMap
  - نشان
  - + قابلیت **سوئیچ** داخل اپ
- **Push Notification**: لازم است
- **سرور**: در هر لحظه فقط **یک Server Base URL** (نیازی به ذخیره چند سرور نیست)

---

## 3) نکات مهم از کدبیس فعلی (Backend Reality Check)
- Backend: Django + DRF + JWT (simplejwt) در `gps_store/settings.py` فعال است.
- اما در وضعیت فعلی:
  - `apps/api/urls.py` قبلاً تقریباً خالی بود، ولی اکنون مسیرهای `/api/v1/` اضافه شده‌اند.
  - بعضی عملیات‌ها به صورت view وب + `@login_required` + `csrf_protect` و `request.POST` هستند و برای موبایل باید **JSON API + JWT** داشته باشند.

نتیجه: قبل از شروع جدی اپ، باید **Mobile API Layer** استاندارد شود.

---

## 4) معماری پیشنهادی اپ (Draft)
- **فریم‌ورک پیشنهادی**: Flutter (برای Android + iOS)
- **ماژول‌ها**:
  - Auth (JWT + Refresh)
  - Devices (لیست/جزئیات/فیلتر)
  - Live Map (OSM/نشان)
  - Reports
  - Users/Subusers (بر اساس نقش)
  - Settings (Theme + Server Base URL)
  - Notifications

---

## 5) UX / ناوبری پیشنهادی (Draft)
- Bottom Navigation (نقشه، دستگاه‌ها، گزارش‌ها، کاربران*، تنظیمات)
  - *تب کاربران فقط برای ادمین/سرگروه
- داشبورد نقش‌محور (نمایش کارت‌های مرتبط با نقش)

---

## 6) نیازهای API برای موبایل (Draft)
### 6.1 احراز هویت
- `POST /api/v1/auth/token/`  -> access/refresh
- `POST /api/v1/auth/token/refresh/` -> access جدید
- `POST /api/v1/auth/logout/` (اختیاری؛ اگر blacklist فعال باشد)

### 6.2 دستگاه‌ها و موقعیت
- `GET /api/v1/devices/` (فقط دستگاه‌های قابل مشاهده کاربر)
- `GET /api/v1/devices/{id}/` (جزئیات)
- `GET /api/v1/locations/?device_id=&from=&to=` (برای گزارش/بازه)

### 6.3 گزارش
- استفاده/همسان‌سازی با endpoint موجود:
  - `GET /gps_devices/api/report/` (فعلاً session-based)
  - نیاز به نسخه JWT-friendly یا انتقال به `/api/v1/reports/...`

### 6.4 عملیات نقش‌محور
- ساخت زیرکاربر
- ویرایش/حذف زیرکاربر
- اختصاص دستگاه به زیرکاربر
- اختصاص دستگاه به مشتری (ادمین)

#### وضعیت فعلی (Implemented)
- `POST /api/v1/subusers/` (ساخت زیرکاربر برای کاربر اصلی؛ زیرکاربر اجازه ندارد)
- `POST /api/v1/devices/assign-owner/` (ادمین: اختصاص دستگاه به مالک)
- `POST /api/v1/devices/assign-subuser/` (سرگروه: اختصاص/لغو اختصاص دستگاه به زیرکاربر)

---

## 7) Push Notification (Draft)
- حداقل نیاز:
  - Android: Firebase Cloud Messaging (FCM)
  - iOS: APNs از طریق FCM
- رویدادهای پیشنهادی:
  - SOS/Alarm
  - Overspeed
  - Offline/No data
  - Expire شدن اشتراک (در صورت نیاز)

---

## 8) تنظیم Server Base URL
- یک مقدار `baseUrl` ذخیره می‌شود
- قبل از ذخیره، تست اتصال (Health Check) انجام می‌شود
- تغییر سرور باعث:
  - پاک شدن توکن‌ها
  - پاک شدن کش داده‌ها
  - لاگین مجدد

---

## 9) فازبندی (Milestones)
### فاز 0: آماده‌سازی API برای موبایل
- اضافه کردن router + endpointهای JWT
- تبدیل عملیات‌های فرم‌محور به JSON API (بدون CSRF)

### فاز 1: اسکلت اپ (MVP)
- صفحه تنظیم سرور
- لاگین
- لیست دستگاه‌ها
- نقشه (OSM)

### فاز 2: تکمیل نقشه و گزارش
- اضافه شدن نشان و سوییچ بین OSM/نشان
- صفحه گزارش و خروجی‌ها

### فاز 3: نقش‌ها و عملیات مدیریتی
- مدیریت زیرکاربران
- اختصاص دستگاه‌ها

### فاز 4: Push Notification
- ثبت device token
- ارسال/دریافت نوتیفیکیشن‌ها

---

## 10) وضعیت پیشرفت (Progress Log)
- 2025-12-19:
  - تصمیم‌ها ثبت شد (scope، نقشه OSM+نشان، push، login، تک‌سرور)
  - بررسی اولیه کدبیس: DRF/JWT فعال است ولی URLهای API کامل نیست
  - پیاده‌سازی اولیه Mobile API v1:
    - `GET /api/v1/health/`
    - `POST /api/v1/auth/token/`
    - `POST /api/v1/auth/token/refresh/`
    - `GET /api/v1/devices/` و `GET /api/v1/devices/{id}/` (خواندنی)
    - `GET /api/v1/locations/` و `GET /api/v1/locations/{id}/` (خواندنی)
    - `POST /api/v1/subusers/` (ساخت زیرکاربر)
    - `POST /api/v1/devices/assign-owner/` (اختصاص به مالک توسط ادمین)
    - `POST /api/v1/devices/assign-subuser/` (اختصاص/لغو اختصاص به زیرکاربر توسط سرگروه)
  - اجرای `manage.py check` داخل `venv`: بدون خطا
  - بررسی محیط موبایل:
    - `flutter --version` روی ویندوز موجود نبود (Flutter SDK نصب نیست)
    - تصمیم: نصب Flutter SDK خارج از `venv` و اجرای `flutter doctor`
  - وضعیت Android toolchain:
    - Android SDK در مسیر پیش‌فرض `%LOCALAPPDATA%\Android\Sdk` یافت نشد (adb/sdkmanager نیز یافت نشد)

---

## 11) TODO کوتاه‌مدت (Next Actions)
- اضافه کردن JSON API برای عملیات نقش‌محور:
  - ساخت زیرکاربر
  - اختصاص دستگاه به زیرکاربر
  - اختصاص دستگاه به مالک (ادمین)
- همسان‌سازی/انتقال گزارش‌ها به endpoint JWT-friendly زیر `/api/v1/`
