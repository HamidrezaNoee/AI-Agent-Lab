# پنل متصل آزمایشی آوان — OAuth 2.0 / OIDC + PKCE

این بخش **کد پنل وب متصل به API موجود** است. برخلاف پیش‌نمایش مستقل پورت ۸۰۹۰، هیچ هویت یا مجوزی را شبیه‌سازی نمی‌کند؛ هر درخواست جلسه، سند، گزارش و ماژول باید با Bearer ACCESS token واقعی از ارائه‌دهنده هویت HTTPS امضا شود و در API و SQL آزمایشی مجوزسنجی گردد.

**وضعیت فعلی: پیاده‌سازی کد و تست‌های آفلاین، نه اتصال کامل به یک ارائه‌دهنده هویت واقعی.** تنظیمات واقعی Identity Provider، کلیدهای عمومی، ثبت OAuth public SPA client و ایجاد عضویت کاربران واقعی هنوز دریافت/اجرا نشده‌اند. قبل از این‌ها، پنل فقط پیام «ورود تنظیم نشده» نشان می‌دهد؛ این حالت درست و امن است.

## قرارداد ارائه‌دهنده هویت

- یک ارائه‌دهنده هویت معتبر با `issuer` و `JWKS` پایدار HTTPS و امضای RS256 برای **ACCESS token**، نه صرفاً ID token.
- توکن دسترسی باید دارای `iss`, `aud`, `sub`, `iat`, `exp` و ادعای `tenant_id` معتبر و مورد اعتماد صادرکننده باشد؛ طول عمر هر توکن حداکثر یک ساعت. API صحت همه این‌ها را بررسی می‌کند و صرف وجود `tenant_id` به‌معنای عضویت نیست.
- یک OAuth **Public Browser/SPA** client با Authorization Code Flow و `PKCE S256`، بدون client secret در مرورگر؛ Token endpoint باید `CORS` برای origin پنل را برای public client پشتیبانی کند.
- Redirect URI دقیق: `http://127.0.0.1:8088/portal/` (یا اگر به‌جای IP از localhost استفاده می‌کنی، همان URL دقیق را نزد IdP ثبت کن). Origin مربوطه را در تنظیمات CORS صادرکننده مجاز کن.
- کاربر واقعی یا آزمایشی باید در جدول Membership همان `tenant_id` با **`sub` دقیق صادرشده** ثبت و فعال باشد، اشتراک سازمان اعتبار داشته باشد و مجوز صریح جلسه/سند به او اختصاص داده شده باشد. هیچ‌گاه `sub` دلخواه را در JWT خودساخته برای پنل واقعی جایگزین نکن.

## تنظیمات نمونه با مقادیر جایگزین (تنها پس از دریافت مشخصات واقعی)

```powershell
$repo = "D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab-GitHub"
$python = "D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab\.venv\Scripts\python.exe"
git -C $repo pull --ff-only origin main
cd $repo

$env:COMMERCIAL_MODE = "lab"
$env:COMMERCIAL_SQL_SERVER = "DESKTOP-GJI3D8L\SQLSERVER2022"
$env:COMMERCIAL_SQL_DATABASE = "EnterpriseProcess2_AI_Test"
$env:COMMERCIAL_SQL_USER = "AI_CommercialReader"
$pw = Read-Host "LAB Commercial SQL password" -AsSecureString
$env:COMMERCIAL_SQL_PASSWORD = [System.Net.NetworkCredential]::new("", $pw).Password

$env:COMMERCIAL_OIDC_ISSUER = "https://YOUR-AUTHORIZED-IDENTITY-PROVIDER/issuer/"
$env:COMMERCIAL_OIDC_AUDIENCE = "YOUR-REGISTERED-MEETING-API-AUDIENCE"
$env:COMMERCIAL_OIDC_JWKS_URL = "https://YOUR-AUTHORIZED-IDENTITY-PROVIDER/.well-known/jwks.json"
$env:COMMERCIAL_OIDC_AUTHORIZATION_URL = "https://YOUR-AUTHORIZED-IDENTITY-PROVIDER/authorize"
$env:COMMERCIAL_OIDC_TOKEN_URL = "https://YOUR-AUTHORIZED-IDENTITY-PROVIDER/token"
$env:COMMERCIAL_OIDC_CLIENT_ID = "YOUR-REGISTERED-PUBLIC-SPA-CLIENT-ID"
$env:COMMERCIAL_OIDC_SCOPES = "openid profile"
# Only if your IdP requires an extra authorization audience parameter:
# $env:COMMERCIAL_OIDC_AUTH_AUDIENCE = "YOUR-REGISTERED-MEETING-API-AUDIENCE"

$env:COMMERCIAL_CHAT_ENABLED = "0"
$env:COMMERCIAL_WEB_PORTAL_ENABLED = "1"
& $python -m uvicorn commercial.api:app --host 127.0.0.1 --port 8088
```

