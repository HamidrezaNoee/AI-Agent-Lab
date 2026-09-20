# وضعیت قابل بازبینی آوان — ۲۰ سپتامبر ۲۰۲۶

## اکنون چه چیزی واقعاً قابل اجراست؟

پیش‌نمایش فارسی RTL با ۱۰۰ سناریوی *کاملاً ساختگی* و سه ماژول اختیاری فقط برای بررسی UI و جریان محصول قابل اجراست:

```powershell
$repo = "D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab-GitHub"
$python = "D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab\.venv\Scripts\python.exe"
git -C $repo pull --ff-only origin main
cd $repo
& $python -m pip install -r commercial/requirements.txt
& $python -m unittest discover -s commercial/tests -v
& $python -m uvicorn commercial.demo_preview:app --host 127.0.0.1 --port 8090
```

مرورگر: http://127.0.0.1:8090 . پس از بررسی، Ctrl+C در پنجره PowerShell.

این پنل بدون SQL و ProcessMaker و Keycloak اجرا می‌شود؛ برای مشتری یا استفاده عملیاتی نیست. هیچ کد لایسنس واقعی، خرید، دسترسی مدیر یا ارسال اعلان در این نمایشگر انجام نمی‌شود.

## چه اصلاحی روی کد فعلی انجام شده است؟

- دو فایل **قدیمی و تداخلی** با نام‌های دقیق `15_identity_hierarchy_authorization_TEST_ONLY.sql` و `16_test_hierarchy_authorization_TEST_ONLY.sql` بازنشسته شده‌اند. اجرا نکنید. این فایل‌ها با اسکریپت‌های دیگر ۱۵/۱۶ که قبلاً تست شده‌اند تفاوت دارند.
- مسیر معتبر دایرکتوری/چارت آزمایشی، `commercial/sql/19_directory_hierarchy_TEST_ONLY.sql` تا `27_admin_login_permissions_TEST_ONLY.sql` است. **هیچ‌یک از SQLهای جدید را بدون بررسی پیش‌نیازها و فقط در بانک TEST اجرا نکنید.**
- در مدل درخواست‌شده، کارشناس فقط جلسات مرتبط با دخالت خودش یا افراد زیرچارت فعال خودش را می‌بیند؛ مجوزهای قدیمیِ ساخته‌شده صرفاً برای دیتاست ۱۰۰جلسه‌ای دیگر در `/v2` به‌تنهایی دسترسی اضافه نمی‌کنند. Manager/SysAdmin فقط در Tenant خود همه جلسات را می‌بینند؛ GodAdmin محتوای مشتری را به‌طور خودکار نمی‌بیند.
- برای فعال‌کردن مسیر سازمانی، تنظیم محیطی `COMMERCIAL_V2_ONLY=1` تمام مسیرهای محتوایی قدیمی `/v1` را با HTTP 410 از دسترس خارج می‌کند، تا جست‌وجو/تحلیل قدیمی راه میان‌بُر کنترل چارت نشود. `/v2` همچنان JWT واقعی و عضویت فعال SQL می‌خواهد.
- برای لایسنس فقط `commercial/licensing/studio.py` و `commercial/licensing/codec.py` معتبرند. فایل `commercial/license_studio.py` صرفاً به ابزار رسمی ارجاع می‌دهد و توکن ناسازگار قدیمی صادر نمی‌کند.

## کنترل‌های جدید آفلاین

```powershell
& $python -m pip check
& $python -m unittest discover -s commercial/tests -v
& $python -m commercial.preflight --database
```

`preflight` گزارش وضعیت تنظیمات، اشیای قابل خواندن Reader و اتصال Subject به DirectoryUser را بدون چاپ رمز می‌دهد. برای رسیدن به نتیجه مفیدِ SQL، متغیرهای قبلی reader به‌علاوه `COMMERCIAL_TEST_TENANT_ID` و `COMMERCIAL_TEST_SUBJECT` لازم‌اند. اگر Keycloak/حساب‌های مدیریتی/REST کاربران PM تنظیم نشده‌اند، گزارش `LAB_CONFIGURATION_INCOMPLETE` نتیجه درست است. پرچم اختیاری `--processmaker` فقط کاربران PM را از API فقط‌خواندنی بررسی می‌کند؛ جلسات را وارد نمی‌کند. این چک **هرگز آماده‌بودن محصول برای مشتری را تأیید نمی‌کند**.

## چه چیزی هنوز «قابل استفاده عملیاتی» نیست؟

- اتصال و آزمون واقعی Keycloak/BFF و نگاشت تأییدشده `sub` به ProcessMaker UID؛ حساب‌های جدید PM به شکل خودکار مجوز AI نمی‌گیرند.
- Sync کنترل‌شده صورتجلسات، دبیر، رئیس، اقدام‌کنندگان و نامه‌ها با داده واقعی و طبقه‌بندی محرمانگی از منابع مورد تأیید.
- اجرای migrations ۱۹ تا ۲۷ در بانک آزمایشی، آزمایش واقعی Reader/DirectoryAdmin/PlatformAdmin و امضای لایسنس روی نصب مشتری.
- کد BFF نشست HttpOnly/CSRF هم‌سطح Organization Portal، بازیابی رمز واقعی از Keycloak، تنظیم امن SQL/PM secrets در UI و آزمون جامع مجوز کاربران/درخت.
- استقرار تولیدی، اعلان زمان‌بندی‌شده، voice و پرداخت بانکی.

