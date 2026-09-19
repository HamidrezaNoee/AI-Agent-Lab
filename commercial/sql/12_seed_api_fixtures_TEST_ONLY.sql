/* Explicitly fictional, isolated fixtures for real SQL/API integration tests.
   Run ONCE as test DBA. Never run against live EnterpriseProcess databases.
   Fixed lab identities do not correspond to actual employees or customers.
   Refuse to overwrite existing fixture keys; this is NOT a generic seed/import.
*/
USE [EnterpriseProcess2_AI_Test];
GO
SET XACT_ABORT ON;
IF DB_NAME() <> N'EnterpriseProcess2_AI_Test'
 THROW 59000,'Wrong database: synthetic test only.',1;
IF OBJECT_ID(N'AgentProduct.MeetingGrant',N'U') IS NULL OR
   OBJECT_ID(N'AgentProduct.DocumentGrant',N'U') IS NULL OR
   COL_LENGTH(N'AgentProduct.DocumentIndex',N'RelatedMeetingID') IS NULL
 THROW 59001,'Run commercial migrations 01, 03, 05, 09 before this fixture.',1;
GO
DECLARE @a uniqueidentifier='11111111-1111-4111-8111-111111111111',
        @b uniqueidentifier='22222222-2222-4222-8222-222222222222';
DECLARE @da1 uniqueidentifier='33333333-3333-4333-8333-333333333331',
        @da2 uniqueidentifier='33333333-3333-4333-8333-333333333332',
        @dag uniqueidentifier='33333333-3333-4333-8333-333333333333',
        @db1 uniqueidentifier='44444444-4444-4444-8444-444444444441';
BEGIN TRY
 BEGIN TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=@a;
 IF EXISTS(SELECT 1 FROM AgentProduct.Tenant WHERE TenantID=@a)
    OR EXISTS(SELECT 1 FROM AgentProduct.MeetingIndex WHERE MeetingID IN(900001,900002))
    OR EXISTS(SELECT 1 FROM AgentProduct.DocumentIndex
              WHERE DocumentID IN (@da1,@da2,@dag))
   THROW 59002,'Lab fixture A already exists. Do not overwrite it.',1;
 INSERT AgentProduct.Tenant(TenantID,TenantName)
 VALUES (@a,N'FICTIONAL LAB COMPANY A');
 INSERT AgentProduct.Membership(TenantID,SubjectID,RoleCode)
 VALUES (@a,N'lab-alice','Viewer'),(@a,N'lab-bob','Viewer');
 INSERT AgentProduct.Subscription
 (TenantID,PlanCode,IsActive,ExpiresAtUtc,MonthlyRequestLimit)
 VALUES(@a,N'LAB-ONLY',1,DATEADD(DAY,30,SYSUTCDATETIME()),20);
 INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES
 (@a,900001,N'LAB-A-001',N'FICTIONAL A: جلسه گمرک و شماره شاسی',N'Draft'),
 (@a,900002,N'LAB-A-002',N'FICTIONAL A: جلسه مالی و بودجه',N'Draft');
 INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@a,900001,N'lab-alice'),(@a,900002,N'lab-bob');
 INSERT AgentProduct.DocumentIndex
 (TenantID,DocumentID,DocumentTitle,CurrentVersion,IsActive,RelatedMeetingID)
 VALUES
 (@a,@da1,N'FICTIONAL A: سند گمرک فقط برای Alice',1,1,900001),
 (@a,@da2,N'FICTIONAL A: سند بودجه فقط برای Bob',1,1,900002),
 (@a,@dag,N'FICTIONAL A: راهنمای عمومی گمرک',1,1,NULL);
 INSERT AgentProduct.DocumentChunk
 (TenantID,DocumentID,ChunkNo,DocumentVersion,ChunkText)
 VALUES
 (@a,@da1,1,1,N'سند ساختگی گمرک: مسئول جلسه A-001 باید مغایرت شماره شاسی و VIN را بررسی کند.'),
 (@a,@da2,1,1,N'سند ساختگی بودجه: مسئول جلسه A-002 باید برآورد مالی را بررسی کند.'),
 (@a,@dag,1,1,N'راهنمای عمومی ساختگی سازمان A: واژه گمرک صرفاً برای آزمایش جست‌وجو آمده است.');
 INSERT AgentProduct.DocumentGrant(TenantID,DocumentID,SubjectID)
 VALUES
 (@a,@da1,N'lab-alice'),(@a,@da2,N'lab-bob'),
 (@a,@dag,N'lab-alice'),(@a,@dag,N'lab-bob');

 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=@b;
 IF EXISTS(SELECT 1 FROM AgentProduct.Tenant WHERE TenantID=@b)
    OR EXISTS(SELECT 1 FROM AgentProduct.MeetingIndex WHERE MeetingID=900003)
    OR EXISTS(SELECT 1 FROM AgentProduct.DocumentIndex WHERE DocumentID=@db1)
   THROW 59003,'Lab fixture B already exists. Do not overwrite it.',1;
 INSERT AgentProduct.Tenant(TenantID,TenantName)
 VALUES(@b,N'FICTIONAL LAB COMPANY B');
 INSERT AgentProduct.Membership(TenantID,SubjectID,RoleCode)
 VALUES(@b,N'lab-carol','Viewer');
 INSERT AgentProduct.Subscription
 (TenantID,PlanCode,IsActive,ExpiresAtUtc,MonthlyRequestLimit)
 VALUES(@b,N'LAB-ONLY',1,DATEADD(DAY,30,SYSUTCDATETIME()),20);
 INSERT AgentProduct.MeetingIndex
 (TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@b,900003,N'LAB-B-003',N'FICTIONAL B: جلسه گمرک خصوصی',N'Draft');
 INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@b,900003,N'lab-carol');
 INSERT AgentProduct.DocumentIndex
 (TenantID,DocumentID,DocumentTitle,CurrentVersion,IsActive,RelatedMeetingID)
 VALUES(@b,@db1,N'FICTIONAL B: سند گمرک فقط برای Carol',1,1,900003);
 INSERT AgentProduct.DocumentChunk
 (TenantID,DocumentID,ChunkNo,DocumentVersion,ChunkText)
 VALUES(@b,@db1,1,1,N'سند ساختگی گمرک سازمان B: متن محرمانه‌نما فقط برای آزمون عدم افشا.');
 INSERT AgentProduct.DocumentGrant(TenantID,DocumentID,SubjectID)
 VALUES(@b,@db1,N'lab-carol');
 COMMIT TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
 PRINT 'PASS: fictional multi-tenant API fixtures committed in TEST DB only.';
 PRINT 'Tenant A: lab-alice -> 900001; lab-bob -> 900002; each also has tenant-wide guide.';
 PRINT 'Tenant B: lab-carol -> 900003; no grant to any tenant A resource.';
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
 THROW;
END CATCH;
GO