پس از **جایگزینی تمام مقادیر نمونه با اطلاعات واقعی و تأیید راه‌اندازی IdP**، صفحه `http://127.0.0.1:8088/portal/` را در همان رایانه باز کن. این فرایند را با مقادیر `YOUR-...` اجرا نکن؛ پنل وارد نخواهد شد. هرگز این پورت را روی `0.0.0.0`، سرور عمومی یا Reverse Proxy اینترنتی منتشر نکن.

توکن در حافظه همان برگه مرورگر نگهداری می‌شود، نه localStorage و نه فایل یا دیتابیس؛ فقط وضعیت موقت PKCE/State در sessionStorage هنگام رفت‌وبرگشت به IdP نگهداری و سپس حذف می‌شود. با بارگذاری مجدد صفحه، کاربر ممکن است لازم باشد دوباره ورود کند. خروج از این پنل توکن ذخیره‌شده در حافظه صفحه را پاک می‌کند؛ **خروج سراسری از IdP/لغو توکن در سطح صادرکننده را پیاده‌سازی نمی‌کند**.

## امنیت و وضعیت قابلیت‌ها

`GET /portal/config` فقط تنظیمات عمومی OAuth ثبت‌شده توسط مدیر سرور را عرضه می‌کند و رمز SQL/کلید خصوصی یا Client Secret را در مرورگر افشا نمی‌کند. در نبود تنظیمات معتبر HTTPS، پاسخ `503` باز می‌گرداند و ورود ممکن نیست. مسیر `/portal/` به‌صورت پیش‌فرض خاموش است و فقط در محیط آزمایشی، با `COMMERCIAL_WEB_PORTAL_ENABLED=1` و روی اتصال localhost مجاز می‌شود.

پس از ورود معتبر، UI با API اصلی کار می‌کند: `/v1/me`, `/v1/modules`, `/v1/meetings/page`, `/v1/chat/preview`, `/v1/secretary/preparation/{meeting_id}`, `/v1/analytics/status-overview`, `/v1/monitoring/overdue` و `PUT /v1/admin/modules/{module_code}`. نمایش یا پنهان‌کردن منو **به‌تنهایی کنترل امنیتی نیست**؛ API مجوز هر درخواست را مجدداً بررسی می‌کند. ویرایش ProcessMaker، ارسال اعلان، پرداخت، صدور واقعی مجوز و پاسخ هوش مصنوعی خارجی در این مرحله همچنان غیرفعال‌اند.

برای **بازبینی فوری ظاهر و سناریوها بدون IdP** از فایل `commercial/REVIEW_PREVIEW_FA.md` و پیش‌نمایش مستقل پورت ۸۰۹۰ استفاده کن. تست آفلاین کد پنل متصل: `python -m unittest discover -s commercial/tests -v`. تست ورود با IdP واقعی منوط به در اختیارداشتن تنظیمات/حساب آزمایشی معتبر است.
