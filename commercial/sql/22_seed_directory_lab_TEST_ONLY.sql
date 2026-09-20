/* FICTIONAL hierarchy fixture ONLY. Run ONCE after 19; no ProcessMaker contact.
   Alice=Expert with Bob beneath; Manager and SysAdmin see all A.
   Carol remains B-only. The old /v1 ACL contract is not altered.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test' OR ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0)<>1
 THROW 60000,'Synthetic directory seed restricted to TEST DBA.',1;
IF OBJECT_ID(N'AgentProduct.DirectoryUser',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.MeetingActor',N'U') IS NULL
 THROW 60001,'Run directory migration 19 first.',1;
GO
SET XACT_ABORT ON;
DECLARE @a uniqueidentifier='11111111-1111-4111-8111-111111111111';
DECLARE @b uniqueidentifier='22222222-2222-4222-8222-222222222222';
BEGIN TRY
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=@a;
 BEGIN TRAN;
 IF EXISTS(SELECT 1 FROM AgentProduct.DirectoryUser
 WHERE TenantID=@a AND PMUserUID IN('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa2','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa3','aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa4'))
 THROW 60002,'Fixture already installed; do not overwrite.',1;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.Membership WHERE TenantID=@a AND SubjectID=N'lab-admin')
 THROW 60003,'Install prior lab admin fixture 17 first.',1;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.Membership WHERE TenantID=@a AND SubjectID=N'lab-manager')
 INSERT AgentProduct.Membership(TenantID,SubjectID,RoleCode)
 VALUES(@a,N'lab-manager','Viewer');
 INSERT AgentProduct.DirectoryUser
 (TenantID,PMUserUID,PMUserName,DisplayName,PMStatus,SubjectID,OrgRole,IsEnabled)
 VALUES
 (@a,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1',N'lab-alice',N'آلیس آزمایشی','ACTIVE',N'lab-alice','Expert',1),
 (@a,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa2',N'lab-bob',N'باب آزمایشی','ACTIVE',N'lab-bob','Expert',1),
 (@a,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa3',N'lab-admin',N'مدیر سیستم آزمایشی','ACTIVE',N'lab-admin','SysAdmin',1),
 (@a,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa4',N'lab-manager',N'مدیر کل جلسات آزمایشی','ACTIVE',N'lab-manager','Manager',1);
 UPDATE AgentProduct.DirectoryUser SET ManagerPMUserUID='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1'
 WHERE TenantID=@a AND PMUserUID='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa2';
 INSERT AgentProduct.MeetingActor(TenantID,MeetingID,PMUserUID,ActorRole)
 VALUES(@a,900001,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1','Secretary'),
       (@a,900002,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa2','ActionOwner'),
       (@a,910001,'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa1','Chair');
 COMMIT TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=@b;
 BEGIN TRAN;
 IF EXISTS(SELECT 1 FROM AgentProduct.DirectoryUser WHERE TenantID=@b AND PMUserUID='bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb1')
 THROW 60004,'Tenant B fictional directory fixture exists.',1;
 INSERT AgentProduct.DirectoryUser
 (TenantID,PMUserUID,PMUserName,DisplayName,PMStatus,SubjectID,OrgRole,IsEnabled)
 VALUES(@b,'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb1',N'lab-carol',N'کارول آزمایشی','ACTIVE',N'lab-carol','Expert',1);
 INSERT AgentProduct.MeetingActor(TenantID,MeetingID,PMUserUID,ActorRole)
 VALUES(@b,900003,'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb1','Participant');
 COMMIT TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
 PRINT 'PASS: fictional directory hierarchy and secretary/chair/action-owner/participant links installed.';
 PRINT 'PASS: Alice Expert -> Bob subordinate; Manager & SysAdmin see tenant A; Carol isolated in B.';
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
 THROW;
END CATCH;
GO
