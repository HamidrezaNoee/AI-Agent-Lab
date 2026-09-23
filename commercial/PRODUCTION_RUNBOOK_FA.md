# اجرای عملیاتی آوان — نسخه ۲۳ سپتامبر ۲۰۲۶

این نسخه از **MySQL خود ProcessMaker** برای داده جلسات و گردش کار استفاده می‌کند و SQL Server مستقل **AVANAgent** را برای اطلاعات خود برنامه نگه می‌دارد. نصب روی PHP یا Apache پروسس‌میکر انجام نمی‌شود؛ PHP 5.6.31 آن دست‌نخورده می‌ماند.

## انتخاب محیط

- اجرای تک‌رایانه و پذیرش اولیه: Docker Desktop با Linux containers روی Windows پشتیبانی‌شده؛ نشانی localhost.
- اجرای کاربران سازمان: Docker Engine و Compose v2 روی VM لینوکسی مستقل، دو نام DNS و HTTPS. روی Windows Server 2012 میزبان ProcessMaker، این کانتینرهای لینوکسی را مستقیم نصب نکنید.
- برای شروع VM با ۴ vCPU، ۸ GB RAM و ۴۰ GB فضای آزاد در نظر بگیرید؛ این ظرفیت پیشنهادی شروع است و تست بار واقعی انجام نشده است. SQL Server و MySQL روی سرورهای موجود می‌مانند. PostgreSQL همراه Docker فقط برای هویت Keycloak است.

## ۱. دریافت سورس

شاخه تحویلی هنوز با main ادغام نشده است:

```powershell
git clone --branch feature/pm-native-agent-store-20260922 --single-branch https://github.com/HamidrezaNoee/AI-Agent-Lab.git AI-Agent-Lab-Release
cd AI-Agent-Lab-Release
```

همین دستور git روی Linux نیز اجرا می‌شود. دسترسی مخزن خصوصی باید برقرار باشد.

## ۲. نصب موجود روی رایانه شما

پیش از ارتقا از AVANAgent و volume `avan-production_avan-state` پشتیبان سازگار بگیرید. `.secrets` و کلید رمزگذاری volume را حفظ کنید. ارتقا به منبع بومی، داده یا نگاشت دسترسی قدیمی EnterpriseProcess را خودکار منتقل نمی‌کند؛ دسترسی‌ها در AVANAgent تنظیم می‌شوند.

```powershell
$repo = 'D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab-GitHub'
Set-Location $repo
git fetch origin feature/pm-native-agent-store-20260922
$upgrade = Join-Path $env:TEMP 'update-meeting-agent.ps1'
git show 'origin/feature/pm-native-agent-store-20260922:scripts/update-meeting-agent.ps1' | Set-Content -Encoding UTF8 $upgrade
powershell -ExecutionPolicy Bypass -File $upgrade -SourceRepo $repo -Destination 'D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab-Release-20260923'
```

پوشه مقصد باید جدید باشد. این روش فقط سرویس آوان را بازسازی می‌کند. فایل‌های محرمانه، volume و fingerprint معتبر ناشر حفظ می‌شوند. اگر نصب قبلی HTTPS است، این اسکریپت عمداً متوقف می‌شود؛ روش ارتقای HTTPS پایین را استفاده کنید.

## ۳. نصب تازه و کلید ناشر

در Windows از ریشه checkout:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/init-security.ps1
```

در Linux:

```bash
sh scripts/init-security.sh
```

اگر کلید ناشر قبلاً دارید، همان کلید عمومی را استفاده کنید. در غیر این صورت، روی رایانه **صادرکننده** طبق [راهنمای لایسنس](licensing/ISSUER_GUIDE_FA.md) کلید خصوصی رمزدار بسازید. فقط کلید عمومی و fingerprint آن وارد نسخه مشتری می‌شود.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/pin-license-public-key.ps1 -PublicKey D:\AVAN-Issuer\public.pem
```

Linux:

```bash
python3 scripts/pin-license-public-key.py --public-key /secure/publisher-public.pem
```

