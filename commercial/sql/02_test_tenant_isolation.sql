/* TEST tenant isolation without retaining any fake customer row.
   Run ONLY as TEST DBA on EnterpriseProcess2_AI_Test, in an SSMS window.
   This proves RLS filtered SELECT for this session, not app authentication. */
USE [EnterpriseProcess2_AI_Test];
GO
SET XACT_ABORT ON;
IF DB_NAME() <> N'EnterpriseProcess2_AI_Test'
 THROW 56100, 'Wrong database.', 1;
IF OBJECT_ID(N'AgentProduct.MeetingIndex',N'U') IS NULL
 THROW 56101, 'Run commercial/sql/01_tenant_boundary_TEST_ONLY.sql first.', 1;
GO
DECLARE @a uniqueidentifier=NEWID(), @b uniqueidentifier=NEWID();
BEGIN TRY
 BEGIN TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID', @value=@a;
 INSERT AgentProduct.Tenant(TenantID,TenantName)
 VALUES (@a,N'FICTIONAL TENANT A'),(@b,N'FICTIONAL TENANT B');
 INSERT AgentProduct.MeetingIndex(TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES (@a,-91001,N'SIM-ACCESS-A',N'Fictional A',N'Draft'),
        (@b,-91002,N'SIM-ACCESS-B',N'Fictional B',N'Draft');
 IF (SELECT COUNT(*) FROM AgentProduct.MeetingIndex WHERE MeetingID IN(-91001,-91002))<>1
  THROW 56102, 'Isolation A failed.', 1;
 IF EXISTS(SELECT 1 FROM AgentProduct.MeetingIndex WHERE MeetingID=-91002)
  THROW 56103, 'A can see B data.', 1;

 EXEC sys.sp_set_session_context @key=N'AgentTenantID', @value=@b;
 IF (SELECT COUNT(*) FROM AgentProduct.MeetingIndex WHERE MeetingID IN(-91001,-91002))<>1
  THROW 56104, 'Isolation B failed.', 1;
 IF EXISTS(SELECT 1 FROM AgentProduct.MeetingIndex WHERE MeetingID=-91001)
  THROW 56105, 'B can see A data.', 1;

 EXEC sys.sp_set_session_context @key=N'AgentTenantID', @value=NULL;
 IF EXISTS(SELECT 1 FROM AgentProduct.MeetingIndex WHERE MeetingID IN(-91001,-91002))
  THROW 56106, 'Missing tenant context must see ZERO rows.', 1;

 ROLLBACK TRAN;
 PRINT 'PASS: tenant A, tenant B, and missing-context SELECT isolation.';
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID', @value=NULL;
 THROW;
END CATCH;
GO
