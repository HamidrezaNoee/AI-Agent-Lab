# برنامه صدور لایسنس آوان

لایسنس با امضای ECDSA P-256 به سازمان و شناسه نصب مقید می‌شود و شامل تاریخ انقضا، سقف کاربران فعال و ماژول‌هاست. کلید خصوصی فقط نزد صادرکننده می‌ماند. مشتری فایل لایسنس و کلید عمومی را دریافت می‌کند.

## برنامه رومیزی

روی رایانه صادرکننده دارای Python و Tk:

```powershell
python -m pip install "cryptography>=44,<47"
python -m commercial.licensing.studio
```

پنجره فارسی امکان ایجاد کلید خصوصی رمزدار، تعیین سازمان/شناسه نصب، تعداد کاربران، مدت به روز، ماژول‌ها و خروجی لایسنس را دارد. برای تاریخ انقضای مشخص، کادر مدت را خالی کنید و تاریخ UTC را وارد کنید. این برنامه Python است؛ فایل EXE امضاشده ویندوز تولید نشده است.

## ابزار مستقل Docker

```powershell
docker build -f commercial/Dockerfile.license -t avan-license-studio .
# پوشه را خارج از checkout مخزن ایجاد کنید
$issuer = 'D:\AVAN-Issuer'
docker run --rm -it -v "${issuer}:/issuer" avan-license-studio keygen --private /issuer/private.pem --public /issuer/public.pem
```

رمز کلید حداقل ۱۲ نویسه است و تعاملی پرسیده می‌شود. کلید را فقط یک‌بار بسازید و پشتیبان امن نگه دارید. ابزار فایل موجود را بازنویسی نمی‌کند.

پیش از ساخت image مشتری، کلید عمومی ناشر را در سورس pin کنید:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/pin-license-public-key.ps1 -PublicKey D:\AVAN-Issuer\public.pem
docker compose up -d --build
```

فایل fingerprint پیش‌فرض مخزن placeholder است؛ نصب تا جایگزینی آن توسط ناشر، لایسنس دلخواه را معتبر نمی‌پذیرد. private.pem را در مخزن یا image مشتری قرار ندهید. برای ارتقا، همان کلید عمومی قبلی را حفظ کنید.

پس از تنظیم سازمان در پنل مدیریت، Tenant ID و Installation ID را از پنل بردارید:

```powershell
docker run --rm -it -v "${issuer}:/issuer" avan-license-studio issue --private /issuer/private.pem --tenant YOUR_TENANT_ID --installation YOUR_INSTALLATION_ID --customer "نام سازمان" --max-users 100 --days 365 --modules 1,2,3,4 --out /issuer/customer-365.license
docker run --rm -v "${issuer}:/issuer" avan-license-studio inspect --public /issuer/public.pem --license /issuer/customer-365.license --tenant YOUR_TENANT_ID --installation YOUR_INSTALLATION_ID --active-users 10
```

`--days` مدت اعتبار از لحظه صدور است؛ به‌جای آن `--expires 2027-09-22T00:00:00Z` قابل استفاده است. مجوز نامحدود فقط با انتخاب آگاهانه `--expires unlimited` صادر شود.

ماژول‌ها: ۱ دستیار مدیریتی، ۲ دبیر جلسه، ۳ گزارش/BI، ۴ پایش. در تب لایسنس پنل GodAdmin، public.pem و محتوای فایل license را وارد کنید. فعال‌سازی لایسنس قبل از پذیرش اولین کاربر ممکن است.

## اعمال محدودیت

اعتبار امضا، سازمان، نصب و زمان در سرور بررسی می‌شود. سقف روی **نگاشت‌های فعال کاربران آوان** است، نه همه کاربران ProcessMaker یا تعداد نشست‌های هم‌زمان. فعال‌سازی کاربر جدید تحت قفل تراکنش انجام می‌شود؛ پر بودن ظرفیت، کاربر جدید را رد می‌کند و کاربران قبلی را حذف نمی‌کند. GodAdmin می‌تواند حساب نگاشت‌شده را غیرفعال کند و ظرفیت آزاد کند. کاهش ظرفیت در لایسنس جدید ابتدا نیازمند کاهش کاربران فعال است.

انقضا دسترسی عملیاتی Agent را می‌بندد؛ پنل GodAdmin برای تمدید باقی می‌ماند و گردش کار ProcessMaker مختل نمی‌شود. اعتبار زمانی به ساعت UTC سرور وابسته است؛ مقابله با مالک متخاصم سرور و دستکاری ساعت بدون سرویس اعتبارسنجی مستقل، تضمین نمی‌شود. این نسخه سرویس فعال‌سازی اینترنتی و ابطال برخط لایسنس ندارد.
