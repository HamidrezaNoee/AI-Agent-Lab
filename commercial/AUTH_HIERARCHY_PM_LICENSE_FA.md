# Milestone 9 — Identity, hierarchy, ProcessMaker sync and licensing

این مرحله الگوی امنیت و لایسنس را از Organization Portal به AI Meeting Agent منتقل می‌کند، ولی منبع داده و مدل دسترسی جلسات مخصوص این محصول است.

## Role model

- GodAdmin: نقش سازنده/مالک محصول (LIMAK). مدیریت لایسنس، Installation ID، Edition/Features و تنظیمات محرمانه سازنده. به‌صورت پیش‌فرض مجوز خواندن محتوای محرمانه جلسات مشتری را ندارد.
- SysAdmin: مدیر سیستم سازمان مشتری. مدیریت اتصال SQL/ProcessMaker، ظاهر/لوگو/نام شرکت، کاربران، reset password از طریق IdP، sync کاربران و چارت، و مشاهده تمام جلسات همان Tenant.
- Manager: مدیر سازمانی. جلسه‌ای را می‌بیند اگر خودش در آن دخیل باشد یا یکی از کاربران زیر درخت سازمانی او در آن جلسه دبیر، رئیس، اقدام‌کننده یا Participant باشد. این دسترسی فقط در Tenant خودش است.
- Expert: فقط جلساتی که خودش دبیر، رئیس، اقدام‌کننده یا Participant است.
- نقش و چارت در SQL محصول enforce می‌شوند؛ مخفی‌کردن منو در UI کنترل امنیتی محسوب نمی‌شود.

## ProcessMaker sync

commercial/processmaker_sync.py فقط جدول USERS را با ستون‌های غیرمحرمانه می‌خواند. USR_PASSWORD عمداً انتخاب نمی‌شود. منبع PM با کاربر MySQL فقط‌خواندنی تنظیم می‌شود. Sync اولیه، کاربران موجودی را که قبلاً به Subject IdP متصل شده‌اند به‌روز می‌کند و کاربران جدید را new_unprovisioned گزارش می‌کند. ساخت login جدید باید توسط SysAdmin و IdP/Keycloak انجام شود تا ProcessMaker نتواند با ساخت یک کاربر، خودش دسترسی AI ایجاد کند.

Endpoint: POST /v1/admin/processmaker/sync-users. هیچ credential پروسس‌میکر از HTTP body دریافت نمی‌شود؛ credential فقط server-side secret است.

## Organization tree and meeting scope

Migration commercial/sql/15_identity_hierarchy_authorization_TEST_ONLY.sql در دیتابیس ایزوله تست این جداول را اضافه می‌کند: UserDirectory, OrganizationNode, UserOrganizationAssignment, MeetingParticipantIndex, SystemSetting, SyncRun, AuditEvent. تمام جداول Tenant-bound زیر RLS قرار می‌گیرند. SystemSetting به SQL reader عمومی SELECT داده نمی‌شود چون محل تنظیمات حساس است.

fn_subject_scope زیرمجموعه‌های Manager را از چارت محاسبه می‌کند. fn_can_view_meeting دخالت مستقیم یا دخالت فرد زیرمجموعه را کنترل می‌کند. SysAdmin کل Tenant را می‌بیند. GodAdmin فقط در صورت grant صریح به جلسه می‌تواند محتوای مشتری را بخواند.

GET /v1/meetings/page از این authorization v2 استفاده می‌کند. GET /v1/organization/tree نیز چارت قابل مشاهده نقش جاری را برمی‌گرداند.

## License Studio

commercial/licensing/studio.py به‌همراه commercial/licensing/codec.py الگوی Organization Portal را دنبال می‌کنند: ECDSA P-256، private key فقط نزد LIMAK، public key در نصب مشتری، bind به Installation ID، ظرفیت کاربر، expiry، edition و features. هیچ private key یا development bypass در repository وجود ندارد.

نسخه آفلاین CLI/GUI ویندوزی ابزار موجود است؛ برای بسته نصب مستقل EXE و صدور/فعال‌سازی روی سیستم مشتری هنوز تست و بسته‌بندی لازم است. فایل قدیمی commercial/license_studio.py فقط به همین ابزار اصلی ارجاع می‌دهد و توکن ناسازگار مستقلی صادر نمی‌کند.

## ترتیب نصب SQL (فقط بانک آزمایشی)

**مسیر ۱۵/۱۶ آزمایشی قدیمی بازنشسته شده و نباید اجرا شود.** آن فایل‌ها با نقش‌های قبلی و ساختار جدید DirectoryUser تداخل داشتند. مسیر پشتیبانی‌شده جدید در commercial/PROCESSMAKER_ORGPORTAL_INTEGRATION_FA.md شرح داده شده و از 19_directory_hierarchy_TEST_ONLY.sql آغاز می‌شود. مراحل ۱۹ تا ۲۷ فقط در EnterpriseProcess2_AI_Test و بعد از تأیید وابستگی‌ها، با حساب TEST DBA قابل اجرا هستند. Migrationها، شناسه‌های PM واقعی یا حساب‌های مدیریتی را به‌صورت خودکار ایجاد نمی‌کنند. بانک عملیاتی ProcessMaker/EnterpriseProcess نباید تغییر کند.

## Font

فایل‌های BYekanPlus توسط کاربر برای UI ارسال شده‌اند. فایل TTF در این commit بازنشر نمی‌شود. هنگام build/deploy باید فایل‌های دارای مجوز به‌صورت asset محلی در package نصب شوند و CSS فقط به asset همان package اشاره کند؛ از CDN عمومی برای فونت سازمانی استفاده نشود.