تا زمانی که fingerprint پیش‌فرض ناشر جایگزین نشده، مجوز معتبر قابل فعال‌سازی نیست. کلید خصوصی را روی سرور مشتری کپی نکنید.

## ۴. اجرای localhost برای پذیرش

```powershell
docker compose -f compose.yaml config --quiet
docker compose -f compose.yaml up -d --build
docker compose -f compose.yaml ps
docker compose -f compose.yaml exec avan python -m commercial.setup_console --take-bootstrap
```

دستور آخر رمز اولیه GodAdmin را **یک‌بار** نمایش می‌دهد؛ از خروجی Docker عمومی یا فایل لاگ گرفته نمی‌شود. پنل نصب: `http://127.0.0.1:8188/admin/`. نام کاربر `godadmin`؛ تغییر رمز و TOTP اجباری است. اگر قبلاً راه‌اندازی شده، با رمز قبلی وارد شوید. نشانی کاربر: `http://127.0.0.1:8188`.

## ۵. اجرای تازه برای شبکه سازمان با HTTPS

این روش برای **نصب تازه روی سرور مقصد** است. تبدیل volume موجودِ localhost با تغییر URL کافی نیست: issuer ذخیره‌شده و redirectهای realm قبلی باید در یک مهاجرت جداگانه هماهنگ شوند. realm import موجود را بازنویسی نمی‌کند؛ volume را برای رفع خطا حذف نکنید.

دو DNS واقعی مثل `agent.company.example` و `auth.company.example` را به سرور بدهید؛ مثال‌ها را با دامنه متعلق به سازمان جایگزین کنید. سرویس gateway باید روی ۸۰ و ۴۴۳ در دسترس مرجع صدور گواهی باشد. نام auth از داخل کانتینر آوان هم باید با HTTPS و گواهی معتبر قابل دسترسی باشد. در شبکه کاملاً بسته، گواهی سازمانی و trust chain را IT در reverse proxy و کانتینرها نصب کند؛ اعتبارسنجی TLS را غیرفعال نکنید.

روی سرور Linux، پس از مراحل کلید و secrets:

```bash
export AVAN_APP_HOST=agent.your-company.com
export AVAN_AUTH_HOST=auth.your-company.com
docker compose -f compose.yaml -f compose.https.yaml config --quiet
docker compose -f compose.yaml -f compose.https.yaml up -d --build
docker compose -f compose.yaml -f compose.https.yaml ps
docker compose -f compose.yaml -f compose.https.yaml exec avan python -m commercial.setup_console --take-bootstrap
```

در PowerShell برای همان فرمان‌های Docker، ابتدا متغیرهای دامنه را این‌طور تنظیم کنید:

```powershell
$env:AVAN_APP_HOST = 'agent.your-company.com'
$env:AVAN_AUTH_HOST = 'auth.your-company.com'
```

برای هر فرمان بعدی Compose HTTPS، همین دو متغیر و **هر دو فایل** را استفاده کنید. این متغیرها نام دامنه‌اند؛ رمز اتصال بانک و کلید AI در آن‌ها نیست.

کاربران از `https://agent.your-company.com` وارد می‌شوند. پنل GodAdmin از دامنه عمومی پاسخ ۴۰۴ می‌دهد. مدیریت فقط روی loopback سرور باقی می‌ماند. برای بازکردن آن از رایانه مدیر، tunnel بسازید (پورت ۸۱۸۸ رایانه مدیر باید آزاد باشد):

```powershell
ssh -N -L 8188:127.0.0.1:8188 admin@YOUR_LINUX_SERVER
```

سپس روی همان رایانه `http://127.0.0.1:8188/admin/` را باز کنید. این مسیر از HTTPS عمومی کاربران مستقل است. پورت‌های ۸۱۸۸ و ۸۱۸۱ را روی IP شبکه منتشر نکنید.

## ۶. تنظیمات لازم در GodAdmin

ترتیب:

