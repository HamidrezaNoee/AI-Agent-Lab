# بارگذاری ۱۰۰۸ سناریوی خودرویی در ProcessMaker آزمایشی

این مجموعه شامل ۱۰۰۸ جلسه و ۴۰۳۲ اقدام در ۲۱ حوزه صنعت خودرو است. عنوان، شرح و ترکیب مسئله/حوزه/شرکت هر جلسه یکتا است. ساختار گزارش‌ها مشترک است؛ سناریوها از ترکیب کنترل‌شده ۸ مسئله و ۶ زمینه عملیاتی ساخته شده‌اند، نه ۱۰۰۸ داستان مستقل نگارش‌شده با مدل. شرکت‌ها و مستندات فرضی‌اند. فایل واقعی PDF در مجموعه وجود ندارد.

هر جلسه دستور جلسه، شرکت‌کنندگان، مباحث، تصمیمات، مسئول، موعد، اولویت، وابستگی، تاریخچه گزارش، بررسی دبیر و نتیجه مورد انتظار دارد. تاریخ مبنای فایل تحویلی ۲۰۲۶-۰۹-۲۳ است؛ برای آزمون نسبت به روز نصب، مجموعه را دوباره تولید کنید. نتایج مورد انتظار تأخیر به تاریخ مبنا وابسته‌اند.

## آماده‌سازی

۱. یک workspace آزمایشی جداگانه و نسخه پشتیبان آماده کنید. دو PMX نهایی Native همراه تحویل را در آن Import کنید و UIDهای فرایند و کارها را حفظ کنید. شناسه‌های مورد انتظار در `processmaker_import.py` هستند. این ابزار به نسخه قدیمی EnterpriseProcess یا کلاس‌های PHP سفارشی متصل نمی‌شود.

۲. کاربران آزمایشی فعال را در ProcessMaker ایجاد کنید. دبیر را به کار آغازین فرایند جلسه و مسئولان را به کار آغازین فرایند اقدام اختصاص دهید. کاربر OAuth اجراکننده باید اجازه REST و ایجاد پرونده از طرف کاربران انتخاب‌شده را داشته باشد. فرم `mapping.json` را با UID واقعی ۳۲کاراکتری تکمیل کنید؛ نام کاربری به‌جای UID معتبر نیست. می‌توان برای شروع چند نقش را به یک کاربر آزمایشی اختصاص داد؛ برای تحلیل عملکرد واحدها، کاربران و واحدهای مجزا تعریف کنید.

۳. فایل JSON و mapping را در یک پوشه، مثلاً `D:\AVAN-TestData` استخراج کنید. Token دسترسی OAuth همان workspace را آماده کنید؛ ابزار آن را تعاملی می‌گیرد و در checkpoint ذخیره نمی‌کند.

## روش Docker در PowerShell

از ریشه مخزن جدید:

```powershell
docker build -f commercial/Dockerfile.scenarios -t avan-scenarios .
$testData = 'D:\AVAN-TestData'
# فقط بررسی محلی؛ هیچ تماس با ProcessMaker انجام نمی‌شود
docker run --rm -v "${testData}:/data" avan-scenarios --dataset AVAN_1008_Automotive_Scenarios_FA.json --mapping mapping.json --limit 5
```

ابتدا پنج جلسه (۲۵ پرونده با اقدامات) را بارگذاری کنید. نشانی و workspace را با محیط واقعی **آزمایشی** جایگزین کنید:

```powershell
docker run --rm -it -v "${testData}:/data" avan-scenarios --dataset AVAN_1008_Automotive_Scenarios_FA.json --mapping mapping.json --base-url https://pm-test.example.org --workspace workflow_test --confirm-test-workspace workflow_test --checkpoint checkpoint.json --limit 5 --apply
```

بعد از مشاهده پنج جلسه و بررسی اتصال والد/فرزندان، همان دستور را با `--limit 1008` و **همان checkpoint، مجموعه و mapping** اجرا کنید. نتیجه نهایی ۵۰۴۰ پرونده است. پنج جلسه قبلی دوباره ساخته نمی‌شوند. اجرا را از دو رایانه یا با دو checkpoint متفاوت هم‌زمان شروع نکنید.

