# ورود یکپارچه آوان

پس از راه‌اندازی اولیه، کاربر سازمانی و GodAdmin از **یک صفحه ورود** استفاده می‌کنند. نشانی `http://127.0.0.1:8188/` مهمان را به Keycloak هدایت می‌کند. صفحه اول فقط نام کاربری و رمز عبور دارد و صفحه دوم فقط وقتی باز می‌شود که حساب برنامه Authenticator (TOTP) داشته باشد؛ کد آن شش‌رقمی است. حساب بدون TOTP پس از رمز صحیح وارد فضای کار می‌شود. فرم ورود راهنمای نصب ندارد. پس‌زمینه همان تصویر نخست «Cinematic teal meeting intelligence network» است.

ورود اصلی همچنان OIDC Authorization Code همراه PKCE است؛ رمز کاربران سازمانی به API برنامه ارسال نمی‌شود. حفاظت Keycloak در برابر حدس رمز در Realm فعال است. حساب محلی `godadmin` فقط برای نصب اولیه یا بازیابی از میزبان نصب باقی می‌ماند: پس از رمز درست، اگر TOTP محلی فعال باشد، یک نشست موقت ۱۲۰ثانیه‌ای صادر و صفحه دوم کد باز می‌شود. نشست مدیریتی نهایی فقط بعد از تأیید کد ساخته می‌شود؛ تلاش‌ها محدود هستند. پس از اتصال هویت GodAdmin به حساب سازمانی، ورود محلی از وب غیرفعال است.


## حفاظت ضدربات Hybrid: Cloudflare + ALTCHA

ورود آوان از حالت **Hybrid Anti-Bot** استفاده می‌کند. مسیر اصلی **Cloudflare Turnstile Managed** است و اگر Script یا Challenge کلادفلر در بازه کوتاه تعیین‌شده آماده نشود، خطا بدهد، یا سرویس خارجی در دسترس نباشد، رابط کاربری بدون توقف به **ALTCHA Self-Hosted** سوییچ می‌کند. کاربر یک کارت امنیتی واحد می‌بیند و لازم نیست Provider را انتخاب کند.

در توسعه محلی، `scripts/init-security.ps1` علاوه بر Secret داخلی ALTCHA، کلیدهای رسمی تست Turnstile را ایجاد می‌کند تا Hybrid بدون تهیه کلید واقعی قابل آزمایش باشد. در محیط HTTPS Production، کلیدهای تست Cloudflare نادیده گرفته می‌شوند و تا زمانی که کلید واقعی تنظیم نشده باشد، ALTCHA به‌عنوان مسیر امن داخلی فعال می‌ماند.

برای فعال‌کردن Cloudflare واقعی در Production، یک Turnstile Widget از نوع Managed در Cloudflare بسازید و Site Key و Secret Key را با دستور زیر در Docker Secret ذخیره کنید:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\configure-turnstile.ps1 `
  -SiteKey '<CLOUDFLARE_TURNSTILE_SITE_KEY>' `
  -SecretKey '<CLOUDFLARE_TURNSTILE_SECRET_KEY>'
```

Secret Key هرگز به Browser ارسال نمی‌شود. Browser فقط Site Key عمومی را می‌گیرد. Token کلادفلر قبل از بررسی رمز در Backend با Siteverify اعتبارسنجی می‌شود. اگر مسیر Cloudflare در Browser ناموفق شود، Challenge امضاشده ALTCHA داخل شبکه Docker حل و با کانتینر `antibot` Verify می‌شود. Challenge محلی زمان‌دار، Action-bound و یک‌بارمصرف است و Replay رد می‌شود.

در Bootstrap GodAdmin و Keycloak هر دو همین ترتیب اجرا می‌شود: **Cloudflare Primary → ALTCHA Fallback → Username/Password → TOTP در صورت فعال بودن**. اگر Cloudflare در Browser موفق شود ولی Verify سمت سرور رد شود، تلاش بعدی همان صفحه به‌صورت خودکار با ALTCHA انجام می‌شود تا اختلال خروجی سرور به اینترنت باعث قفل‌شدن Login نشود.

در Login دسکتاپ کارت به‌صورت جمع‌شده نمایش داده می‌شود. با ورود موس روی کارت، فرم باز می‌شود و با خروج موس خودکار جمع می‌شود؛ برای باز و بسته‌شدن نیازی به کلیک بیرون کارت نیست. روی موبایل/تاچ دکمه «ورود» به‌عنوان fallback رابط کاربری باقی می‌ماند.

## آوردن نسخه روی ویندوز

```powershell
Set-Location 'D:\A Project\17 meeting ai agent\Azure\AVAN-Git-Live-20260927'
git pull --ff-only
docker compose -p avan-production -f .\compose.yaml -f .\compose.pm-local.yaml up -d --build --wait
docker compose -p avan-production -f .\compose.yaml -f .\compose.pm-local.yaml ps
Start-Process 'http://127.0.0.1:8188/'
```

در نصب تازه، جریان `avan-browser` از Realm import می‌شود و ترتیب Username Password Form سپس زیرفرایند Conditional OTP را دارد. برای **Realm موجود** فایل import به‌تنهایی جریان Browser را عوض نمی‌کند. اگر قبلاً جریان `avan-browser` را فعال کرده‌اید، همان Provider با نسخه جدید JAR به Hybrid Anti-Bot متصل می‌شود و نیازی به حذف Realm یا کاربران نیست. اگر Realm موجود شما هنوز Browser flow دیگری دارد، در کنسول Keycloak قسمت **Authentication → Flows**، بعد از مرحله Username Password Form زیرفرایند **Conditional** با Condition - User Configured و OTP Form را کنترل کنید. اگر لازم شد جریان را به Browser binding متصل کنید. دو حساب آزمایشی دارای TOTP و بدون TOTP را در پنجره خصوصی مرورگر بررسی کنید.

فونت‌های مجوزدار YekanBakh در Git نیستند. اگر از نسخه قبلی فایل فونت دارید، سه وزن Regular، SemiBold و Bold را در `commercial/web/production/fonts/` و `infra/keycloak/themes/avan/login/resources/fonts/` قرار دهید؛ در غیر این صورت فونت جایگزین نمایش داده می‌شود.
