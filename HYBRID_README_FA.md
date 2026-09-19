# مرحله ۲: Agent ترکیبی جلسات و اسناد ساختگی (فقط تست)

## مرزبندی
- بانک عملیاتی `EnterpriseProcess2` را تغییر ندهید. مقصد فقط `EnterpriseProcess2_AI_Test` است.
- نمونه سند `sample_docs/fictional_customs_workload.txt` کاملاً ساختگی است؛ برای اسناد واقعی/محرمانه هنوز کنترل دسترسی فردی، محرمانگی، حذف داده و تأیید شرکت پیاده‌سازی نشده است.
- قابلیت اسناد: Chunking + نگهداری نسخه و شناسه منبع؛ با `--embed` می‌توان برای هر قطعه ساختگی Embedding ایجاد کرد. ابزار `knowledge_tools.py` بردارهای موجود را همراه با شواهد واژگانی در یک مجموعه آزمایشی کوچک رتبه‌بندی می‌کند. بدون Embedding، بازیابی واژگانی است. این روش هنوز نمایه برداری مقیاس‌پذیر یا تضمین بازیابی همه شواهد ندارد.
- محیط CLI صرفاً نمونه اولیه است؛ ورود کاربران جداگانه و دسترسی بر اساس هویت کاربر ندارد.

## نصب پایگاه دانش آزمایشی
1. با SSMS و Windows Authentication به `.\\SQLSERVER2022` (همان Instance فعلی) وصل شوید.
2. فایل `sql/04_create_AI_knowledge_schema.sql` را از مخزن باز و یک بار در SSMS اجرا کنید. فقط دو جدول AI.Document و AI.DocumentChunk را در بانک آزمایشی می‌سازد. به SQL Login خواندنی `AI_MeetingAgent` مجوز SELECT روی دو جدول می‌دهد.
3. در PowerShell پروژه فعلی، SQL_SERVER و SQL_DATABASE را تنظیم کنید:

```powershell
$env:SQL_SERVER = ".\SQLSERVER2022"
$env:SQL_DATABASE = "EnterpriseProcess2_AI_Test"
```

4. فایل نمونه ساختگی را به‌صورت صریح با حساب Windows دارای مجوز نوشتن در TEST وارد کنید:

```powershell
python .\07_ingest_test_document.py --file ".\sample_docs\fictional_customs_workload.txt" --meeting-no "SIM-MTG-A-000824" --embed
```

پرچم `--embed` اختیاری است و **متن قطعات سند ساختگی** را برای دریافت Embedding به API OpenAI می‌فرستد و ممکن است هزینه API داشته باشد؛ فقط روی این سند ساختگی آزمایش کنید. بدون این پرچم، بازیابی واژگانی فعال است. اگر سند را قبلاً بدون بردار وارد کرده‌اید، اجرای همان فرمان با `--embed` بردارهای قطعات موجود را اضافه می‌کند.\n\n`--meeting-no` اختیاری است؛ در صورت استفاده باید شماره یک جلسه آزمایشی موجود باشد. برای سند عمومی آن را حذف کنید. با اجرای دوباره بدون تغییر محتوا و همان ارتباط جلسه، رکورد تکراری ایجاد نمی‌شود؛ با تغییر فایل، نسخه جدید ساخته شده و نسخه قبلی از بازیابی جاری کنار می‌رود.

5. بررسی در SSMS:

```sql
USE [EnterpriseProcess2_AI_Test];
SELECT d.DocumentID, d.OriginalFileName, d.Title, d.VersionNo,
       d.IsCurrent, d.IsSynthetic, d.RelatedMeetingID, COUNT(c.ChunkID) AS ChunkCount
FROM AI.Document d JOIN AI.DocumentChunk c ON c.DocumentID=d.DocumentID
GROUP BY d.DocumentID, d.OriginalFileName, d.Title, d.VersionNo,
         d.IsCurrent, d.IsSynthetic, d.RelatedMeetingID;
```

6. برای اجرای Agent، اطمینان یابید SQL_USER و SQL_PASSWORD همان حساب فقط‌خواندنی، و OPENAI_API_KEY تنظیم شده باشند:

```powershell
python -m py_compile .\06_meeting_ai_agent.py .\07_ingest_test_document.py
python -m unittest discover -s tests -v
python .\06_meeting_ai_agent.py
```

پرسش نمونه: «برای جلسه ۳۹۰ تعداد اقدامات بسته، باز و معوق را از SQL بگو و مراحل ماتریس ظرفیت کارشناسان گمرکی را از سند نمونه با شناسه DOC نقل کن؛ فرق اطلاعات عملیاتی و متن ساختگی را روشن کن.»

## چگونگی کار
- `management_kpis`: COUNT و زمان مبنا را با SQL Server محاسبه می‌کند. رقم کل را از نمونه ۱۵تایی `list_overdue_actions` استنتاج نمی‌کند.
- `search_knowledge_documents`: فقط قطعات اسناد ساختگی جاری را بازیابی می‌کند؛ اگر Embedding وجود داشته باشد، رتبه‌بندی برداری+واژگانی و در غیر این صورت بازیابی واژگانی انجام می‌شود. ارجاع هر قطعه به شکل `DOC:<DocumentID>:v<VersionNo>:c<ChunkNo>` به همراه نام فایل، نسخه و بازه کاراکتری است. بازه کاراکتری شماره صفحه Word نیست.
- پرسش ترکیبی باید ابزار داده عملیاتی و ابزار سند را هر دو فراخوانی کند و منابع را تفکیک کند.
- متن بازیابی‌شده برای Agent *داده غیرقابل‌اعتماد* است، نه دستور جدید برای اجرای ابزار یا تغییر مجوز.

## محدودیت‌های پیش از استفاده سازمانی
1. SSO و کنترل مجوز هر کاربر برای رکوردهای SQL و هر قطعه سند لازم است.
2. پذیرش PDF، OCR و تصاویر، و پردازش نسخه‌دار فایل‌های ضمیمه فعلاً وجود ندارد.
3. Chunking فعلی بر اساس طول و هم‌پوشانی متن است؛ تقسیم‌بندی معنایی و ارزیابی Recall هنوز لازم است.
4. Embedding در آزمایشگاه اختیاری است، ولی جست‌وجوی برداری کنونی تمام قطعات را در Python بررسی می‌کند و سقف ۵۰۰۰ قطعه فعال دارد. برای داده سازمانی باید نمایه برداری/متنی مقیاس‌پذیر، فیلتر سطح دسترسی **پیش از بازیابی** و ارزیابی کیفیت جست‌وجو اضافه شود.
5. هیچ ابزار نوشتنی در Agent ارائه نشده؛ ایجاد یا اصلاح اقدام واقعی باید بعداً با کنترل دسترسی، تأیید انسانی و Audit Trail جداگانه پیاده‌سازی شود.
