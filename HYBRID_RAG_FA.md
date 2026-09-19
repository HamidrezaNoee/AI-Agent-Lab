# مرحله ۷: بازیابی اسناد در کنار SQL جلسات (نسخه آزمایشی)

**این نسخه فقط برای دیتابیس جداگانه `EnterpriseProcess2_AI_Test` و فایل‌های کاملاً ساختگی است.**
فایل‌های واقعی شرکت، اطلاعات کارکنان، مشتریان، صورت‌جلسات محرمانه و اسناد عملیاتی را وارد این بانک تست نکنید.
متن Chunkهای منتخب هنگام پاسخ به API مدل ارسال می‌شود. گزینه `--embed` نیز متن تمام Chunkهای سند انتخاب‌شده را هنگام ورود به API Embeddings می‌فرستد.

## وضعیت و محدودیت‌ها

- جداول `MTG` مرجع تعداد، وضعیت، مسئول و موعد اقدام باقی می‌مانند؛ متن اسناد از `AI.Document` و `AI.DocumentChunk` بازیابی می‌شود.
- نسخه سند با SHA-256 و `VersionNo` نگهداری می‌شود؛ فقط نسخه `IsCurrent=1` وارد پاسخ می‌شود و نسخه قبلی برای حسابرسی حفظ می‌شود.
- `SourceLocation` در این MVP به شکل بازه `StartChar..EndChar` از **متن استخراج‌شده** است؛ شماره صفحه Word نیست.
- در حالت `--embed` از `text-embedding-3-small` استفاده می‌شود؛ نگهداری بردار به صورت float32 در SQL Server 2022 و رتبه‌بندی آن در Python است. جست‌وجوی واژگانی نیز برای Chunkهای فاقد بردار در دسترس است.
- این نسخه برای **حداکثر ۵۰۰۰ Chunk فعال** طراحی شده و اگر از سقف عبور کند نتیجه ناقص نمی‌دهد؛ باید موتور نمایه‌گذاری و جست‌وجوی مقیاس‌پذیر اضافه شود.
- PDF اسکن‌شده، OCR، تشخیص شماره صفحه DOCX، کنترل دسترسی واقعی برای هر کاربر وب، پردازش پس‌زمینه و ویرایش ProcessMaker هنوز پیاده‌سازی نشده‌اند.

## اجرا روی ویندوز / SQL Server فعلی

۱. ابتدا Agent را در PowerShell با عبارت `exit` متوقف کنید. در SSMS به `.\\SQLSERVER2022` با **Windows Authentication** متصل شوید. بانک آزمایشی `EnterpriseProcess2_AI_Test` از قبل باید موجود و شامل داده‌های قبلی باشد. **اسکریپت‌های ساخت بانک یا Seed را دوباره اجرا نکنید.**

۲. در SSMS به ترتیب دو فایل زیر را اجرا کنید. اجرای دوباره آنها با شرط‌های وجود جدول/ستون طراحی شده است:

```
sql/04_create_AI_knowledge_schema.sql
sql/05_add_AI_embeddings.sql
```

۳. در همان پنجره PowerShell که رمز SQL و کلید OpenAI را قبلاً تنظیم کرده‌اید:

```powershell
$repo = "D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab-GitHub"
$project = "D:\A Project\17 meeting ai agent\Azure\AI-Agent-Lab"
git -C $repo pull --ff-only origin main
Copy-Item "$repo\06_meeting_ai_agent.py" "$project\06_meeting_ai_agent.py" -Force
Copy-Item "$repo\knowledge_tools.py" "$project\knowledge_tools.py" -Force
Copy-Item "$repo\07_ingest_documents.py" "$project\07_ingest_documents.py" -Force
Copy-Item "$repo\sample_docs\synthetic_import_procedure.md" "$project\sample_docs\synthetic_import_procedure.md" -Force
cd $project
$env:SQL_SERVER = ".\SQLSERVER2022"
$env:SQL_DATABASE = "EnterpriseProcess2_AI_Test"
```

پیش از کپی فایل نمونه، پوشه مقصد را در صورت نبودن بسازید:

```powershell
New-Item -ItemType Directory -Path "$project\sample_docs" -Force | Out-Null
```

اگر در اجرای `Copy-Item` خطای نبود پوشه مقصد گرفتید، دستور `New-Item` را **قبل از** کپی نمونه اجرا و فقط همان `Copy-Item` را تکرار کنید.

۴. وابستگی‌ها و کنترل Syntax / تست‌های بدون دیتابیس:

```powershell
python -m pip install python-docx
python -m py_compile .\06_meeting_ai_agent.py .\knowledge_tools.py .\07_ingest_documents.py
# Optional after copying tests/:
python -m unittest discover -s tests -v
```

۵. ابتدا یک فایل Markdown **کاملاً ساختگی** نمونه را با Windows Authentication در بانک تست وارد کنید. برای آزمایش جست‌وجوی معنایی، `--embed` نیز اضافه کنید (به API OpenAI درخواست فرستاده و هزینه دارد):

```powershell
python .\07_ingest_documents.py --file .\sample_docs\synthetic_import_procedure.md --synthetic --embed
```

برای ورود فایل Word آزمایشی به جای نمونه، آدرس یک فایل `.docx` مجاز را بدهید؛ در این مرحله PDF پشتیبانی نمی‌شود. گزینه `--meeting-id 19` اختیاری است و فقط درصورتی به کار می‌رود که **شناسه واقعی** آن جلسه آزمایشی را در SQL بررسی کرده باشید.

۶. بدون مصرف API چت، فقط بازیابی اسناد را آزمایش کنید. اگر Chunk برداری موجود باشد، این تست یک درخواست Embedding برای سؤال ایجاد می‌کند:

```powershell
python .\knowledge_tools.py "برای رفع مغایرت VIN چه مدارکی لازم است؟"
```

در خروجی باید شناسه‌ای مانند `DOC:1:v1:c1` و `source_file`، `document_version`، `start_character` و `passage` دیده شود. عددها ممکن است متفاوت باشند.

۷. در SSMS اسکریپت `sql/06_verify_AI_knowledge.sql` را برای بررسی نسخه‌ها، تعداد Chunkها و طول بردارها اجرا کنید؛ سپس Agent را اجرا کنید:

```powershell
python .\06_meeting_ai_agent.py
```

نمونه سؤال سندی: «طبق راهنمای آزمایشی مغایرت شماره شاسی، چه مدارکی باید جمع‌آوری شود؟ نام سند و شناسه Chunk را هم بیاور.»

نمونه سؤال ترکیبی: «برای جلسه آزمایشی با شناسه ۱۹، اقدامات باز را از SQL بگو و جداگانه توضیح بده طبق سند آزمایشی درباره تطبیق VIN چه مدارکی لازم است. منبع هر قسمت را مشخص کن.»

**فراموش نکنید:** یک سند عمومی نمونه الزاماً سند پیوست‌شده به جلسه ۱۹ نیست؛ Agent باید این دو را تفکیک کند.

## مراحل تکمیلی برای بهره‌برداری سازمانی

برای ورود اسناد واقعی و استقرار وب باید ابتدا هویت کاربر، مجوز سطح سند و جلسه پیش از بازیابی، سیاست نگهداری و ارسال اطلاعات به API، صحت نسخه سند، صف پردازش اسناد، تست‌های بازیابی و ثبت Audit تعریف و اجرا شوند. تا پیش از آن از این نسخه فقط با اسناد غیرواقعی استفاده کنید.
