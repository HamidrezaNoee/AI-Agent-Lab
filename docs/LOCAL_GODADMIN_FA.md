# حفظ GodAdmin اولیه برای مدیریت دائمی

به درخواست مالک، حساب ساخته‌شده هنگام نصب برای مدیریت دائمی کافی است. ساخت
GodAdmin جدید و اتصال دستی OIDC از صفحه هویت حذف شده است. در «حساب اصلی GodAdmin»
نام کاربری، رمز فعلی، رمز جدید اختیاری و کد Authenticator را وارد کنید. پس از
ذخیره باید دوباره وارد شوید. رمز اولیه نصب، MFA، داده‌ها و تنظیمات موجود با
به‌روزرسانی دوباره تولید نمی‌شوند. کاربران معمولی همچنان از Keycloak استفاده می‌کنند.
GodAdmin محلی فعلاً دسترسی مدیریت سامانه دارد؛ برای انجام وظیفه فرد دیگر در BPMS
هویت آن فرد را جعل نمی‌کند.

## نصب فعلی که GodAdmin دیگری به آن متصل شده

```powershell
Set-Location 'D:\A Project\17 meeting ai agent\Azure\AVAN-Git-Live-20260927'
git checkout feature/pm-native-agent-store-20260922
git pull --ff-only
$composeArgs = @('-f', 'compose.yaml')
if (Test-Path '.\compose.pm-local.yaml') { $composeArgs += @('-f', 'compose.pm-local.yaml') }
docker compose @composeArgs up -d --build avan
docker compose @composeArgs exec avan python -m commercial.local_godadmin --delete-other-accounts
docker compose @composeArgs restart avan
Start-Process 'http://127.0.0.1:8188/auth/login'
```

اگر نصب override دیگری دارد همان ترکیب Compose را حفظ کنید. فرمان، رمز و کد
Authenticator حساب محلی اولیه را به صورت مخفی می‌پرسد؛ رمز هویت دیگری را وارد
نکنید. ابتدا قابل استفاده بودن حساب محفوظ را بررسی می‌کند. سپس اتصال GodAdmin
قبلی را برمی‌دارد و هویت‌های انسانی دیگر در realm داخلی `avan` را حذف می‌کند.
حساب‌های سرویس زیرساخت حفظ می‌شوند. حساب محلی در بانک تنظیمات AVAN است و در
فهرست حذف Keycloak نیست. رمز، نام کاربری فعلی و Authenticator آن حفظ می‌شوند.
Restart AVAN، نشست‌های حافظه حساب‌های قبلی را می‌بندد.

این فرمان حساب‌های ورود دیگر AVAN را حذف می‌کند، نه کاربران ProcessMaker، پرونده‌ها،
صورتجلسه‌ها، اتصال‌ها و تاریخچه کسب‌وکار. داده تاریخی منتسب به افراد حذف‌شده
عمداً باقی می‌ماند. فرمان عمومی HTTP برای حذف دسته‌جمعی اضافه نشده است.
اگر حذف بیرونی نیمه‌تمام شود، حساب محلی همچنان محفوظ است؛ پیام تعداد حذف را
نشان می‌دهد و فرمان را می‌توان برای تکمیل دوباره اجرا کرد.

برای صرفاً حفظ GodAdmin و بدون حذف حساب‌ها، گزینه `--delete-other-accounts` را
حذف کنید. حساب محلی، رمز جدید و TOTP تأییدشده باید از قبل داشته باشد؛ هیچ حساب
پیش‌فرض با رمز ثابت یا عبور بدون MFA اضافه نشده است.