اگر وب ProcessMaker آزمایشی فقط HTTP دارد، نشانی مثلاً `http://PM-TEST-HOST:81` و گزینه `--allow-http` لازم است. این پورت مربوط به REST وب است، نه MySQL. ابزار redirect را دنبال نمی‌کند.

## روش Python و تولید مجدد

Python این ابزار روی رایانه ابزار یا کانتینر اجرا می‌شود؛ PHP 5.6 سرور ProcessMaker تغییر نمی‌کند.

```powershell
python -m pip install "httpx>=0.27,<1" "jdatetime>=5,<6"
python -m commercial.scenarios.generate --out D:\AVAN-TestData\AVAN_1008_Automotive_Scenarios_FA.json --as-of 2026-09-23
python -m commercial.scenarios.processmaker_import --dataset D:\AVAN-TestData\AVAN_1008_Automotive_Scenarios_FA.json --mapping D:\AVAN-TestData\mapping.json --limit 5
```

برای تولید در Docker، entrypoint را به `python` تغییر دهید و `-m commercial.scenarios.generate --out /data/...` بدهید. حذف `--as-of` تاریخ روز UTC را مبنا قرار می‌دهد.

## رفتار واقعی Import

- پرونده‌ها با REST رسمی در حالت **DRAFT** ساخته می‌شوند؛ ابزار Route یا execute-trigger را فراخوانی نمی‌کند. تنظیمات یا hookهای خود محیط ممکن است هنگام ایجاد پرونده اجرا شوند؛ محیط جداگانه لازم است.
- گزارش‌های مرحله‌ای و بررسی دبیر، داده آزمایشی متغیرهای بومی فرایند هستند. تاریخچه واقعی گردش کار، زمان چرخه و وظایف انجام‌شده جعل نمی‌شود. بنابراین BI گردش کار این موارد را پیش‌نویسِ ساخته‌شده در زمان Import می‌بیند؛ تحلیل جلسات تاریخ‌ها و وضعیت کسب‌وکاری مجموعه را می‌خواند.
- برای آزمون واقعی گردش کار، چند پرونده جداگانه را از UI ProcessMaker با کاربران واقعی تا پایان حرکت دهید. پرونده‌های مجموعه را بدون بررسی رفتار تریگر ایجاد فرزند Route نکنید؛ ممکن است فرزندهای آزمایشی از نو ایجاد شوند.
- هیچ SQL مستقیم، فایل helper سفارشی، ایمیل یا سند واقعی ارسال نمی‌شود.
- رکوردها با `AVAN_TestDatasetID`، `AVAN_TestRecordKey` و `AVAN_IsSynthetic` مشخص می‌شوند. مجموعه را در workspace عملیاتی وارد نکنید.

## توقف و ادامه مطمئن

قبل از POST، وضعیت `pending` در checkpoint ذخیره می‌شود. اگر پاسخ شبکه نامشخص باشد، ابزار خودکار POST را تکرار نمی‌کند. پرونده را در ProcessMaker از روی نشانگرها پیدا کنید و UID آن را ثبت کنید:

```powershell
# علاوه بر گزینه‌های اتصال و فایل‌های دستور --apply قبلی:
# --resolve 'AUTO-0001=REAL_32_CHARACTER_APP_UID'
# برای فرزند: --resolve 'AUTO-0001:A-001=REAL_32_CHARACTER_APP_UID'
```

ابزار نشانگرهای پرونده را دوباره می‌خواند و سپس checkpoint را اصلاح می‌کند. اگر هیچ پرونده‌ای ساخته نشده، بعد از تأیید قطعی مدیر محیط و تهیه کپی checkpoint، فقط رکورد pending مربوطه را حذف کنید و ادامه دهید. فایل `.lock` تنها پس از اطمینان از متوقف‌بودن اجرای قبلی حذف شود. حذف یا گم‌کردن checkpoint می‌تواند موجب ایجاد تکراری شود؛ آن را نگه دارید.

مرجع: [REST Cases 3.2](https://wiki.processmaker.net/3.2/REST_API_Cases/Cases)، [Case Variables 3.2](https://wiki.processmaker.net/3.2/REST_API_Cases/Case_Variables).
