# اجرای آوان با Docker Desktop — Windows / PowerShell

## حالت اول: پیش‌نمایش قابل بازبینی (همین حالا)

این Compose فقط رابط فارسی و ۱۰۰ جلسه/۳۰۰ اقدام **کاملاً ساختگی** را اجرا می‌کند؛ هشت پرسش مدیریتی روی همین داده‌ها پاسخ مستند نمونه می‌دهند. **هیچ اتصال SQL Server، ProcessMaker، OpenAI، درگاه بانکی، Keycloak، حساب مشتری یا ارسال پیامکی ندارد.** GodAdmin/SysAdmin در این حالت فقط صفحات نمایشی بدون احراز هویت یا عملیات واقعی‌اند. تنها از مرورگر **همان لپ‌تاپ** قابل مشاهده است.

ابتدا Docker Desktop را در Windows با Linux containers/WSL2 راه‌اندازی کن. اگر نسخه محلی Python/Uvicorn قبلاً روی پورت ۸۰۹۰ اجرا شده است، در همان PowerShell با Ctrl+C متوقفش کن.

```powershell
$repo = "D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab-GitHub"
git -C $repo pull --ff-only origin main
cd $repo

docker version
docker compose version
docker compose config --quiet
docker compose up -d --build --wait
docker compose ps

# پاسخ سلامت پردازش (نه سلامت SQL/IdP)
Invoke-RestMethod -Uri "http://127.0.0.1:8090/health"
```

سپس این تست عملی روی کانتینر بالا آمده را نیز اجرا کن:

```powershell
powershell -ExecutionPolicy Bypass -File .\commercial\Verify-Docker.ps1
```

این تست باید سلامت، ۱۰۰ جلسه، ۳۰۰ اقدام و خروجی هر هشت پرسش را با اتصال HTTP به برنامه داخل Docker تأیید کند. سپس در مرورگر باز کن: http://127.0.0.1:8090 . بخش «دستیار مدیریتی» برای هشت پرسش و «نمونه SysAdmin/GodAdmin» برای بررسی ظاهر منوها موجود است.

برای دیدن گزارش و رفع خطای اجرا:

```powershell
docker compose logs -f --tail=100 meeting-preview
```

برای توقف موقت: `docker compose stop`. برای اجرای دوباره: `docker compose start`. برای حذف فقط کانتینر و شبکه همین پروژه (بدون حذف تصاویر/فایل‌های خودت): `docker compose down`. برای تغییر کدها و بازسازی: `docker compose up -d --build --wait`. **هیچ‌گاه docker system prune یا حذف Volumeهای دیگر پروژه‌ها را برای این کار اجرا نکن.**

## فونت BYekanPlus

فونت‌های Regular/Bold خودت را در مسیرهای زیر، با نام دقیق، قرار بده:

```text
commercial/web/fonts/byekanplus-regular.ttf
commercial/web/fonts/byekanplus-bold.ttf
```

این دو فایل باید متعلق به خودت و دارای مجوز استفاده باشند؛ در GitHub و image قرار نمی‌گیرند. Volume فقط‌خواندنیِ Compose آن‌ها را از لپ‌تاپ درون کانتینر در دسترس قرار می‌دهد. در نبود فایل‌ها فونت جایگزین Tahoma استفاده می‌شود و درخواست 404 تکراری ارسال نمی‌شود. پس از کپی فایل‌ها، با Ctrl+F5 صفحه مرورگر را تازه کن؛ اگر فونت کش شده بود `docker compose restart meeting-preview`.

## حالت دوم: پنل متصل آزمایشی — فقط پس از فراهم‌شدن هویت و SQL TEST

این یک سرویس Docker **جدا** در `compose.connected-lab.yaml` است. رابط `/portal/` از API تجاری با JWT معتبر، RLS، حساب‌های جداگانه SQL و دسترسی سلسله‌مراتبی /v2 استفاده می‌کند. وجود Docker به‌تنهایی کاربر ProcessMaker را به Keycloak لینک نمی‌کند، SQL را آماده نمی‌کند و داده واقعی جلسات را وارد نمی‌کند. متغیرهای نمونه در فایل example قابل استفاده مستقیم نیستند. برای PROD یا سرور عمومی تنظیم نشده است.

