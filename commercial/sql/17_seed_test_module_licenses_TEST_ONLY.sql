/* FICTIONAL PURCHASE FIXTURE for testing paid module switches ONLY.
   Tenant A: all 3 optional modules licensed for 30 days in test;
   M2 ON, M3 OFF, M4 ON; tenant B buys nothing and stays OFF.
   This is NOT an actual financial transaction or license issuance.
   Run ONCE as TEST DBA after 12,14,15,16; never on operational DB.
*/
USE [EnterpriseProcess2_AI_Test];
GO
SET XACT_ABORT ON;
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test'
 THROW 59500,'Wrong database',1;
IF ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0)<>1
 THROW 59501,'Run as test DBA',1;
IF OBJECT_ID(N'AgentProduct.TenantModule',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.ActionIndex',N'U') IS NULL
 THROW 59502,'Run 14 and 15 first',1;
GO
DECLARE @a uniqueidentifier='11111111-1111-4111-8111-111111111111';
BEGIN TRY
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=@a;
 BEGIN TRAN;
 IF EXISTS(SELECT 1 FROM AgentProduct.TenantModule
           WHERE TenantID=@a AND ModuleCode IN(2,3,4))
  THROW 59503,'Module lab fixtures already exist; do not overwrite.',1;
 IF EXISTS(SELECT 1 FROM AgentProduct.Membership
           WHERE TenantID=@a AND SubjectID=N'lab-admin')
  THROW 59504,'Synthetic lab admin already exists; do not overwrite.',1;
 INSERT AgentProduct.Membership(TenantID,SubjectID,RoleCode)
 VALUES(@a,N'lab-admin','Admin');
 INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@a,900001,N'lab-admin'),(@a,910001,N'lab-admin');
 INSERT AgentProduct.TenantModule
 (TenantID,ModuleCode,IsLicensed,IsEnabled,LicenseUntilUtc)
 VALUES
 (@a,2,1,1,DATEADD(DAY,30,SYSUTCDATETIME())),
 (@a,3,1,0,DATEADD(DAY,30,SYSUTCDATETIME())),
 (@a,4,1,1,DATEADD(DAY,30,SYSUTCDATETIME()));
 COMMIT TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
 PRINT 'PASS: fictional tenant A lab licenses installed (M2 ON, M3 OFF, M4 ON).';
 PRINT 'PASS: tenant B remains UNLICENSED; lab-admin exists only in tenant A.';
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
 THROW;
END CATCH;
GO
