# ورود یکپارچه آوان

پس از راه‌اندازی اولیه، کاربران و GodAdmin از **یک صفحه ورود Keycloak** استفاده می‌کنند. نشانی آوان `http://127.0.0.1:8188/` است؛ مهمان به `/auth/login` هدایت می‌شود و فرم سازمانی نام کاربری، رمز عبور و کپچای تصویر را نشان می‌دهد. تصویر بدون تماس با سرویس بیرونی ساخته می‌شود؛ پاسخ تا دو دقیقه و فقط یک بار در همان نشست ورود معتبر است. Keycloak با فعال بودن حفاظت در برابر حدس رمز و محدودیت تلاش در هر نشست، پاسخ کپچا را قبل از بررسی رمز اعتبارسنجی می‌کند. اگر حساب TOTP تنظیم کرده باشد، پس از رمز صحیح صفحه جداگانه کد Authenticator می‌آید؛ حساب بدون TOTP آن صفحه را نمی‌بیند. نام کاربری و رمز به API آوان ارسال نمی‌شوند و روند OIDC Authorization Code همراه PKCE حفظ شده است.

حساب محلی `godadmin` **تنها برای راه‌اندازی اولیه یا بازیابی روی میزبان نصب** باقی می‌ماند؛ فرم آن نیز کپچای یک‌بارمصرف و محدودیت پنج تلاش دارد. پس از اتصال حساب GodAdmin به هویت سازمانی، ورود محلی وب غیرفعال می‌شود. صفحه ورود و فرم مرحله OTP راهنمای نصب ندارند. راهنمای اتصال و پیکربندی همچنان داخل پنل تنظیمات در دسترس است.

## نصب تازه

```powershell
Set-Location 'D:\A Project\17 meeting ai agent\Azure\AVAN-Git-Live-20260927'
git pull --ff-only
powershell -ExecutionPolicy Bypass -File .\scripts\init-security.ps1
docker compose -p avan-production -f .\compose.yaml -f .\compose.pm-local.yaml up -d --build --wait
docker compose -p avan-production -f .\compose.yaml -f .\compose.pm-local.yaml ps
Start-Process 'http://127.0.0.1:8188/'
```

فرایند نصب تازه `avan-browser` را از فایل import همان Realm ثبت می‌کند. پس از تکمیل راه‌اندازی GodAdmin و اتصال هویت سازمانی، ورود اصلی خودکار نمایش داده می‌شود.

## ارتقای نصب موجود Keycloak

`--import-realm` در Keycloak، Realm موجود را جایگزین نمی‌کند؛ بنابراین فایل JSON جدید **جریان ورود Realm از قبل موجود را عوض نمی‌کند**. پس از بالا آمدن نسخه جدید، در کنسول مدیریت Keycloak نصب موجود و Realm `avan`:

1. Authentication → Flows → Create flow؛ نام `avan-browser`، نوع `Basic flow`.
2. در جریان ساخته‌شده Add step → **AVAN username, password and image challenge** با Requirement برابر **Required**.
3. Add sub-flow → نام `avan-conditional-otp` با Requirement برابر **Conditional**؛ زیر آن Add step → **Condition - User Configured** با Required و **OTP Form** با Required. مرحله شرط باید پیش از OTP باشد.
4. در فهرست Flows، از منوی جریان `avan-browser` گزینه **Bind flow** را بزنید و به **Browser flow** متصل کنید. قبل از خروج از کنسول با یک پنجره خصوصی ورود دارای OTP و یک حساب آزمایشی بدون OTP را امتحان کنید. در فرم اول کپچا باید دیده شود، فقط حساب دارای OTP باید صفحه کد ببیند.
5. از حذف Realm یا import با overwrite استفاده نکنید؛ کاربران و تنظیمات موجود باید حفظ شوند.

در فاصله ساخت image تا فعال‌سازی جریان، فرم جدید به‌طور موقت با جریان ورود قبلی Keycloak اجرا می‌شود و کپچا را نشان نمی‌دهد؛ ارتقا را با فعال‌سازی flow بالا کامل کنید. اگر Step سفارشی در فهرست دیده نمی‌شود، build کانتینر Keycloak را بررسی کنید: `docker compose -p avan-production -f .\compose.yaml -f .\compose.pm-local.yaml logs --tail 100 keycloak`.

برای تشخیص وضعیت واقعی بعد از ورود، ورود را در پنجره خصوصی آزمایش کنید و درخواست POST فرم ورود را بررسی کنید: کپچا باید توسط Keycloak رد شود اگر اشتباه وارد شده یا همان پاسخ دوباره ارسال شده باشد. اجرای محلی این مخزن به Docker و دسترسی به Keycloak در سیستم مقصد نیاز دارد؛ آزمون‌های کد به‌تنهایی جایگزین این بررسی نیستند.