پیش‌نیازها: اسکریپت‌های SQL معتبر و تأییدشده آزمایشی (۱۹ تا ۲۷ طبق مستندات پروژه) فقط در `EnterpriseProcess2_AI_Test`، حساب‌های SQL کم‌دسترسی Reader/DirectoryAdmin/PlatformAdmin، IdP واقعی HTTPS با Authorization Code + PKCE و SPA redirect دقیق `http://127.0.0.1:8088/portal/`، عضویت فعال subject و نگاشت تأییدشده ProcessMaker، و امکان ارتباط امن کانتینر با SQL Server آزمایشی روی TCP ثابت ۱۴۳۳. فایل هویت/گواهی/رمز را در GitHub یا گفتگو قرار نده.

در SQL Server ویندوز، اگر کانتینر روی همان لپ‌تاپ است، در فایل env از `host.docker.internal,1433` استفاده کن، **نه** `DESKTOP-GJI3D8L\\SQLSERVER2022`؛ نام Instance ویندوزی در Linux container به‌صورت Named Instance معمولاً قابل resolve نیست. حتماً آدرس/پورت با تنظیم SQL Server و Firewall **بانک آزمایشی** سازگار باشد. بانک `EnterpriseProcess` و `EnterpriseProcess2` نباید در این Compose استفاده شوند.

```powershell
cd "D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab-GitHub"
Copy-Item ".env.connected-lab.example" ".env.connected-lab"
notepad ".env.connected-lab"
```

**فقط پس از** جایگزینی تمام مقادیر `REPLACE_` و `YOUR_` با تنظیمات واقعیِ آزمایشی و تأیید دسترسی‌ها توسط مسئول IT:

```powershell
docker compose --env-file .env.connected-lab -f compose.connected-lab.yaml config --quiet
docker compose --env-file .env.connected-lab -f compose.connected-lab.yaml up -d --build --wait
docker compose --env-file .env.connected-lab -f compose.connected-lab.yaml ps
Invoke-RestMethod -Uri "http://127.0.0.1:8088/health"
```

سپس `http://127.0.0.1:8088/portal/` را باز کن. `/health` فقط زنده‌بودن پردازش را نشان می‌دهد، نه موفقیت ورود، SQL، Sync یا مجوز لایسنس. اگر IdP تنظیم نشده باشد، ورود باید عمداً غیرفعال بماند. متغیرهای `COMMERCIAL_MODE=lab`، `COMMERCIAL_SQL_DATABASE=EnterpriseProcess2_AI_Test`، `COMMERCIAL_V2_ONLY=1` و `COMMERCIAL_CHAT_ENABLED=0` در Compose اجباری‌اند و با فایل env قابل دورزدن نیستند. تنها آدرس `127.0.0.1:8088` از میزبان منتشر می‌شود؛ پورت را به `0.0.0.0` یا دامنه اینترنتی تغییر نده.

برای توقف سرویس متصل:

```powershell
docker compose --env-file .env.connected-lab -f compose.connected-lab.yaml down
```

برای گزارش زنده سرویس متصل، مراقب محتویات لاگ حاوی اطلاعات کاربران باش؛ هیچ credential، access token یا متن محرمانه را در گفتگو ارسال نکن.

## محدودیت‌ها و امنیت

- سرویس preview برای کنترل مجوز واقعی کاربران نیست؛ فقط اطلاعات خیالی را نشان می‌دهد. سرویس connected-lab بدون حساب و سرویس هویت واقعی قابل استفاده نیست.
- Dockerfileها از کاربر غیر root، قفل filesystem، Healthcheck و binding میزبان localhost استفاده می‌کنند. اتصال برنامه به دیتابیس در سرویس connected نیازمند ODBC Driver 17 است؛ Dockerfile.connected-lab آن را داخل image نصب می‌کند.
- در نمونه فعلی **هیچ** زمان‌بند اعلان، درگاه پرداخت، ورود واقعی داده‌های MTG از ProcessMaker، voice/STT، یا تست نفوذ/تأیید استقرار اینترنتی وجود ندارد. Docker جایگزین تکمیل این بخش‌ها نمی‌شود.
- در محیط ساخت فایل، دسترسی به موتور Docker Desktop ویندوز تو وجود ندارد؛ تست عملی `docker compose up` و تأیید دسترسی SQL/IdP باید در لپ‌تاپ/سرور خودت اجرا شود. در GitHub Actions یک Smoke Test مستقل برای build/start/health و هشت پرسش نمونه تعریف شده است؛ تعریف CI به معنی Passشدن خودکار آن نیست.
