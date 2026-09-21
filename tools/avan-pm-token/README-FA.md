# ابزار محلی دریافت توکن ProcessMaker برای آوان

این ابزار در ویندوز و فقط برای ProcessMaker محلی (`http://localhost:84`، Workspace `workflow`) قابل استفاده است. برنامه بعد از دریافت OAuth Access Token، API دریافت کاربران را با همان توکن تست می‌کند. فقط اگر هر دو مرحله موفق باشند، توکن را در Clipboard قرار می‌دهد؛ آن را در خروجی چاپ نمی‌کند یا در فایل ذخیره نمی‌کند.

## راه‌اندازی پس از دریافت شاخه Git

از پوشه اصلی `AI-Agent-Lab-GitHub`:

```powershell
git fetch origin feature/avan-pm-token-tool-20260921
git restore --source=FETCH_HEAD --worktree -- tools/avan-pm-token
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\avan-pm-token\Run-Tool.ps1
```

اگر فایل اجرایی در شاخه موجود باشد، اجرا می‌شود؛ در غیر این صورت اگر `go` روی ویندوز نصب باشد، فایل EXE از سورس ایجاد و اجرا می‌شود. بدون Go، ابزار معادل PowerShell اجرا می‌شود. برای ساخت دستی EXE: `cd .\tools\avan-pm-token\source; go build -o ..\Avan-ProcessMaker-Token-Tool.exe .`

مقادیر ورودی: URL اصلی `http://localhost:84`، Workspace `workflow`، Client ID و Client Secret برنامه OAuth، نام کاربری و رمز عبور حساب ProcessMaker. نام کاربری `administrator` فقط برای آزمایش اولیه است و برای محیط عملیاتی، حساب خدماتی با حداقل مجوز لازم برای فهرست کاربران باید استفاده شود.

**محدودیت:** این ابزار الزام HTTPS در فرم اتصال آوان را دور نمی‌زند. حتی با توکن صحیح، تا زمانی که ProcessMaker از نشانی HTTPS دارای گواهی مورد اعتماد کانتینر آوان در دسترس نباشد، ذخیره تنظیمات در آن فرم ممکن نیست. توکن دارای تاریخ انقضا است؛ فرم فعلی آن را خودکار تمدید نمی‌کند.

هیچ رمز، توکن، فایل `.secrets` یا کد دومرحله‌ای را به Git، لاگ یا گفتگو ارسال نکنید. پس از استفاده، با `Set-Clipboard -Value ''` کلیپ‌بورد را پاک کنید.
