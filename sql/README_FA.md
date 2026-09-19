# راه‌اندازی SQL آزمایشی Meeting Agent

**هرگز Seed را روی دیتابیس عملیاتی `EnterpriseProcess2` اجرا نکنید.** مقصد فقط `EnterpriseProcess2_AI_Test` است؛ این بانک جدید فقط اسکیمای MTG را دریافت می‌کند، نه رکوردهای واقعی. شناسه‌های Seed پرونده واقعی در ProcessMaker نمی‌سازند.

1. با SSMS به `DESKTOP-GJI3D8L\SQLSERVER2022` متصل شوید. `sql/00_create_EnterpriseProcess2_AI_Test.sql` را برای ساخت بانک خالی اجرا کنید.
2. فایل `01_create_MTG_schema_AI_Test.sql` را از بسته دیتاست به پوشه `sql/` کپی و در SSMS اجرا کنید. این DDL از ساختار ارسالی کاربر به بانک تست تغییر مسیر داده و بخش ساخت user را جدا کرده است.
3. فایل `seed_1100_meetings_EnterpriseProcess2_AI_Test.sql` را از بسته کپی و با اکانت مدیر **فقط در بانک تست** اجرا کنید. سپس `03_verify_AI_test_seed.sql` را اجرا کنید؛ تعداد هدف: ۱۱۰۰ جلسه، ۶۶۰۰ مصوبه، ۸۸۰۰ اقدام، ۱۷۶۰۰ گزارش و ۱۷۶۰۰ Review.
4. در صورت وجود Login سروری `AI_MeetingAgent`، `sql/02_grant_AI_test_reader.sql` را اجرا کنید. اگر وجود ندارد با رمز قوی تازه در SSMS بسازید؛ این حساب صرفاً برای SELECT است، نه اجرای Seed.
5. PowerShell: `$env:SQL_SERVER='.\SQLSERVER2022'`، `$env:SQL_DATABASE='EnterpriseProcess2_AI_Test'`، `$env:SQL_USER='AI_MeetingAgent'` و `SQL_PASSWORD` را به‌صورت امن با `Read-Host -AsSecureString` تنظیم کنید. اتصال را با `python -c "from db import get_connection; c=get_connection(); print(c.execute('SELECT DB_NAME()').fetchone()[0]); c.close()"` تست کنید.
6. `python .\05_sql_tool_agent.py` را اجرا کنید و `MeetingID` واقعی یکی از رکوردهای پیشوند `SIM-MTG-A-` در خروجی اعتبارسنجی را سؤال کنید؛ شناسه ۳۰ ممکن است متعلق به رکورد قبلی باشد.

این repo از ابتدا خالی بوده است. فایل SQL حجیم Seed و DDL کامل را از بستهٔ ارائه‌شده در چت با `git add sql/` و `git push` روی سیستم خودتان به این مخزن اضافه کنید. قبل از push بررسی کنید `.env`، API key، پسورد و بکاپ واقعی به staging نرفته باشد.