1. **بانک اختصاصی Agent**: SQL host/port و TLS واقعی را بدهید. نصب‌کننده با تأیید `AVANAgent` فقط بانک مستقل و حساب محدود `AVAN_AgentApp` را می‌سازد. رمز مدیر SQL ذخیره نمی‌شود. اگر قبلاً بانک ساخته شده، اتصال حساب برنامه را ثبت کنید.
2. **داده‌های ProcessMaker**: IP/DNS واقعی MySQL، پورت واقعی (معمولاً ۳۳۰۶)، workspace database مانند `wf_workflow`، کاربر SELECT-only و timezone واقعی PHP/PM. `localhost` داخل کانتینر خود کانتینر است؛ برای دیتابیس روی میزبان Docker Desktop از `host.docker.internal` استفاده کنید.
3. **اطلاعات سازمان**: نام را ثبت کنید و Tenant ID و Installation ID را برای صدور لایسنس بردارید.
4. **لایسنس**: کلید عمومی pin‌شده و لایسنس امضاشده مخصوص همین نصب را فعال کنید؛ سپس پذیرش کاربران امکان‌پذیر است.
5. **هویت سازمانی**: اتصال Keycloak را بررسی کنید. ثبت/نگاشت کاربران از مسیر فعلی پنل انجام می‌شود. ایمیل، کاربر فعال ProcessMaker، نقش و مدیر مستقیم باید درست باشند. حساب‌های بدون نگاشت به اطلاعات دسترسی ندارند.
6. **هوش مصنوعی**: API key، مدل مجاز حساب خود و در صورت نیاز مدل‌های صوت را تنظیم و اتصال را آزمایش کنید. بی‌نیازی از API key سرویس AI ادعا نمی‌شود.

Agent به SQL Server قبلی جلسات وصل نمی‌شود. تنظیم REST ProcessMaker برای بررسی اتصال موجود است؛ مسیر خواندن عملیاتی این نسخه MySQL است. برای Import مجموعه، REST جداگانه فقط در workspace آزمایشی استفاده می‌شود.

DBA باید SELECT روی این شش جدول workspace بدهد: `APPLICATION`, `APP_DELEGATION`, `TASK`, `PROCESS`, `USERS`, `DEPARTMENT`. حساب Agent نباید مجوز تغییر داده این بانک داشته باشد. نمونه قدیمی MTG SQL را اجرا نکنید.

### ایجاد حساب ورود برای نصب تازه

بعد از تنظیم MySQL، سازمان و لایسنس، برای هر کاربر تازه این دستور را از میزبان Docker اجرا کنید. UID و ایمیل باید متعلق به همان کاربر فعال ProcessMaker باشند؛ گزینه confirm به معنای تأیید مالکیت ایمیل توسط مدیر سازمان است.

```bash
docker compose -f compose.yaml -f compose.https.yaml exec avan python -m commercial.identity_operator --pm-uid REAL_PM_USER_UID --username ardalan --role SysAdmin --confirm-employee-email employee@your-company.com
```

در نصب localhost فقط `-f compose.yaml` کافی است. رمز موقت تعاملی پرسیده می‌شود. کاربر در اولین ورود رمز را عوض و TOTP را تنظیم می‌کند؛ سپس درخواست امضاشده او در «کاربران» GodAdmin ظاهر می‌شود و مدیر نگاشت PM/نقش را تأیید می‌کند. دستور، حساب موجود را بازنویسی نمی‌کند و مجوز داده را خودکار نمی‌دهد. نقش‌های دیگر Expert و Manager هستند.

در realm تازه، `tenant_id` فقط توسط مدیر قابل ویرایش است. اگر realm از نصب قدیمی باقی مانده، مدیر Keycloak باید در Realm Settings → User Profile ویژگی `tenant_id` را با View/Edit فقط Admin تعریف کند. Import مجدد خودکار این تنظیم را روی realm موجود تغییر نمی‌دهد. ابزار قبل از فعال‌کردن حساب مقدار tenant را بازخوانی می‌کند؛ در صورت ناسازگاری حساب غیرفعال می‌ماند و مدیر باید علت را بررسی کند.

