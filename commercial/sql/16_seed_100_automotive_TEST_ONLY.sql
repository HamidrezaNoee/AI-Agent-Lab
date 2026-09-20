/* Generated from commercial/datasets/100_automotive_meeting_scenarios_FA.json.
   Synthetic 100 automotive meetings + 300 actions, tenant A fixture ONLY.
   TEST ADMIN + TEST DATABASE ONLY. No operational MTG/ProcessMaker writes.
   This intentionally persists FICTIONAL data; do not run twice.
*/
USE [EnterpriseProcess2_AI_Test];
GO
SET XACT_ABORT ON;
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test'
 THROW 59400,'Wrong database: fictional 100-scenario import only.',1;
IF ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0)<>1
 THROW 59401,'Run synthetic import as test DBA.',1;
IF OBJECT_ID(N'AgentProduct.ActionIndex',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.MeetingGrant',N'U') IS NULL
 THROW 59402,'Run module and action migrations 14 and 15 first.',1;
GO
DECLARE @t uniqueidentifier='11111111-1111-4111-8111-111111111111';
BEGIN TRY
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=@t;
 BEGIN TRAN;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.Tenant WHERE TenantID=@t)
  OR NOT EXISTS(SELECT 1 FROM AgentProduct.Membership
                WHERE TenantID=@t AND SubjectID=N'lab-alice')
  THROW 59403,'Run prior TEST fixture 12 first.',1;
 IF EXISTS(SELECT 1 FROM AgentProduct.MeetingIndex
           WHERE TenantID=@t AND MeetingID BETWEEN 910001 AND 910100)
  OR EXISTS(SELECT 1 FROM AgentProduct.ActionIndex
           WHERE TenantID=@t AND MeetingID BETWEEN 910001 AND 910100)
  THROW 59404,'100-scenario import already present; do NOT overwrite.',1;
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910001,N'LAB-910001',N'ارزیابی تأمین‌کننده خودروهای هیبریدی','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910001,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910001,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «ارزیابی تأمین‌کننده خودروهای هیبریدی» همراه با ثبت مستندات قابل رسیدگی.',N'بازرگانی','2026-09-12 12:00:00',100,1),
 (@t,910001,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «ارزیابی تأمین‌کننده خودروهای هیبریدی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-14 15:00:00',100,1),
 (@t,910001,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «ارزیابی تأمین‌کننده خودروهای هیبریدی».',N'مدیریت','2026-09-16 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910002,N'LAB-910002',N'مغایرت شرایط تحویل قرارداد CKD','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910002,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910002,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «مغایرت شرایط تحویل قرارداد CKD» همراه با ثبت مستندات قابل رسیدگی.',N'بازرگانی','2026-09-13 12:00:00',60,0),
 (@t,910002,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «مغایرت شرایط تحویل قرارداد CKD» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-15 15:00:00',35,0),
 (@t,910002,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «مغایرت شرایط تحویل قرارداد CKD».',N'مدیریت','2026-09-17 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910003,N'LAB-910003',N'تأخیر تخصیص ارز محموله SUV','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910003,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910003,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «تأخیر تخصیص ارز محموله SUV» همراه با ثبت مستندات قابل رسیدگی.',N'بازرگانی','2026-09-14 12:00:00',20,0),
 (@t,910003,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «تأخیر تخصیص ارز محموله SUV» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-16 15:00:00',0,0),
 (@t,910003,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «تأخیر تخصیص ارز محموله SUV».',N'مدیریت','2026-09-18 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910004,N'LAB-910004',N'ریسک تغییر نرخ حمل قطعات','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910004,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910004,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «ریسک تغییر نرخ حمل قطعات» همراه با ثبت مستندات قابل رسیدگی.',N'بازرگانی','2026-09-15 12:00:00',0,0),
 (@t,910004,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «ریسک تغییر نرخ حمل قطعات» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-17 15:00:00',70,0),
 (@t,910004,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «ریسک تغییر نرخ حمل قطعات».',N'مدیریت','2026-09-19 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910005,N'LAB-910005',N'مقایسه پیش‌فاکتور سه تأمین‌کننده','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910005,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910005,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «مقایسه پیش‌فاکتور سه تأمین‌کننده» همراه با ثبت مستندات قابل رسیدگی.',N'بازرگانی','2026-09-16 12:00:00',100,1),
 (@t,910005,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «مقایسه پیش‌فاکتور سه تأمین‌کننده» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-18 15:00:00',100,1),
 (@t,910005,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «مقایسه پیش‌فاکتور سه تأمین‌کننده».',N'مدیریت','2026-09-20 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910006,N'LAB-910006',N'بازنگری برنامه سفارش فصلی خودرو','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910006,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910006,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بازنگری برنامه سفارش فصلی خودرو» همراه با ثبت مستندات قابل رسیدگی.',N'بازرگانی','2026-09-17 12:00:00',60,0),
 (@t,910006,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بازنگری برنامه سفارش فصلی خودرو» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-19 15:00:00',35,0),
 (@t,910006,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بازنگری برنامه سفارش فصلی خودرو».',N'مدیریت','2026-09-21 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910007,N'LAB-910007',N'کنترل اصالت گواهی مبدأ','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910007,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910007,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کنترل اصالت گواهی مبدأ» همراه با ثبت مستندات قابل رسیدگی.',N'بازرگانی','2026-09-18 12:00:00',20,0),
 (@t,910007,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کنترل اصالت گواهی مبدأ» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-20 15:00:00',0,0),
 (@t,910007,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کنترل اصالت گواهی مبدأ».',N'مدیریت','2026-09-22 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910008,N'LAB-910008',N'مدیریت کمبود قطعات سفارش تجمیعی','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910008,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910008,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «مدیریت کمبود قطعات سفارش تجمیعی» همراه با ثبت مستندات قابل رسیدگی.',N'بازرگانی','2026-09-19 12:00:00',0,0),
 (@t,910008,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «مدیریت کمبود قطعات سفارش تجمیعی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-21 15:00:00',70,0),
 (@t,910008,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «مدیریت کمبود قطعات سفارش تجمیعی».',N'مدیریت','2026-09-23 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910009,N'LAB-910009',N'تطبیق شماره شاسی با فاکتور تجاری','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910009,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910009,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «تطبیق شماره شاسی با فاکتور تجاری» همراه با ثبت مستندات قابل رسیدگی.',N'بازرگانی','2026-09-20 12:00:00',100,1),
 (@t,910009,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «تطبیق شماره شاسی با فاکتور تجاری» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-22 15:00:00',100,1),
 (@t,910009,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «تطبیق شماره شاسی با فاکتور تجاری».',N'مدیریت','2026-09-24 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910010,N'LAB-910010',N'بررسی مهلت اعتبار اعتبارنامه خرید','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910010,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910010,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بررسی مهلت اعتبار اعتبارنامه خرید» همراه با ثبت مستندات قابل رسیدگی.',N'بازرگانی','2026-09-21 12:00:00',60,0),
 (@t,910010,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بررسی مهلت اعتبار اعتبارنامه خرید» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-23 15:00:00',35,0),
 (@t,910010,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بررسی مهلت اعتبار اعتبارنامه خرید».',N'مدیریت','2026-09-25 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910011,N'LAB-910011',N'پیگیری مجوز ثبت سفارش مدل جدید','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910011,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910011,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «پیگیری مجوز ثبت سفارش مدل جدید» همراه با ثبت مستندات قابل رسیدگی.',N'مجوزات','2026-09-22 12:00:00',20,0),
 (@t,910011,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «پیگیری مجوز ثبت سفارش مدل جدید» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-24 15:00:00',0,0),
 (@t,910011,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «پیگیری مجوز ثبت سفارش مدل جدید».',N'مدیریت','2026-09-26 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910012,N'LAB-910012',N'رفع مغایرت استاندارد آلایندگی','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910012,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910012,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «رفع مغایرت استاندارد آلایندگی» همراه با ثبت مستندات قابل رسیدگی.',N'مجوزات','2026-09-23 12:00:00',0,0),
 (@t,910012,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «رفع مغایرت استاندارد آلایندگی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-25 15:00:00',70,0),
 (@t,910012,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «رفع مغایرت استاندارد آلایندگی».',N'مدیریت','2026-09-27 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910013,N'LAB-910013',N'تکمیل پرونده تأیید نوع خودرو','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910013,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910013,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «تکمیل پرونده تأیید نوع خودرو» همراه با ثبت مستندات قابل رسیدگی.',N'مجوزات','2026-09-24 12:00:00',100,1),
 (@t,910013,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «تکمیل پرونده تأیید نوع خودرو» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-26 15:00:00',100,1),
 (@t,910013,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «تکمیل پرونده تأیید نوع خودرو».',N'مدیریت','2026-09-16 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910014,N'LAB-910014',N'تمدید مجوز واردات قطعات ایمنی','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910014,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910014,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «تمدید مجوز واردات قطعات ایمنی» همراه با ثبت مستندات قابل رسیدگی.',N'مجوزات','2026-09-25 12:00:00',60,0),
 (@t,910014,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «تمدید مجوز واردات قطعات ایمنی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-27 15:00:00',35,0),
 (@t,910014,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «تمدید مجوز واردات قطعات ایمنی».',N'مدیریت','2026-09-17 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910015,N'LAB-910015',N'هماهنگی آزمون تطابق مصرف سوخت','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910015,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910015,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «هماهنگی آزمون تطابق مصرف سوخت» همراه با ثبت مستندات قابل رسیدگی.',N'مجوزات','2026-09-26 12:00:00',20,0),
 (@t,910015,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «هماهنگی آزمون تطابق مصرف سوخت» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-14 15:00:00',0,0),
 (@t,910015,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «هماهنگی آزمون تطابق مصرف سوخت».',N'مدیریت','2026-09-18 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910016,N'LAB-910016',N'بررسی مستندات شماره‌گذاری','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910016,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910016,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بررسی مستندات شماره‌گذاری» همراه با ثبت مستندات قابل رسیدگی.',N'مجوزات','2026-09-12 12:00:00',0,0),
 (@t,910016,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بررسی مستندات شماره‌گذاری» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-15 15:00:00',70,0),
 (@t,910016,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بررسی مستندات شماره‌گذاری».',N'مدیریت','2026-09-19 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910017,N'LAB-910017',N'رفع نقص گواهی بازرسی پیش از حمل','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910017,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910017,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «رفع نقص گواهی بازرسی پیش از حمل» همراه با ثبت مستندات قابل رسیدگی.',N'مجوزات','2026-09-13 12:00:00',100,1),
 (@t,910017,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «رفع نقص گواهی بازرسی پیش از حمل» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-16 15:00:00',100,1),
 (@t,910017,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «رفع نقص گواهی بازرسی پیش از حمل».',N'مدیریت','2026-09-20 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910018,N'LAB-910018',N'برنامه اخذ تأییدیه سامانه ترمز','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910018,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910018,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «برنامه اخذ تأییدیه سامانه ترمز» همراه با ثبت مستندات قابل رسیدگی.',N'مجوزات','2026-09-14 12:00:00',60,0),
 (@t,910018,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «برنامه اخذ تأییدیه سامانه ترمز» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-17 15:00:00',35,0),
 (@t,910018,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «برنامه اخذ تأییدیه سامانه ترمز».',N'مدیریت','2026-09-21 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910019,N'LAB-910019',N'تطبیق کد تعرفه با مشخصات کالا','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910019,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910019,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «تطبیق کد تعرفه با مشخصات کالا» همراه با ثبت مستندات قابل رسیدگی.',N'مجوزات','2026-09-15 12:00:00',20,0),
 (@t,910019,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «تطبیق کد تعرفه با مشخصات کالا» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-18 15:00:00',0,0),
 (@t,910019,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «تطبیق کد تعرفه با مشخصات کالا».',N'مدیریت','2026-09-22 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910020,N'LAB-910020',N'کنترل مدارک ترخیص خودروهای برقی','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910020,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910020,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کنترل مدارک ترخیص خودروهای برقی» همراه با ثبت مستندات قابل رسیدگی.',N'مجوزات','2026-09-16 12:00:00',0,0),
 (@t,910020,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کنترل مدارک ترخیص خودروهای برقی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-19 15:00:00',70,0),
 (@t,910020,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کنترل مدارک ترخیص خودروهای برقی».',N'مدیریت','2026-09-23 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910021,N'LAB-910021',N'تأخیر ورود کانتینر به بندر','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910021,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910021,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «تأخیر ورود کانتینر به بندر» همراه با ثبت مستندات قابل رسیدگی.',N'لجستیک','2026-09-17 12:00:00',100,1),
 (@t,910021,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «تأخیر ورود کانتینر به بندر» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-20 15:00:00',100,1),
 (@t,910021,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «تأخیر ورود کانتینر به بندر».',N'مدیریت','2026-09-24 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910022,N'LAB-910022',N'مغایرت وزن اظهارنامه و بارنامه','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910022,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910022,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «مغایرت وزن اظهارنامه و بارنامه» همراه با ثبت مستندات قابل رسیدگی.',N'لجستیک','2026-09-18 12:00:00',60,0),
 (@t,910022,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «مغایرت وزن اظهارنامه و بارنامه» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-21 15:00:00',35,0),
 (@t,910022,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «مغایرت وزن اظهارنامه و بارنامه».',N'مدیریت','2026-09-25 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910023,N'LAB-910023',N'برنامه حمل زمینی محموله قطعات','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910023,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910023,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «برنامه حمل زمینی محموله قطعات» همراه با ثبت مستندات قابل رسیدگی.',N'لجستیک','2026-09-19 12:00:00',20,0),
 (@t,910023,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «برنامه حمل زمینی محموله قطعات» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-22 15:00:00',0,0),
 (@t,910023,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «برنامه حمل زمینی محموله قطعات».',N'مدیریت','2026-09-26 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910024,N'LAB-910024',N'ارزیابی خسارت بسته‌بندی باتری','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910024,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910024,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «ارزیابی خسارت بسته‌بندی باتری» همراه با ثبت مستندات قابل رسیدگی.',N'لجستیک','2026-09-20 12:00:00',0,0),
 (@t,910024,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «ارزیابی خسارت بسته‌بندی باتری» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-23 15:00:00',70,0),
 (@t,910024,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «ارزیابی خسارت بسته‌بندی باتری».',N'مدیریت','2026-09-27 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910025,N'LAB-910025',N'پیگیری تعیین مسیر گمرکی','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910025,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910025,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «پیگیری تعیین مسیر گمرکی» همراه با ثبت مستندات قابل رسیدگی.',N'لجستیک','2026-09-21 12:00:00',100,1),
 (@t,910025,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «پیگیری تعیین مسیر گمرکی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-24 15:00:00',100,1),
 (@t,910025,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «پیگیری تعیین مسیر گمرکی».',N'مدیریت','2026-09-16 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910026,N'LAB-910026',N'هماهنگی تخلیه و انبارش خودرو','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910026,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910026,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «هماهنگی تخلیه و انبارش خودرو» همراه با ثبت مستندات قابل رسیدگی.',N'لجستیک','2026-09-22 12:00:00',60,0),
 (@t,910026,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «هماهنگی تخلیه و انبارش خودرو» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-25 15:00:00',35,0),
 (@t,910026,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «هماهنگی تخلیه و انبارش خودرو».',N'مدیریت','2026-09-17 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910027,N'LAB-910027',N'کمبود ظرفیت حمل خودروی سواری','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910027,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910027,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کمبود ظرفیت حمل خودروی سواری» همراه با ثبت مستندات قابل رسیدگی.',N'لجستیک','2026-09-23 12:00:00',20,0),
 (@t,910027,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کمبود ظرفیت حمل خودروی سواری» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-26 15:00:00',0,0),
 (@t,910027,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کمبود ظرفیت حمل خودروی سواری».',N'مدیریت','2026-09-18 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910028,N'LAB-910028',N'رسیدگی به اختلاف تعداد پالت','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910028,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910028,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «رسیدگی به اختلاف تعداد پالت» همراه با ثبت مستندات قابل رسیدگی.',N'لجستیک','2026-09-24 12:00:00',0,0),
 (@t,910028,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «رسیدگی به اختلاف تعداد پالت» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-27 15:00:00',70,0),
 (@t,910028,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «رسیدگی به اختلاف تعداد پالت».',N'مدیریت','2026-09-19 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910029,N'LAB-910029',N'اصلاح زمان‌بندی ترانزیت محموله','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910029,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910029,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «اصلاح زمان‌بندی ترانزیت محموله» همراه با ثبت مستندات قابل رسیدگی.',N'لجستیک','2026-09-25 12:00:00',100,1),
 (@t,910029,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «اصلاح زمان‌بندی ترانزیت محموله» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-14 15:00:00',100,1),
 (@t,910029,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «اصلاح زمان‌بندی ترانزیت محموله».',N'مدیریت','2026-09-20 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910030,N'LAB-910030',N'کنترل هزینه دموراژ کانتینر','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910030,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910030,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کنترل هزینه دموراژ کانتینر» همراه با ثبت مستندات قابل رسیدگی.',N'لجستیک','2026-09-26 12:00:00',60,0),
 (@t,910030,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کنترل هزینه دموراژ کانتینر» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-15 15:00:00',35,0),
 (@t,910030,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کنترل هزینه دموراژ کانتینر».',N'مدیریت','2026-09-21 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910031,N'LAB-910031',N'اصلاح پیش‌بینی تقاضای کراس‌اوور','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910031,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910031,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «اصلاح پیش‌بینی تقاضای کراس‌اوور» همراه با ثبت مستندات قابل رسیدگی.',N'فروش و بازاریابی','2026-09-12 12:00:00',20,0),
 (@t,910031,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «اصلاح پیش‌بینی تقاضای کراس‌اوور» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-16 15:00:00',0,0),
 (@t,910031,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «اصلاح پیش‌بینی تقاضای کراس‌اوور».',N'مدیریت','2026-09-22 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910032,N'LAB-910032',N'بررسی تأخیر تحویل خودرو به مشتری','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910032,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910032,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بررسی تأخیر تحویل خودرو به مشتری» همراه با ثبت مستندات قابل رسیدگی.',N'فروش و بازاریابی','2026-09-13 12:00:00',0,0),
 (@t,910032,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بررسی تأخیر تحویل خودرو به مشتری» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-17 15:00:00',70,0),
 (@t,910032,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بررسی تأخیر تحویل خودرو به مشتری».',N'مدیریت','2026-09-23 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910033,N'LAB-910033',N'هماهنگی کمپین معرفی مدل جدید','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910033,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910033,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «هماهنگی کمپین معرفی مدل جدید» همراه با ثبت مستندات قابل رسیدگی.',N'فروش و بازاریابی','2026-09-14 12:00:00',100,1),
 (@t,910033,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «هماهنگی کمپین معرفی مدل جدید» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-18 15:00:00',100,1),
 (@t,910033,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «هماهنگی کمپین معرفی مدل جدید».',N'مدیریت','2026-09-24 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910034,N'LAB-910034',N'تحلیل نرخ تبدیل سرنخ‌های فروش','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910034,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910034,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «تحلیل نرخ تبدیل سرنخ‌های فروش» همراه با ثبت مستندات قابل رسیدگی.',N'فروش و بازاریابی','2026-09-15 12:00:00',60,0),
 (@t,910034,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «تحلیل نرخ تبدیل سرنخ‌های فروش» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-19 15:00:00',35,0),
 (@t,910034,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «تحلیل نرخ تبدیل سرنخ‌های فروش».',N'مدیریت','2026-09-25 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910035,N'LAB-910035',N'پیگیری شکایات قرارداد فروش','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910035,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910035,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «پیگیری شکایات قرارداد فروش» همراه با ثبت مستندات قابل رسیدگی.',N'فروش و بازاریابی','2026-09-16 12:00:00',20,0),
 (@t,910035,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «پیگیری شکایات قرارداد فروش» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-20 15:00:00',0,0),
 (@t,910035,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «پیگیری شکایات قرارداد فروش».',N'مدیریت','2026-09-26 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910036,N'LAB-910036',N'به‌روزرسانی شرایط فروش اقساطی','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910036,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910036,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «به‌روزرسانی شرایط فروش اقساطی» همراه با ثبت مستندات قابل رسیدگی.',N'فروش و بازاریابی','2026-09-17 12:00:00',0,0),
 (@t,910036,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «به‌روزرسانی شرایط فروش اقساطی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-21 15:00:00',70,0),
 (@t,910036,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «به‌روزرسانی شرایط فروش اقساطی».',N'مدیریت','2026-09-27 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910037,N'LAB-910037',N'رفع اختلاف موجودی و تعهد فروش','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910037,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910037,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «رفع اختلاف موجودی و تعهد فروش» همراه با ثبت مستندات قابل رسیدگی.',N'فروش و بازاریابی','2026-09-18 12:00:00',100,1),
 (@t,910037,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «رفع اختلاف موجودی و تعهد فروش» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-22 15:00:00',100,1),
 (@t,910037,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «رفع اختلاف موجودی و تعهد فروش».',N'مدیریت','2026-09-16 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910038,N'LAB-910038',N'بررسی عملکرد نمایندگی‌های فروش','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910038,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910038,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بررسی عملکرد نمایندگی‌های فروش» همراه با ثبت مستندات قابل رسیدگی.',N'فروش و بازاریابی','2026-09-19 12:00:00',60,0),
 (@t,910038,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بررسی عملکرد نمایندگی‌های فروش» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-23 15:00:00',35,0),
 (@t,910038,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بررسی عملکرد نمایندگی‌های فروش».',N'مدیریت','2026-09-17 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910039,N'LAB-910039',N'راهکار افزایش فروش قطعات اصلی','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910039,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910039,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «راهکار افزایش فروش قطعات اصلی» همراه با ثبت مستندات قابل رسیدگی.',N'فروش و بازاریابی','2026-09-20 12:00:00',20,0),
 (@t,910039,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «راهکار افزایش فروش قطعات اصلی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-24 15:00:00',0,0),
 (@t,910039,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «راهکار افزایش فروش قطعات اصلی».',N'مدیریت','2026-09-18 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910040,N'LAB-910040',N'برنامه اطلاع‌رسانی تغییر قیمت','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910040,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910040,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «برنامه اطلاع‌رسانی تغییر قیمت» همراه با ثبت مستندات قابل رسیدگی.',N'فروش و بازاریابی','2026-09-21 12:00:00',0,0),
 (@t,910040,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «برنامه اطلاع‌رسانی تغییر قیمت» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-25 15:00:00',70,0),
 (@t,910040,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «برنامه اطلاع‌رسانی تغییر قیمت».',N'مدیریت','2026-09-19 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910041,N'LAB-910041',N'کاهش زمان انتظار پذیرش سرویس','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910041,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910041,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کاهش زمان انتظار پذیرش سرویس» همراه با ثبت مستندات قابل رسیدگی.',N'خدمات پس از فروش','2026-09-22 12:00:00',100,1),
 (@t,910041,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کاهش زمان انتظار پذیرش سرویس» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-26 15:00:00',100,1),
 (@t,910041,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کاهش زمان انتظار پذیرش سرویس».',N'مدیریت','2026-09-20 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910042,N'LAB-910042',N'پیگیری تأخیر تأمین قطعه گارانتی','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910042,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910042,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «پیگیری تأخیر تأمین قطعه گارانتی» همراه با ثبت مستندات قابل رسیدگی.',N'خدمات پس از فروش','2026-09-23 12:00:00',60,0),
 (@t,910042,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «پیگیری تأخیر تأمین قطعه گارانتی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-27 15:00:00',35,0),
 (@t,910042,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «پیگیری تأخیر تأمین قطعه گارانتی».',N'مدیریت','2026-09-21 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910043,N'LAB-910043',N'بررسی افزایش مراجعات تکراری گیربکس','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910043,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910043,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بررسی افزایش مراجعات تکراری گیربکس» همراه با ثبت مستندات قابل رسیدگی.',N'خدمات پس از فروش','2026-09-24 12:00:00',20,0),
 (@t,910043,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بررسی افزایش مراجعات تکراری گیربکس» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-14 15:00:00',0,0),
 (@t,910043,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بررسی افزایش مراجعات تکراری گیربکس».',N'مدیریت','2026-09-22 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910044,N'LAB-910044',N'تحلیل شکایت مشتریان از نوبت‌دهی','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910044,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910044,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «تحلیل شکایت مشتریان از نوبت‌دهی» همراه با ثبت مستندات قابل رسیدگی.',N'خدمات پس از فروش','2026-09-25 12:00:00',0,0),
 (@t,910044,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «تحلیل شکایت مشتریان از نوبت‌دهی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-15 15:00:00',70,0),
 (@t,910044,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «تحلیل شکایت مشتریان از نوبت‌دهی».',N'مدیریت','2026-09-23 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910045,N'LAB-910045',N'بازنگری SLA رسیدگی به شکایات','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910045,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910045,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بازنگری SLA رسیدگی به شکایات» همراه با ثبت مستندات قابل رسیدگی.',N'خدمات پس از فروش','2026-09-26 12:00:00',100,1),
 (@t,910045,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بازنگری SLA رسیدگی به شکایات» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-16 15:00:00',100,1),
 (@t,910045,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بازنگری SLA رسیدگی به شکایات».',N'مدیریت','2026-09-24 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910046,N'LAB-910046',N'رفع مغایرت تأییدیه گارانتی','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910046,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910046,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «رفع مغایرت تأییدیه گارانتی» همراه با ثبت مستندات قابل رسیدگی.',N'خدمات پس از فروش','2026-09-12 12:00:00',60,0),
 (@t,910046,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «رفع مغایرت تأییدیه گارانتی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-17 15:00:00',35,0),
 (@t,910046,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «رفع مغایرت تأییدیه گارانتی».',N'مدیریت','2026-09-25 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910047,N'LAB-910047',N'برنامه آموزش تکنسین خودرو برقی','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910047,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910047,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «برنامه آموزش تکنسین خودرو برقی» همراه با ثبت مستندات قابل رسیدگی.',N'خدمات پس از فروش','2026-09-13 12:00:00',20,0),
 (@t,910047,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «برنامه آموزش تکنسین خودرو برقی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-18 15:00:00',0,0),
 (@t,910047,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «برنامه آموزش تکنسین خودرو برقی».',N'مدیریت','2026-09-26 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910048,N'LAB-910048',N'پایش رضایت مشتری پس از تعمیر','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910048,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910048,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «پایش رضایت مشتری پس از تعمیر» همراه با ثبت مستندات قابل رسیدگی.',N'خدمات پس از فروش','2026-09-14 12:00:00',0,0),
 (@t,910048,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «پایش رضایت مشتری پس از تعمیر» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-19 15:00:00',70,0),
 (@t,910048,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «پایش رضایت مشتری پس از تعمیر».',N'مدیریت','2026-09-27 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910049,N'LAB-910049',N'کنترل کیفیت تعمیرات جلوبندی','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910049,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910049,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کنترل کیفیت تعمیرات جلوبندی» همراه با ثبت مستندات قابل رسیدگی.',N'خدمات پس از فروش','2026-09-15 12:00:00',100,1),
 (@t,910049,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کنترل کیفیت تعمیرات جلوبندی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-20 15:00:00',100,1),
 (@t,910049,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کنترل کیفیت تعمیرات جلوبندی».',N'مدیریت','2026-09-16 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910050,N'LAB-910050',N'کاهش زمان خواب خودرو در تعمیرگاه','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910050,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910050,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کاهش زمان خواب خودرو در تعمیرگاه» همراه با ثبت مستندات قابل رسیدگی.',N'خدمات پس از فروش','2026-09-16 12:00:00',60,0),
 (@t,910050,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کاهش زمان خواب خودرو در تعمیرگاه» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-21 15:00:00',35,0),
 (@t,910050,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کاهش زمان خواب خودرو در تعمیرگاه».',N'مدیریت','2026-09-17 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910051,N'LAB-910051',N'کسری موجودی فیلتر روغن اصلی','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910051,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910051,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کسری موجودی فیلتر روغن اصلی» همراه با ثبت مستندات قابل رسیدگی.',N'انبار','2026-09-17 12:00:00',20,0),
 (@t,910051,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کسری موجودی فیلتر روغن اصلی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-22 15:00:00',0,0),
 (@t,910051,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کسری موجودی فیلتر روغن اصلی».',N'مدیریت','2026-09-18 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910052,N'LAB-910052',N'مغایرت شمارش دوره‌ای قطعات','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910052,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910052,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «مغایرت شمارش دوره‌ای قطعات» همراه با ثبت مستندات قابل رسیدگی.',N'انبار','2026-09-18 12:00:00',0,0),
 (@t,910052,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «مغایرت شمارش دوره‌ای قطعات» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-23 15:00:00',70,0),
 (@t,910052,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «مغایرت شمارش دوره‌ای قطعات».',N'مدیریت','2026-09-19 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910053,N'LAB-910053',N'کاهش قطعات راکد انبار مرکزی','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910053,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910053,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کاهش قطعات راکد انبار مرکزی» همراه با ثبت مستندات قابل رسیدگی.',N'انبار','2026-09-19 12:00:00',100,1),
 (@t,910053,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کاهش قطعات راکد انبار مرکزی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-24 15:00:00',100,1),
 (@t,910053,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کاهش قطعات راکد انبار مرکزی».',N'مدیریت','2026-09-20 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910054,N'LAB-910054',N'کنترل تاریخ مصرف مواد شیمیایی','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910054,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910054,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کنترل تاریخ مصرف مواد شیمیایی» همراه با ثبت مستندات قابل رسیدگی.',N'انبار','2026-09-20 12:00:00',60,0),
 (@t,910054,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کنترل تاریخ مصرف مواد شیمیایی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-25 15:00:00',35,0),
 (@t,910054,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کنترل تاریخ مصرف مواد شیمیایی».',N'مدیریت','2026-09-21 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910055,N'LAB-910055',N'پیگیری محل نگهداری باتری لیتیومی','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910055,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910055,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «پیگیری محل نگهداری باتری لیتیومی» همراه با ثبت مستندات قابل رسیدگی.',N'انبار','2026-09-21 12:00:00',20,0),
 (@t,910055,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «پیگیری محل نگهداری باتری لیتیومی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-26 15:00:00',0,0),
 (@t,910055,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «پیگیری محل نگهداری باتری لیتیومی».',N'مدیریت','2026-09-22 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910056,N'LAB-910056',N'بهبود فرآیند تحویل قطعه به نماینده','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910056,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910056,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بهبود فرآیند تحویل قطعه به نماینده» همراه با ثبت مستندات قابل رسیدگی.',N'انبار','2026-09-22 12:00:00',0,0),
 (@t,910056,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بهبود فرآیند تحویل قطعه به نماینده» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-27 15:00:00',70,0),
 (@t,910056,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بهبود فرآیند تحویل قطعه به نماینده».',N'مدیریت','2026-09-23 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910057,N'LAB-910057',N'استانداردسازی کدگذاری لوازم یدکی','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910057,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910057,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «استانداردسازی کدگذاری لوازم یدکی» همراه با ثبت مستندات قابل رسیدگی.',N'انبار','2026-09-23 12:00:00',100,1),
 (@t,910057,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «استانداردسازی کدگذاری لوازم یدکی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-14 15:00:00',100,1),
 (@t,910057,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «استانداردسازی کدگذاری لوازم یدکی».',N'مدیریت','2026-09-24 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910058,N'LAB-910058',N'بررسی برگشت قطعه معیوب','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910058,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910058,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بررسی برگشت قطعه معیوب» همراه با ثبت مستندات قابل رسیدگی.',N'انبار','2026-09-24 12:00:00',60,0),
 (@t,910058,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بررسی برگشت قطعه معیوب» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-15 15:00:00',35,0),
 (@t,910058,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بررسی برگشت قطعه معیوب».',N'مدیریت','2026-09-25 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910059,N'LAB-910059',N'کنترل نقطه سفارش لنت ترمز','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910059,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910059,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کنترل نقطه سفارش لنت ترمز» همراه با ثبت مستندات قابل رسیدگی.',N'انبار','2026-09-25 12:00:00',20,0),
 (@t,910059,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کنترل نقطه سفارش لنت ترمز» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-16 15:00:00',0,0),
 (@t,910059,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کنترل نقطه سفارش لنت ترمز».',N'مدیریت','2026-09-26 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910060,N'LAB-910060',N'کاهش خطای ثبت سریال قطعات','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910060,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910060,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کاهش خطای ثبت سریال قطعات» همراه با ثبت مستندات قابل رسیدگی.',N'انبار','2026-09-26 12:00:00',0,0),
 (@t,910060,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کاهش خطای ثبت سریال قطعات» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-17 15:00:00',70,0),
 (@t,910060,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کاهش خطای ثبت سریال قطعات».',N'مدیریت','2026-09-27 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910061,N'LAB-910061',N'تطبیق پرداخت ارزی سفارش خودرو','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910061,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910061,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «تطبیق پرداخت ارزی سفارش خودرو» همراه با ثبت مستندات قابل رسیدگی.',N'مالی','2026-09-12 12:00:00',100,1),
 (@t,910061,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «تطبیق پرداخت ارزی سفارش خودرو» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-18 15:00:00',100,1),
 (@t,910061,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «تطبیق پرداخت ارزی سفارش خودرو».',N'مدیریت','2026-09-16 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910062,N'LAB-910062',N'بررسی نقدینگی هزینه ترخیص','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910062,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910062,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بررسی نقدینگی هزینه ترخیص» همراه با ثبت مستندات قابل رسیدگی.',N'مالی','2026-09-13 12:00:00',60,0),
 (@t,910062,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بررسی نقدینگی هزینه ترخیص» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-19 15:00:00',35,0),
 (@t,910062,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بررسی نقدینگی هزینه ترخیص».',N'مدیریت','2026-09-17 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910063,N'LAB-910063',N'تحلیل انحراف بودجه حمل‌ونقل','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910063,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910063,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «تحلیل انحراف بودجه حمل‌ونقل» همراه با ثبت مستندات قابل رسیدگی.',N'مالی','2026-09-14 12:00:00',20,0),
 (@t,910063,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «تحلیل انحراف بودجه حمل‌ونقل» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-20 15:00:00',0,0),
 (@t,910063,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «تحلیل انحراف بودجه حمل‌ونقل».',N'مدیریت','2026-09-18 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910064,N'LAB-910064',N'پیگیری تأخیر وصول مطالبات نمایندگی','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910064,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910064,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «پیگیری تأخیر وصول مطالبات نمایندگی» همراه با ثبت مستندات قابل رسیدگی.',N'مالی','2026-09-15 12:00:00',0,0),
 (@t,910064,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «پیگیری تأخیر وصول مطالبات نمایندگی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-21 15:00:00',70,0),
 (@t,910064,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «پیگیری تأخیر وصول مطالبات نمایندگی».',N'مدیریت','2026-09-19 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910065,N'LAB-910065',N'بازنگری قیمت تمام‌شده مدل برقی','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910065,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910065,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بازنگری قیمت تمام‌شده مدل برقی» همراه با ثبت مستندات قابل رسیدگی.',N'مالی','2026-09-16 12:00:00',100,1),
 (@t,910065,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بازنگری قیمت تمام‌شده مدل برقی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-22 15:00:00',100,1),
 (@t,910065,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بازنگری قیمت تمام‌شده مدل برقی».',N'مدیریت','2026-09-20 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910066,N'LAB-910066',N'کنترل اسناد هزینه خدمات گارانتی','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910066,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910066,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کنترل اسناد هزینه خدمات گارانتی» همراه با ثبت مستندات قابل رسیدگی.',N'مالی','2026-09-17 12:00:00',60,0),
 (@t,910066,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کنترل اسناد هزینه خدمات گارانتی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-23 15:00:00',35,0),
 (@t,910066,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کنترل اسناد هزینه خدمات گارانتی».',N'مدیریت','2026-09-21 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910067,N'LAB-910067',N'برنامه پرداخت مرحله‌ای تأمین‌کننده','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910067,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910067,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «برنامه پرداخت مرحله‌ای تأمین‌کننده» همراه با ثبت مستندات قابل رسیدگی.',N'مالی','2026-09-18 12:00:00',20,0),
 (@t,910067,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «برنامه پرداخت مرحله‌ای تأمین‌کننده» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-24 15:00:00',0,0),
 (@t,910067,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «برنامه پرداخت مرحله‌ای تأمین‌کننده».',N'مدیریت','2026-09-22 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910068,N'LAB-910068',N'رفع مغایرت فاکتور و حواله انبار','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910068,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910068,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «رفع مغایرت فاکتور و حواله انبار» همراه با ثبت مستندات قابل رسیدگی.',N'مالی','2026-09-19 12:00:00',0,0),
 (@t,910068,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «رفع مغایرت فاکتور و حواله انبار» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-25 15:00:00',70,0),
 (@t,910068,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «رفع مغایرت فاکتور و حواله انبار».',N'مدیریت','2026-09-23 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910069,N'LAB-910069',N'پایش تعهدات ارزی سررسیدشده','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910069,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910069,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «پایش تعهدات ارزی سررسیدشده» همراه با ثبت مستندات قابل رسیدگی.',N'مالی','2026-09-20 12:00:00',100,1),
 (@t,910069,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «پایش تعهدات ارزی سررسیدشده» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-26 15:00:00',100,1),
 (@t,910069,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «پایش تعهدات ارزی سررسیدشده».',N'مدیریت','2026-09-24 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910070,N'LAB-910070',N'تعیین سقف اعتبار فروش سازمانی','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910070,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910070,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «تعیین سقف اعتبار فروش سازمانی» همراه با ثبت مستندات قابل رسیدگی.',N'مالی','2026-09-21 12:00:00',60,0),
 (@t,910070,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «تعیین سقف اعتبار فروش سازمانی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-27 15:00:00',35,0),
 (@t,910070,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «تعیین سقف اعتبار فروش سازمانی».',N'مدیریت','2026-09-25 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910071,N'LAB-910071',N'بررسی نقص تکراری سیستم تهویه','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910071,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910071,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بررسی نقص تکراری سیستم تهویه» همراه با ثبت مستندات قابل رسیدگی.',N'مهندسی و PDI','2026-09-22 12:00:00',20,0),
 (@t,910071,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بررسی نقص تکراری سیستم تهویه» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-14 15:00:00',0,0),
 (@t,910071,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بررسی نقص تکراری سیستم تهویه».',N'مدیریت','2026-09-26 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910072,N'LAB-910072',N'کنترل چک‌لیست PDI محموله جدید','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910072,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910072,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کنترل چک‌لیست PDI محموله جدید» همراه با ثبت مستندات قابل رسیدگی.',N'مهندسی و PDI','2026-09-23 12:00:00',0,0),
 (@t,910072,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کنترل چک‌لیست PDI محموله جدید» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-15 15:00:00',70,0),
 (@t,910072,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کنترل چک‌لیست PDI محموله جدید».',N'مدیریت','2026-09-27 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910073,N'LAB-910073',N'ردیابی علت خطای ECU پس از تحویل','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910073,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910073,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «ردیابی علت خطای ECU پس از تحویل» همراه با ثبت مستندات قابل رسیدگی.',N'مهندسی و PDI','2026-09-24 12:00:00',100,1),
 (@t,910073,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «ردیابی علت خطای ECU پس از تحویل» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-16 15:00:00',100,1),
 (@t,910073,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «ردیابی علت خطای ECU پس از تحویل».',N'مدیریت','2026-09-16 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910074,N'LAB-910074',N'بررسی کیفیت مونتاژ تریم داخلی','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910074,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910074,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بررسی کیفیت مونتاژ تریم داخلی» همراه با ثبت مستندات قابل رسیدگی.',N'مهندسی و PDI','2026-09-25 12:00:00',60,0),
 (@t,910074,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بررسی کیفیت مونتاژ تریم داخلی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-17 15:00:00',35,0),
 (@t,910074,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بررسی کیفیت مونتاژ تریم داخلی».',N'مدیریت','2026-09-17 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910075,N'LAB-910075',N'هماهنگی فراخوان بررسی پیچ چرخ','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910075,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910075,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «هماهنگی فراخوان بررسی پیچ چرخ» همراه با ثبت مستندات قابل رسیدگی.',N'مهندسی و PDI','2026-09-26 12:00:00',20,0),
 (@t,910075,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «هماهنگی فراخوان بررسی پیچ چرخ» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-18 15:00:00',0,0),
 (@t,910075,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «هماهنگی فراخوان بررسی پیچ چرخ».',N'مدیریت','2026-09-18 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910076,N'LAB-910076',N'پایش نتایج آزمون ترمز','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910076,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910076,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «پایش نتایج آزمون ترمز» همراه با ثبت مستندات قابل رسیدگی.',N'مهندسی و PDI','2026-09-12 12:00:00',0,0),
 (@t,910076,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «پایش نتایج آزمون ترمز» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-19 15:00:00',70,0),
 (@t,910076,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «پایش نتایج آزمون ترمز».',N'مدیریت','2026-09-19 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910077,N'LAB-910077',N'تحلیل افت ظرفیت باتری نمونه آزمایشی','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910077,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910077,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «تحلیل افت ظرفیت باتری نمونه آزمایشی» همراه با ثبت مستندات قابل رسیدگی.',N'مهندسی و PDI','2026-09-13 12:00:00',100,1),
 (@t,910077,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «تحلیل افت ظرفیت باتری نمونه آزمایشی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-20 15:00:00',100,1),
 (@t,910077,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «تحلیل افت ظرفیت باتری نمونه آزمایشی».',N'مدیریت','2026-09-20 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910078,N'LAB-910078',N'رفع مغایرت کالیبراسیون سنسورها','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910078,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910078,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «رفع مغایرت کالیبراسیون سنسورها» همراه با ثبت مستندات قابل رسیدگی.',N'مهندسی و PDI','2026-09-14 12:00:00',60,0),
 (@t,910078,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «رفع مغایرت کالیبراسیون سنسورها» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-21 15:00:00',35,0),
 (@t,910078,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «رفع مغایرت کالیبراسیون سنسورها».',N'مدیریت','2026-09-21 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910079,N'LAB-910079',N'بهبود استاندارد حفاظت رنگ خودرو','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910079,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910079,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بهبود استاندارد حفاظت رنگ خودرو» همراه با ثبت مستندات قابل رسیدگی.',N'مهندسی و PDI','2026-09-15 12:00:00',20,0),
 (@t,910079,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بهبود استاندارد حفاظت رنگ خودرو» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-22 15:00:00',0,0),
 (@t,910079,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بهبود استاندارد حفاظت رنگ خودرو».',N'مدیریت','2026-09-22 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910080,N'LAB-910080',N'بررسی نرخ خرابی اولیه خودرو','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910080,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910080,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بررسی نرخ خرابی اولیه خودرو» همراه با ثبت مستندات قابل رسیدگی.',N'مهندسی و PDI','2026-09-16 12:00:00',0,0),
 (@t,910080,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بررسی نرخ خرابی اولیه خودرو» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-23 15:00:00',70,0),
 (@t,910080,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بررسی نرخ خرابی اولیه خودرو».',N'مدیریت','2026-09-23 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910081,N'LAB-910081',N'بررسی بند جریمه تأخیر تأمین‌کننده','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910081,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910081,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بررسی بند جریمه تأخیر تأمین‌کننده» همراه با ثبت مستندات قابل رسیدگی.',N'حقوقی','2026-09-17 12:00:00',100,1),
 (@t,910081,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بررسی بند جریمه تأخیر تأمین‌کننده» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-24 15:00:00',100,1),
 (@t,910081,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بررسی بند جریمه تأخیر تأمین‌کننده».',N'مدیریت','2026-09-24 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910082,N'LAB-910082',N'تطبیق ضمانت‌نامه حسن انجام کار','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910082,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910082,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «تطبیق ضمانت‌نامه حسن انجام کار» همراه با ثبت مستندات قابل رسیدگی.',N'حقوقی','2026-09-18 12:00:00',60,0),
 (@t,910082,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «تطبیق ضمانت‌نامه حسن انجام کار» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-25 15:00:00',35,0),
 (@t,910082,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «تطبیق ضمانت‌نامه حسن انجام کار».',N'مدیریت','2026-09-25 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910083,N'LAB-910083',N'رسیدگی به اختلاف شرایط گارانتی','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910083,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910083,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «رسیدگی به اختلاف شرایط گارانتی» همراه با ثبت مستندات قابل رسیدگی.',N'حقوقی','2026-09-19 12:00:00',20,0),
 (@t,910083,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «رسیدگی به اختلاف شرایط گارانتی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-26 15:00:00',0,0),
 (@t,910083,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «رسیدگی به اختلاف شرایط گارانتی».',N'مدیریت','2026-09-26 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910084,N'LAB-910084',N'به‌روزرسانی الحاقیه قرارداد لجستیک','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910084,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910084,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «به‌روزرسانی الحاقیه قرارداد لجستیک» همراه با ثبت مستندات قابل رسیدگی.',N'حقوقی','2026-09-20 12:00:00',0,0),
 (@t,910084,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «به‌روزرسانی الحاقیه قرارداد لجستیک» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-27 15:00:00',70,0),
 (@t,910084,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «به‌روزرسانی الحاقیه قرارداد لجستیک».',N'مدیریت','2026-09-27 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910085,N'LAB-910085',N'کنترل محرمانگی داده مشتریان','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910085,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910085,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کنترل محرمانگی داده مشتریان» همراه با ثبت مستندات قابل رسیدگی.',N'حقوقی','2026-09-21 12:00:00',100,1),
 (@t,910085,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کنترل محرمانگی داده مشتریان» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-14 15:00:00',100,1),
 (@t,910085,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کنترل محرمانگی داده مشتریان».',N'مدیریت','2026-09-16 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910086,N'LAB-910086',N'بررسی اختلاف مالی نمایندگی','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910086,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910086,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بررسی اختلاف مالی نمایندگی» همراه با ثبت مستندات قابل رسیدگی.',N'حقوقی','2026-09-22 12:00:00',60,0),
 (@t,910086,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بررسی اختلاف مالی نمایندگی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-15 15:00:00',35,0),
 (@t,910086,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بررسی اختلاف مالی نمایندگی».',N'مدیریت','2026-09-17 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910087,N'LAB-910087',N'بازنگری مسئولیت تحویل خودرو','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910087,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910087,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بازنگری مسئولیت تحویل خودرو» همراه با ثبت مستندات قابل رسیدگی.',N'حقوقی','2026-09-23 12:00:00',20,0),
 (@t,910087,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بازنگری مسئولیت تحویل خودرو» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-16 15:00:00',0,0),
 (@t,910087,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بازنگری مسئولیت تحویل خودرو».',N'مدیریت','2026-09-18 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910088,N'LAB-910088',N'بررسی حق فسخ قرارداد خرید قطعات','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910088,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910088,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بررسی حق فسخ قرارداد خرید قطعات» همراه با ثبت مستندات قابل رسیدگی.',N'حقوقی','2026-09-24 12:00:00',0,0),
 (@t,910088,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بررسی حق فسخ قرارداد خرید قطعات» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-17 15:00:00',70,0),
 (@t,910088,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بررسی حق فسخ قرارداد خرید قطعات».',N'مدیریت','2026-09-19 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910089,N'LAB-910089',N'کنترل اعتبار وکالت‌نامه واردات','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910089,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910089,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کنترل اعتبار وکالت‌نامه واردات» همراه با ثبت مستندات قابل رسیدگی.',N'حقوقی','2026-09-25 12:00:00',100,1),
 (@t,910089,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کنترل اعتبار وکالت‌نامه واردات» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-18 15:00:00',100,1),
 (@t,910089,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کنترل اعتبار وکالت‌نامه واردات».',N'مدیریت','2026-09-20 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910090,N'LAB-910090',N'رسیدگی به شکایت قراردادی مشتری','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910090,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910090,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «رسیدگی به شکایت قراردادی مشتری» همراه با ثبت مستندات قابل رسیدگی.',N'حقوقی','2026-09-26 12:00:00',60,0),
 (@t,910090,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «رسیدگی به شکایت قراردادی مشتری» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-19 15:00:00',35,0),
 (@t,910090,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «رسیدگی به شکایت قراردادی مشتری».',N'مدیریت','2026-09-21 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910091,N'LAB-910091',N'هماهنگی اتصال ProcessMaker به SQL Server','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910091,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910091,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «هماهنگی اتصال ProcessMaker به SQL Server» همراه با ثبت مستندات قابل رسیدگی.',N'فناوری اطلاعات و راهبرد','2026-09-12 12:00:00',20,0),
 (@t,910091,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «هماهنگی اتصال ProcessMaker به SQL Server» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-20 15:00:00',0,0),
 (@t,910091,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «هماهنگی اتصال ProcessMaker به SQL Server».',N'مدیریت','2026-09-22 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910092,N'LAB-910092',N'بازنگری کیفیت داده‌های صورت‌جلسات','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910092,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910092,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بازنگری کیفیت داده‌های صورت‌جلسات» همراه با ثبت مستندات قابل رسیدگی.',N'فناوری اطلاعات و راهبرد','2026-09-13 12:00:00',0,0),
 (@t,910092,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بازنگری کیفیت داده‌های صورت‌جلسات» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-21 15:00:00',70,0),
 (@t,910092,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بازنگری کیفیت داده‌های صورت‌جلسات».',N'مدیریت','2026-09-23 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910093,N'LAB-910093',N'طراحی سطح دسترسی داشبورد مدیران','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910093,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910093,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «طراحی سطح دسترسی داشبورد مدیران» همراه با ثبت مستندات قابل رسیدگی.',N'فناوری اطلاعات و راهبرد','2026-09-14 12:00:00',100,1),
 (@t,910093,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «طراحی سطح دسترسی داشبورد مدیران» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-22 15:00:00',100,1),
 (@t,910093,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «طراحی سطح دسترسی داشبورد مدیران».',N'مدیریت','2026-09-24 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910094,N'LAB-910094',N'برنامه استقرار سرویس هوش مصنوعی آزمایشی','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910094,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910094,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «برنامه استقرار سرویس هوش مصنوعی آزمایشی» همراه با ثبت مستندات قابل رسیدگی.',N'فناوری اطلاعات و راهبرد','2026-09-15 12:00:00',60,0),
 (@t,910094,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «برنامه استقرار سرویس هوش مصنوعی آزمایشی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-23 15:00:00',35,0),
 (@t,910094,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «برنامه استقرار سرویس هوش مصنوعی آزمایشی».',N'مدیریت','2026-09-25 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910095,N'LAB-910095',N'کنترل پشتیبان‌گیری داده‌های جلسات','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910095,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910095,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «کنترل پشتیبان‌گیری داده‌های جلسات» همراه با ثبت مستندات قابل رسیدگی.',N'فناوری اطلاعات و راهبرد','2026-09-16 12:00:00',20,0),
 (@t,910095,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «کنترل پشتیبان‌گیری داده‌های جلسات» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-24 15:00:00',0,0),
 (@t,910095,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «کنترل پشتیبان‌گیری داده‌های جلسات».',N'مدیریت','2026-09-26 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910096,N'LAB-910096',N'بهبود شاخص‌های پیگیری اقدامات','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910096,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910096,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بهبود شاخص‌های پیگیری اقدامات» همراه با ثبت مستندات قابل رسیدگی.',N'فناوری اطلاعات و راهبرد','2026-09-17 12:00:00',0,0),
 (@t,910096,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بهبود شاخص‌های پیگیری اقدامات» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-25 15:00:00',70,0),
 (@t,910096,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بهبود شاخص‌های پیگیری اقدامات».',N'مدیریت','2026-09-27 16:00:00',45,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910097,N'LAB-910097',N'طراحی گزارش تلفیقی واحدهای خودرویی','Closed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910097,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910097,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «طراحی گزارش تلفیقی واحدهای خودرویی» همراه با ثبت مستندات قابل رسیدگی.',N'فناوری اطلاعات و راهبرد','2026-09-18 12:00:00',100,1),
 (@t,910097,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «طراحی گزارش تلفیقی واحدهای خودرویی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-26 15:00:00',100,1),
 (@t,910097,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «طراحی گزارش تلفیقی واحدهای خودرویی».',N'مدیریت','2026-09-16 16:00:00',100,1);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910098,N'LAB-910098',N'بررسی مغایرت شناسه مشتری در سامانه‌ها','InProgress');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910098,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910098,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «بررسی مغایرت شناسه مشتری در سامانه‌ها» همراه با ثبت مستندات قابل رسیدگی.',N'فناوری اطلاعات و راهبرد','2026-09-19 12:00:00',60,0),
 (@t,910098,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «بررسی مغایرت شناسه مشتری در سامانه‌ها» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-27 15:00:00',35,0),
 (@t,910098,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «بررسی مغایرت شناسه مشتری در سامانه‌ها».',N'مدیریت','2026-09-17 16:00:00',10,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910099,N'LAB-910099',N'تعریف رویه ممیزی تغییرات فرایندی','Delayed');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910099,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910099,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «تعریف رویه ممیزی تغییرات فرایندی» همراه با ثبت مستندات قابل رسیدگی.',N'فناوری اطلاعات و راهبرد','2026-09-20 12:00:00',20,0),
 (@t,910099,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «تعریف رویه ممیزی تغییرات فرایندی» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-14 15:00:00',0,0),
 (@t,910099,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «تعریف رویه ممیزی تغییرات فرایندی».',N'مدیریت','2026-09-18 16:00:00',0,0);
INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@t,910100,N'LAB-910100',N'برنامه آموزش کاربران سیستم مدیریت جلسات','Planned');
INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@t,910100,N'lab-alice');
INSERT AgentProduct.ActionIndex
 (TenantID,MeetingID,ActionNo,ActionTitle,OwnerUnit,DueAtUtc,ProgressPercent,IsClosed)
 VALUES
 (@t,910100,N'A-001',N'جمع‌آوری مدارک و بررسی علت مسئله «برنامه آموزش کاربران سیستم مدیریت جلسات» همراه با ثبت مستندات قابل رسیدگی.',N'فناوری اطلاعات و راهبرد','2026-09-21 12:00:00',0,0),
 (@t,910100,N'A-002',N'ارائه برنامه اصلاحی و برآورد منابع برای «برنامه آموزش کاربران سیستم مدیریت جلسات» به رئیس جلسه.',N'برنامه‌ریزی و راهبرد','2026-09-15 15:00:00',70,0),
 (@t,910100,N'A-003',N'پیگیری اجرای تصمیم جلسه و گزارش نتیجه قابل اندازه‌گیری درباره «برنامه آموزش کاربران سیستم مدیریت جلسات».',N'مدیریت','2026-09-19 16:00:00',45,0);
 COMMIT TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
 PRINT 'PASS: imported 100 fictional automotive meeting summaries and 300 action rows into AgentProduct test tenant A.';
 PRINT 'NOTE: complete lifecycle fields remain in the source JSON; index stores only current meeting/action projections.';
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
 THROW;
END CATCH;
GO
