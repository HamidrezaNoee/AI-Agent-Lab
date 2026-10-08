# اتصال چند BPMS و فضای کار GodAdmin

پس از ورود، آوان یک Workspace یکپارچه دارد و «مدیریت سامانه» از Side Menu همان Workspace باز می‌شود. در Information Architecture جدید، **ProcessMaker یک BPMS است و Tab مستقل ندارد**.

## معماری مدیریت تنظیمات

منوی اصلی مدیریت سامانه فقط این بخش‌ها را دارد:

- وضعیت سامانه: Dashboard فقط‌خواندنی سلامت؛ هیچ Secret یا Connection از اینجا ویرایش نمی‌شود.
- اتصالات BPMS: مالک واحد تمام موتورهای BPMS، شامل ProcessMaker.
- بانک Agent: SQL Server اختصاصی Agent.
- هوش مصنوعی: Provider/Model/Voice.
- سازمان و دسترسی: اطلاعات سازمان، Identity و کاربران.
- لایسنس: Installation/Tenant/License.

هر Setting فقط یک Owner Page دارد. Dashboard و صفحه‌های دیگر اجازه ویرایش دوباره همان Secret را نمی‌دهند.

## اتصالات BPMS

صفحه «اتصالات BPMS» یک Catalog واحد از اتصال‌ها دارد. برای هر اتصال عملیات زیر موجود است:

- تست اتصال
- ویرایش
- کپی تنظیمات
- حذف
- فعال‌سازی/غیرفعال‌سازی در صورت پشتیبانی موتور

دکمه «اتصال جدید» ابتدا نوع BPMS و نام دلخواه را می‌گیرد. اتصال فقط بعد از Test موفق ذخیره می‌شود.

### ProcessMaker

ProcessMaker به‌صورت Native Provider مدیریت می‌شود و دو کانال دارد:

1. MySQL فقط‌خواندنی برای داده‌های Process/Case/Task/Meeting.
2. OAuth API برای Directory/Users و قابلیت‌های API.

فرم ProcessMaker اطلاعات MySQL، Base URL، Workspace، Client ID/Secret و در اتصال اولیه Username/Password را می‌گیرد. آوان خودش Access Token و Refresh Token را می‌گیرد، API را تست می‌کند و Secretها را رمزگذاری‌شده ذخیره می‌کند. Password حساب ProcessMaker ذخیره نمی‌شود.

چند پروفایل ProcessMaker قابل ثبت است. یکی به‌عنوان اتصال Active انتخاب می‌شود و برای سازگاری Runtime فعلی، تنظیمات همان Profile به تنظیمات عملیاتی MySQL/OAuth فعال اعمال می‌شود. اتصال قدیمی نسخه قبل نیز هنگام اولین خواندن Catalog بدون حذف داده به Profile «ProcessMaker اصلی» مهاجرت می‌کند.

«کپی تنظیمات» برای ProcessMaker در Backend انجام می‌شود و Password/Token/Client Secret به Browser بازگردانده نمی‌شوند.

### موتورهای دیگر

برای Camunda، Appian، UiPath، ServiceNow و موتورهای دیگر، اتصال از Adapter سازگار با AVAN REST v1 انجام می‌شود. Adapter باید حداقل این Endpointها را با HTTPS و Bearer Token فقط‌خواندنی ارائه کند:

- `GET /avan/v1/identity`
- `GET /avan/v1/bi/processes`

Tenant پاسخ Identity باید دقیقاً با Tenant سازمان در آوان برابر باشد. داده‌های عملیاتی Adapter در بانک Agent کپی نمی‌شوند.

## راهنمای تنظیمات

راهنمای طولانی داخل فرم‌ها نمایش داده نمی‌شود. در هر بخش فقط دکمه 💡 وجود دارد. کلیک روی آن یک Tab جدید در `/admin/help/` باز می‌کند که آموزش را به‌صورت شماتیک، مسیر مرحله‌ای، محل تهیه مقادیر و نکات امنیتی نمایش می‌دهد.

صفحه Help داده زنده یا Secret دریافت نمی‌کند و صرفاً محتوای آموزشی است.

## اجرای نسخه روی ویندوز

در مخزن Git که شاخه `feature/pm-native-agent-store-20260922` را دنبال می‌کند:

```powershell
Set-Location 'D:\A Project\17 meeting ai agent\Azure\AVAN-Git-Live-20260927'
git pull --ff-only
docker version
docker compose -p avan-production -f .\compose.yaml -f .\compose.pm-local.yaml up -d --build --wait
docker compose -p avan-production -f .\compose.yaml -f .\compose.pm-local.yaml ps
Invoke-RestMethod 'http://127.0.0.1:8188/health'
Start-Process 'http://127.0.0.1:8188/'
```

اگر Docker Desktop اجرا نشده است ابتدا آن را باز کنید و بعد `docker version` را تکرار کنید. ورود GodAdmin از صفحه اصلی با حساب سازمانی انجام می‌شود؛ بخش تنظیمات از دکمه «تنظیمات GodAdmin» در بالا در دسترس است.
