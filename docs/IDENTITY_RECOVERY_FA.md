# بازیابی حساب ورود موجود

حساب اولیه نصب `godadmin` با هویت جدید ساخته‌شده در Keycloak یکی نیست. رمز موقت
حساب جدید پس از تغییر رمز دیگر قابل استفاده نیست. از نام کاربری هویت AVAN و رمز
جدیدی که در صفحه تغییر رمز تعیین کرده‌اید استفاده کنید، سپس کد همان Authenticator.
نام کاربری و رمز ProcessMaker برای ورود AVAN نیستند.

## حساب سازمانی Keycloak

فرمان زیر فقط از میزبان Docker اجرا می‌شود؛ endpoint عمومی بازیابی اضافه نشده است.
قفل تلاش‌های ناموفق را باز می‌کند و رمز یا OTP را تغییر نمی‌دهد:

```powershell
Set-Location 'D:\A Project\17 meeting ai agent\Azure\AVAN-Git-Live-20260927'
$composeArgs = @('-f', 'compose.yaml')
if (Test-Path '.\compose.pm-local.yaml') { $composeArgs += @('-f', 'compose.pm-local.yaml') }
$identityUsername = Read-Host 'نام کاربری هویت جدید AVAN'
docker compose @composeArgs exec avan python -m commercial.identity_recovery --username $identityUsername
```

اگر رمز جدید پذیرفته نشد، به جای تلاش‌های تکراری یک رمز موقت جدید تعیین کنید:

```powershell
docker compose @composeArgs exec avan python -m commercial.identity_recovery --username $identityUsername --reset-password
```

رمز در ترمینال به صورت مخفی پرسیده و دوباره تأیید می‌شود. رمز را در دستور، چت یا
فایل قرار ندهید. نقش‌ها، سازمان، Binding و کلید Authenticator حفظ می‌شوند؛ جلسات
حساب پس از تغییر رمز بسته می‌شوند. با رمز موقت و Authenticator موجود وارد شوید
و رمز دائمی تعیین کنید. فرمان حساب غیرفعال را فعال نمی‌کند و نام کاربری متفاوت
با GodAdmin متصل را رد می‌کند. اگر HTTP 403 داد، دسترسی service account باید در
Keycloak توسط مدیر میزبان بررسی شود؛ فرمان به‌طور خودکار دسترسی را افزایش نمی‌دهد.

## حساب اولیه نصب

قفل ورود اولیه پس از ۱۵ دقیقه منقضی می‌شود؛ restart سرویس AVAN نیز محدودیت موقت
حافظه را پاک می‌کند. اگر حساب واقعاً هنوز اولیه است، با `godadmin` و آخرین رمز
تعیین‌شده وارد شوید. فرمان identity_recovery برای این حساب استفاده نشود.
بازیابی اضطراری قدیمی `--reset-godadmin` اتصال هویت و MFA اولیه را پاک می‌کند؛
برای مشکل ورود هویت جدید از آن استفاده نکنید.

## باز و بسته‌شدن مستطیل

مدیریت ← تنظیمات ظاهری ← بخش رفتار Hover: «باز و بسته‌شدن خودکار مستطیل ورود».
با خاموش کردن، فرم همیشه باز می‌ماند. مرحله OTP همیشه باز است. تنظیم را ذخیره
و صفحه ورود را با Ctrl+F5 تازه کنید. پیش‌فرض برای تنظیمات قدیمی روشن است.