## ۷. پذیرش پیش از استفاده عمومی

`/health` فقط بالا بودن سرویس را نشان می‌دهد؛ تست اتصال‌ها در پنل لازم است. حداقل این موارد را روی محیط آزمایشی واقعی بررسی کنید:

- دو PMX Native با UID اصلی Import شوند؛ دعوت، تأیید صورت‌جلسه، ایجاد اقدام، ارسال/بازگشت گزارش، بررسی دبیر، پیوست و اختتام اجرا شوند.
- حساب کارشناس فقط جلسات/پرونده‌های مجاز خود و مدیر فقط دامنه مصوب را ببیند.
- تعداد تأخیر و اختتام یک جلسه با فرم PM تطبیق داده شود؛ ۱۰۰٪ بدون تأیید دبیر بسته محسوب نشود.
- آمار BI یک فرایند با خود PM تطبیق کند؛ وظایف موازی موجب افزایش تعداد پرونده نشوند.
- گفتگو و پیش‌نویس بعد از restart باقی بمانند؛ تغییر دسترسی نمایش سابقه غیرمجاز را ببندد.
- انقضا و ظرفیت لایسنس روی یک نصب آزمایشی بررسی شوند.
- پرسش واقعی با کلید AI و در صورت نیاز صوت اجرا شود؛ ورود مجدد و توقف پایش پس از ابطال دسترسی بررسی شود.

۱۰۰۸ سناریوی ارائه‌شده را فقط طبق [راهنمای Import](scenarios/README_FA.md) در workspace تست بارگذاری کنید. واردکردن مجموعه آزمایشی در بانک عملیاتی لازم نیست.

## ۸. ارتقا، سلامت و بازیابی

در نصب HTTPS، ابتدا از بانک AVANAgent، volume آوان، PostgreSQL هویت و `.secrets` پشتیبان بگیرید؛ کلید رمزگذاری باید همراه داده قابل بازیابی باشد. image فعلی را tag کنید و commit فعلی را ثبت کنید. تغییرات محلی fingerprint را حفظ کنید.

```bash
docker image tag avan-enterprise:local avan-enterprise:before-update
git rev-parse HEAD
# دریافت نسخه بررسی‌شده؛ فایل pin و تنظیمات نصب را حفظ کنید
git fetch origin feature/pm-native-agent-store-20260922
# پس از fast-forward امن checkout و با همان دامنه‌ها:
docker compose -f compose.yaml -f compose.https.yaml up -d --build --no-deps avan
docker compose -f compose.yaml -f compose.https.yaml ps
docker compose -f compose.yaml -f compose.https.yaml logs --tail 80 avan
```

برای اجرای نسخه قبلی image، بدون پاک‌کردن داده:

```bash
docker image tag avan-enterprise:before-update avan-enterprise:local
docker compose -f compose.yaml -f compose.https.yaml up -d --no-build --no-deps --force-recreate avan
```

اگر طرح داده در نسخه‌های بعد تغییر کند، rollback داده نیز لازم است؛ پشتیبان را جدا نگه دارید. `docker compose down -v` اجرا نکنید. این نسخه یک worker وب دارد؛ replicas را بدون پیاده‌سازی lease پایش و اشتراک نشست افزایش ندهید.

## وضعیت آزمون تحویل

آزمون‌های Python، محاسبات تمام ۱۰۰۸ سناریو، کنترل مجوز و لایسنس، و آزمون مرورگر با API شبیه‌سازی‌شده انجام شده‌اند. اتصال واقعی سازمان به SQL Server/MySQL/ProcessMaker، سرویس AI، صدور گواهی TLS و اجرای Docker در محیط مقصد هنوز انجام نشده‌اند؛ قبولی تست‌های محلی جای پذیرش سازمان را نمی‌گیرد.

مرجع تنظیمات: [Keycloak realm import](https://www.keycloak.org/server/importExport)، [Keycloak reverse proxy](https://www.keycloak.org/server/reverseproxy)، [Caddy HTTPS](https://caddyserver.com/docs/automatic-https).
