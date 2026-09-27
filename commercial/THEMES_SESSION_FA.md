# فونت، پوسته‌ها و ورود آوان

این نسخه از سه وزن Regular، SemiBold و Bold فونت YekanBakh ارسالی شما استفاده می‌کند. فایل‌های فونت در مخزن خصوصی پروژه قرار دارند و از شبکهٔ بیرونی دریافت نمی‌شوند. پنج پوستهٔ روشن، تیره، سبز، آبی و قرمز در بالای فضای کار و پنل GodAdmin قابل انتخاب‌اند. انتخاب هر مرورگر در همان مرورگر ذخیره می‌شود.

## به‌روزرسانی نسخهٔ آزمایشی ویندوز با Git

Docker Desktop را اجرا کنید. اگر در مخزن محلی تغییرات ثبت‌نشده دارید، پیش از `git switch`/`git pull` آن‌ها را تعیین تکلیف کنید؛ این دستورها تغییراتتان را حذف نمی‌کنند. مسیر `$source` را پوشهٔ نصب فعلی دارای `.secrets` قرار دهید. Docker volumeها را پاک نکنید.

```powershell
$repo = 'D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab-GitHub'
$source = 'D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab-Release-BundledSQL'
$branch = 'feature/pm-native-agent-store-20260922'
Set-Location $repo
git fetch origin $branch
if ($LASTEXITCODE -ne 0) { throw 'Git fetch failed.' }
git show-ref --verify --quiet "refs/heads/$branch"
if ($LASTEXITCODE -eq 0) { git switch $branch } else { git switch --track -c $branch "origin/$branch" }
if ($LASTEXITCODE -ne 0) { throw 'Switch branch failed; check uncommitted changes.' }
git pull --ff-only origin $branch
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed; do not reset local changes.' }
if (-not (Test-Path -LiteralPath '.secrets')) {
    if (-not (Test-Path -LiteralPath (Join-Path $source '.secrets'))) { throw 'Source secrets missing.' }
    Copy-Item -LiteralPath (Join-Path $source '.secrets') -Destination '.secrets' -Recurse
}
powershell -ExecutionPolicy Bypass -File .\scripts\init-security.ps1
if ($LASTEXITCODE -ne 0) { throw 'Secret initialization failed.' }
docker info
if ($LASTEXITCODE -ne 0) { throw 'Start Docker Desktop first.' }
docker compose -p avan-production -f .\compose.yaml -f .\compose.pm-local.yaml config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose configuration failed.' }
docker compose -p avan-production -f .\compose.yaml -f .\compose.pm-local.yaml up -d --build --wait
if ($LASTEXITCODE -ne 0) { throw 'Containers did not become healthy.' }
docker compose -p avan-production -f .\compose.yaml ps -a
Invoke-RestMethod 'http://127.0.0.1:8188/health'
Start-Process 'http://127.0.0.1:8188/'
```

این دستور همان پروژهٔ Docker با نام `avan-production` را به‌روزرسانی و volumeهای موجود را حفظ می‌کند. رمزها را در پیام یا Git منتشر نکنید. فونت‌های این مخزن خصوصی برای همین نصب در پروژه موجودند.

## رفتار نشست

- بعد از ۱۰ دقیقه بدون فعالیت کاربر در فضای کار، نشست آوان پایان می‌یابد. تایمرهای پایش خودکار این مدت را تمدید نمی‌کنند. هنگام استفادهٔ فعال، آوان توکن کوتاه‌عمر Keycloak را سمت سرور تمدید می‌کند.
- دکمهٔ «خروج»، نشست‌های آوان همان حساب را باطل، cookie را حذف و مرورگر را به خروج Keycloak هدایت می‌کند. درخواست ورود بعدی نیز با `prompt=login` نیازمند ورود مجدد است.
- پنل جداگانهٔ GodAdmin همچنان در `http://127.0.0.1:8188/admin/` است و نشست مستقل دارد.
- قالب صفحهٔ ورود Keycloak برای نصب تازهٔ realm به‌صورت خودکار انتخاب می‌شود. اگر realm از قبل در دیتابیس Keycloak وجود دارد، import مجدد تنظیمات موجود را عوض نمی‌کند؛ برای هماهنگ شدن فرم وارد کردن نام کاربری و رمز، در **Realm settings → Themes → Login theme** گزینهٔ `avan` را انتخاب کنید. صفحهٔ آغازین خود آوان و فونت و پوسته‌ها بدون این کار به‌روزرسانی می‌شوند.

## آزمون پذیرش

۱. در فضای کار هر پنج پوسته را انتخاب کنید، صفحه را تازه‌سازی کنید و باقی ماندن پوسته را بررسی کنید.
۲. پس از ورود، بیش از پنج دقیقه با صفحه کار کنید؛ نشست باید برقرار بماند.
۳. بدون هیچ فعالیتی ده دقیقه صبر کنید؛ درخواست بعدی باید ورود دوباره بخواهد.
۴. «خروج» را بزنید؛ بازکردن دوبارهٔ آوان و کلیک روی ورود باید صفحهٔ ورود Keycloak را نشان دهد.

در صورت مشکل، خروجی `docker compose -p avan-production -f .\compose.yaml ps -a` و `docker compose -p avan-production -f .\compose.yaml logs --tail=80 avan keycloak` را بررسی کنید؛ رمزها را در خروجی ارسالی حذف کنید.
