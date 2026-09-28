# ورود یکپارچه آوان

پس از راه‌اندازی اولیه، کاربر سازمانی و GodAdmin از **یک صفحه ورود** استفاده می‌کنند. نشانی `http://127.0.0.1:8188/` مهمان را به Keycloak هدایت می‌کند. صفحه اول فقط نام کاربری و رمز عبور دارد و صفحه دوم فقط وقتی باز می‌شود که حساب برنامه Authenticator (TOTP) داشته باشد؛ کد آن شش‌رقمی است. حساب بدون TOTP پس از رمز صحیح وارد فضای کار می‌شود. فرم ورود راهنمای نصب ندارد. پس‌زمینه همان تصویر نخست «Cinematic teal meeting intelligence network» است.

ورود اصلی همچنان OIDC Authorization Code همراه PKCE است؛ رمز کاربران سازمانی به API برنامه ارسال نمی‌شود. حفاظت Keycloak در برابر حدس رمز در Realm فعال است. حساب محلی `godadmin` فقط برای نصب اولیه یا بازیابی از میزبان نصب باقی می‌ماند: پس از رمز درست، اگر TOTP محلی فعال باشد، یک نشست موقت ۱۲۰ثانیه‌ای صادر و صفحه دوم کد باز می‌شود. نشست مدیریتی نهایی فقط بعد از تأیید کد ساخته می‌شود؛ تلاش‌ها محدود هستند. پس از اتصال هویت GodAdmin به حساب سازمانی، ورود محلی از وب غیرفعال است.

## آوردن نسخه روی ویندوز

```powershell
Set-Location 'D:\A Project\17 meeting ai agent\Azure\AVAN-Git-Live-20260927'
git pull --ff-only
docker compose -p avan-production -f .\compose.yaml -f .\compose.pm-local.yaml up -d --build --wait
docker compose -p avan-production -f .\compose.yaml -f .\compose.pm-local.yaml ps
Start-Process 'http://127.0.0.1:8188/'
```

در نصب تازه، جریان `avan-browser` از Realm import می‌شود و ترتیب Username Password Form سپس زیرفرایند Conditional OTP را دارد. برای **Realm موجود** فایل import به‌تنهایی جریان Browser را عوض نمی‌کند. اگر قبلاً جریان `avan-browser` را طبق نسخه قبلی فعال کرده‌اید، شناسه مرحله قدیمی حفظ می‌شود و در این نسخه بدون کپچا رمز را بررسی می‌کند؛ نیاز به حذف Realm یا کاربران نیست. اگر Realm موجود شما هنوز Browser flow دیگری دارد، در کنسول Keycloak قسمت **Authentication → Flows**، بعد از مرحله Username Password Form زیرفرایند **Conditional** با Condition - User Configured و OTP Form را کنترل کنید. اگر لازم شد جریان را به Browser binding متصل کنید. دو حساب آزمایشی دارای TOTP و بدون TOTP را در پنجره خصوصی مرورگر بررسی کنید.

فونت‌های مجوزدار YekanBakh در Git نیستند. اگر از نسخه قبلی فایل فونت دارید، سه وزن Regular، SemiBold و Bold را در `commercial/web/production/fonts/` و `infra/keycloak/themes/avan/login/resources/fonts/` قرار دهید؛ در غیر این صورت فونت جایگزین نمایش داده می‌شود.
