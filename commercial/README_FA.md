# آوان — مدیریت هوشمند جلسات و مصوبات

مسیر پیش‌فرض Docker این مخزن اکنون سرویس عملیاتی `commercial.production_app` با فرانت مستقل `commercial/web/production`، بانک `EnterpriseProcess2` و پورت محلی `8188` است. نه دیتاست ساختگی وارد ایمیج عملیاتی می‌شود، نه سیستم از APIهای قدیمی /v1 برای دسترسی به جلسات استفاده می‌کند. ورود، هویت شرکت و نقش‌ها باید از IdP معتبر و نگاشت تأییدشده ProcessMaker به دست بیایند؛ هیچ اکانت پیش‌فرض یا گذرواژه نمایشی ساخته نمی‌شود.

**[راهنمای کامل مهاجرت EnterpriseProcess2، اسکریپت‌های SQL و راه‌اندازی Docker](PRODUCTION_ENTERPRISEPROCESS2_SETUP_FA.md)**

اپلیکیشن متصل فعلی گزارش‌گیری فقط‌خواندنی از جداول `MTG` را با کنترل شرکت واحد، چارت و امضای لایسنس ارائه می‌کند. بااین‌حال اجرای موفق روی **نسخه زنده دیتابیس، هویت و لایسنس شما هنوز مشاهده نشده است** و برخی قابلیت‌های وعده‌داده‌شده محصول (GodAdmin کامل، مدیریت حساب در SysAdmin، Sync و ابطال دسترسی خودکار ProcessMaker، ثبت اقدام در گردش کار، voice/LLM و انتشار اینترنتی امن) هنوز تکمیل نشده‌اند. بخش عملیاتی موجود نباید بدون تأیید SQL و احراز هویت واقعی، آماده استقرار عمومی معرفی شود.

## اسناد و فایل‌های فعال

- [بررسی فقط‌خواندنی اختلاف ستون‌های SQL](sql/PRODUCTION_EnterpriseProcess2_00_inventory.sql)
- [مهاجرت افزودنی AVAN بدون تغییر MTG](sql/PRODUCTION_EnterpriseProcess2_01_AVAN_additive.sql)
- [مجوزهای محدود حساب SQL](sql/PRODUCTION_EnterpriseProcess2_02_reader_grants.sql)
- [قالب کنترل‌شده اتصال هویت کاربران](sql/PRODUCTION_EnterpriseProcess2_03_verified_onboarding_TEMPLATE.sql)
- [قالب فعال‌سازی لایسنس امضاشده](sql/PRODUCTION_EnterpriseProcess2_04_install_signed_license_TEMPLATE.sql)
- [Dockerfile عملیاتی](Dockerfile.production) و [Compose پیش‌فرض](../compose.yaml)

فایل‌های پیش‌نمایش قدیمی در تاریخچه توسعه باقی مانده‌اند؛ نه بخشی از ایمیج عملیاتی هستند و نه در صفحه فعلی به کاربر نمایش داده می‌شوند. پیش از اجرای اسکریپت‌های بانک اصلی، مرحله اول inventory و بررسی ساختار زنده الزامی است.
