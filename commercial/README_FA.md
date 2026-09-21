# آوان | سامانه مدیریت هوشمند جلسات

آوان در مسیر پیش‌فرض Docker از `commercial.production_app` و اطلاعات ثبت‌شده در `EnterpriseProcess2.MTG` استفاده می‌کند. تصویر عملیاتی هیچ سناریوی ساختگی یا API قدیمی /v1 را به کاربر ارائه نمی‌دهد.

**[اجرای Docker بدون .env، دریافت یک‌باره رمز GodAdmin و تنظیم تمام اتصال‌های اصلی از داخل برنامه](PRODUCTION_ENTERPRISEPROCESS2_SETUP_FA.md)**

دستورات راه‌اندازی:

```powershell
cd "D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab-GitHub"
git pull --ff-only origin main
docker compose up -d --build --wait
docker compose exec -T avan python -m commercial.setup_console --take-bootstrap
```

مدیریت نصب و تنظیمات در **http://127.0.0.1:8188/admin/** و فضای کاری کارکنان در **http://127.0.0.1:8188/** است. GodAdmin اولیه با رمز تصادفی ایجاد می‌شود؛ تغییر رمز و احراز هویت دومرحله‌ای در اولین ورود لازم است. اطلاعات SQL Server، Realm هویت، ProcessMaker و لایسنس از داخل صفحه مدیریت دریافت و به صورت رمزگذاری‌شده در Docker volume نگهداری می‌شوند؛ کلید خصوصی ناشر هرگز وارد مشتری نمی‌شود.

راه‌اندازی پایگاه اصلی فقط پس از بررسی اختلاف جداول، تأیید نسخه پشتیبان و اعلام صریح نام `EnterpriseProcess2` مجاز است. ابزار نصب از SQLهای از پیش بازبینی‌شده استفاده می‌کند و جدول/فرایند/تریگر موجود `MTG` را تغییر نمی‌دهد.

**محدودیت صداقت محصول:** ساخت Realm و سرویس معتبر Keycloak، کلید عمومی مرجع ناشر و نگاشت/ابطال خودکار حساب کارکنان ProcessMaker هنوز پیش‌نیازهای مستقلی دارند. نصب GodAdmin یا ورود تنظیمات به معنی آماده‌بودن سامانه برای انتشار اینترنتی یا دسترسی محتوایی کارکنان نیست.
