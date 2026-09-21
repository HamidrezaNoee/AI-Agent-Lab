# Docker Desktop — راه‌اندازی فعلی آوان

**فایل `compose.yaml` دیگر نسخه نمایشی نیست و به ویرایش هیچ `.env.production` نیاز ندارد.** همه تنظیمات اتصال پس از ورود GodAdmin از پنل برنامه ثبت می‌شوند.

```powershell
$repo = "D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab-GitHub"
git -C $repo pull --ff-only origin main
cd $repo
docker compose up -d --build --wait
docker compose exec -T avan python -m commercial.setup_console --take-bootstrap
```

آدرس مدیریت نصب: **http://127.0.0.1:8188/admin/**. نام‌کاربری `godadmin`، رمز اولیه تصادفی از خروجی دستور بالا. اولین ورود نیازمند تغییر رمز و راه‌اندازی تأیید دومرحله‌ای است. سپس از داخل پنل می‌توانی SQL Server `EnterpriseProcess2`، OIDC/Keycloak، ProcessMaker و لایسنس را تنظیم کنی.

**[راهنمای کامل و ایمن نصب، پشتیبان‌گیری بانک، بررسی اختلاف ستون‌ها و ارتباط هویت/ProcessMaker](PRODUCTION_ENTERPRISEPROCESS2_SETUP_FA.md)**

برای تشخیص خطای Docker:

```powershell
docker compose ps
docker compose logs --tail=100 avan
```

دستور `docker compose down` volume تنظیمات را حذف نمی‌کند؛ ولی **`docker compose down -v` را اجرا نکن**، زیرا باعث حذف حساب GodAdmin، شناسه نصب و تنظیمات رمزگذاری‌شده می‌شود. کانتینر قدیمی پورت ۸۰۹۰ اگر قبلاً روشن مانده، جداگانه باید متوقف شود. پورت محصول فعلی ۸۱۸۸ است.

در وضعیت کنونی، موفقیت `/health` به معنی وصل‌بودن بانک و قابل استفاده‌بودن کاربر واقعی نیست؛ هویت و لایسنس باید جداگانه داخل پنل تأیید شوند.