به‌همین دلیل پنل متصل `/portal/` را نباید در محیط عمومی اجرا کرد و `COMMERCIAL_CHAT_ENABLED=0` باید باقی بماند. این مرحله برای بازبینی پیش‌نمایش و بررسی امنیت کد قابل استفاده است، نه تحویل یک نرم‌افزار عملیاتی.


## رفع خطاهای گزارش‌شده در اجرای محلی

- مسیر قدیمی `/v1/meetings/page` اکنون به تابع واردشده `visible_meetings_page` برمی‌گردد؛ خطای `NameError: visible_meetings_v2 is not defined` نباید دوباره رخ دهد. مسیر جدید و مستقل چارت همچنان `/v2/meetings/page` است.
- مسیرهای ناقص `/v1/organization/tree` و `/v1/admin/processmaker/sync-users` حذف شدند؛ نسخه معتبر فقط زیر `/v2` است.
- فونت BYekanPlus اختیاری است؛ فقط وقتی فایل‌های شخصی شما در `commercial/web/fonts/byekanplus-regular.ttf` و `byekanplus-bold.ttf` موجود باشند، CSS درخواست آن‌ها را می‌دهد. در غیر این صورت مرورگر بدون ۴۰۴های تکراری از Tahoma استفاده می‌کند. فایل فونت در GitHub قرار نگرفته است.
- `commercial/Start-Preview.ps1` مسیر venv شما را در کنار `AI-Agent-Lab-GitHub` پیدا می‌کند و پیش از اجرای Preview، تست‌های آفلاین را اجرا می‌کند. اگر تست شکست بخورد، Preview را اجرا نمی‌کند.

دستورات Windows PowerShell (اگر سرور پورت ۸۰۹۰ باز است، ابتدا در همان پنجره Ctrl+C):

```powershell
$repo = "D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab-GitHub"
git -C $repo pull --ff-only origin main
cd $repo
powershell -ExecutionPolicy Bypass -File .\commercial\Start-Preview.ps1
```

پیش‌نمایش: http://127.0.0.1:8090 . برای خروج Ctrl+C. خطاهای جدید تست یا uvicorn را با نام فایل و خط مربوطه نگه دارید؛ هیچ پاکسازی/reset مخرب در repository لازم نیست.

## درخواست امن تغییر رمز کاربر (کد اضافه شده؛ نیازمند IdP واقعی)

پنل SysAdmin اکنون برای کاربر معمولیِ فعال و لینک‌شده، دکمه درخواست ارسال ایمیل تغییر رمز را دارد: `POST /v2/admin/directory/{pm_uid}/send-password-update`. ابتدا نقش امضاشده SysAdmin و حق مدیریت در SQL تأیید می‌شود، سپس Keycloak با سرویس‌توکن **صرفاً روی سرور** ایمیل `UPDATE_PASSWORD` را ایجاد می‌کند؛ API هیچ رمز اولیه، لینک بازیابی یا توکن ورود به مرورگر تحویل نمی‌دهد. مقدار `SubjectID` مقصد باید UUID واقعی Keycloak باشد؛ شناسه‌های `lab-alice` و مشابه رد می‌شوند.

این عملکرد پیش‌فرض خاموش است. فقط مسئول IT می‌تواند در محیط ایزوله و پس از تنظیم realm HTTPS همسان با issuer، سرویس‌توکن محدود و مجوزهای لازم، `COMMERCIAL_KEYCLOAK_ADMIN_ENABLED=1` و `COMMERCIAL_KEYCLOAK_ADMIN_REALM_URL` را تنظیم کند. `COMMERCIAL_KEYCLOAK_ADMIN_TOKEN` نباید در GitHub، مرورگر، لاگ یا گفتگو قرار گیرد. بازیابی رمز واقعی، ارسال ایمیل و سیاست ممیزی/نرخ درخواست باید با Keycloak/IT آزموده شود؛ افزودن این endpoint به معنی ورود سازمانی آماده یا امکان مدیریت کامل هویت نیست.

**نتیجه اجرایی:** اکنون رابط ساختگی برای بررسی قابل استفاده است؛ سامانه عملیاتی چندشرکتی با ProcessMaker و Keycloak تا زمان اجرای تست‌ها و تنظیم منبع‌های واقعی آماده نیست.


## تکمیل رابط قابل بررسی مدیران در پیش‌نمایش

در منوی نمونه پورت ۸۰۹۰ اکنون دو صفحه مستقل `نمونه SysAdmin` و `نمونه GodAdmin` اضافه شده‌اند. صفحه اول فهرست پنج کاربر ساختگی، نمونه چارت و مدیر مستقیم، نقش کارشناس/مدیر، نمایش وضعیت اتصال SQL/PM/Keycloak و تنظیم نمایشی نام/رنگ را دارد. صفحه دوم مشتریان کاملاً ساختگی، داشبورد ماژول‌ها و فرم **فقط پیش‌نمایش مشخصات درخواست لایسنس** را نشان می‌دهد.

این دو صفحه احراز هویت یا عملیات واقعی را شبیه‌سازی **امنیتی** نمی‌کنند؛ نقش/رنگ فقط حافظه همین صفحه را تغییر می‌دهد. Reset Password، ارتباط زنده ProcessMaker، ساخت حساب، صدور امضای لایسنس، فعال‌سازی مجوز در SQL و تنظیم رمز اتصال فقط در پنل متصل و پس از تنظیم هویت/مجوزهای واقعی قابل بررسی خواهند بود. فعال‌کردن پورت ۸۰۹۰ روی شبکه عمومی ممنوع است.
