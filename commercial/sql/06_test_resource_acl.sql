/* Rollback-only ACL regression: two subjects in ONE tenant, plus missing tenant context.
   Verify that tenant RLS alone is NOT enough; individual resource grants matter.
*/
USE [EnterpriseProcess2_AI_Test];
GO
SET XACT_ABORT ON;
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test'
 THROW 56500,'Wrong database',1;
IF OBJECT_ID(N'AgentProduct.MeetingGrant',N'U') IS NULL
 THROW 56501,'Run commercial/sql/05_resource_acl_TEST_ONLY.sql first',1;
GO
DECLARE @tenant uniqueidentifier=NEWID(),@d1 uniqueidentifier=NEWID(),@d2 uniqueidentifier=NEWID();
BEGIN TRY
 BEGIN TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID', @value=@tenant;
 INSERT AgentProduct.Tenant(TenantID,TenantName)
 VALUES(@tenant,N'FICTIONAL ACL TEST TENANT');
 INSERT AgentProduct.Membership(TenantID,SubjectID,RoleCode)
 VALUES(@tenant,N'alice-test',N'Viewer'),(@tenant,N'bob-test',N'Viewer');
 INSERT AgentProduct.MeetingIndex(TenantID,MeetingID,MeetingNo,MeetingTitle,MeetingStatus)
 VALUES(@tenant,-92001,N'SIM-ACL-A',N'FICTIONAL ALICE ONLY',N'Draft'),
       (@tenant,-92002,N'SIM-ACL-B',N'FICTIONAL BOB ONLY',N'Draft');
 INSERT AgentProduct.MeetingGrant(TenantID,MeetingID,SubjectID)
 VALUES(@tenant,-92001,N'alice-test'),(@tenant,-92002,N'bob-test');
 INSERT AgentProduct.DocumentIndex(TenantID,DocumentID,DocumentTitle,CurrentVersion,IsActive)
 VALUES(@tenant,@d1,N'FICTIONAL ALICE DOCUMENT',1,1),
       (@tenant,@d2,N'FICTIONAL BOB DOCUMENT',1,1);
 INSERT AgentProduct.DocumentChunk(TenantID,DocumentID,ChunkNo,DocumentVersion,ChunkText)
 VALUES(@tenant,@d1,1,1,N'ALICE SECRET TEST CHUNK'),
       (@tenant,@d2,1,1,N'BOB SECRET TEST CHUNK');
 INSERT AgentProduct.DocumentGrant(TenantID,DocumentID,SubjectID)
 VALUES(@tenant,@d1,N'alice-test'),(@tenant,@d2,N'bob-test');

 IF (SELECT COUNT(*) FROM AgentProduct.MeetingIndex m
     JOIN AgentProduct.MeetingGrant g ON g.TenantID=m.TenantID AND g.MeetingID=m.MeetingID
     WHERE m.TenantID=@tenant AND g.SubjectID=N'alice-test')<>1
  THROW 56502,'Alice meeting count incorrect',1;
 IF EXISTS(SELECT 1 FROM AgentProduct.MeetingGrant
           WHERE SubjectID=N'alice-test' AND MeetingID=-92002)
  THROW 56503,'Alice has Bob meeting grant',1;
 IF (SELECT COUNT(*) FROM AgentProduct.DocumentIndex d
     JOIN AgentProduct.DocumentGrant g ON g.TenantID=d.TenantID AND g.DocumentID=d.DocumentID
     WHERE d.TenantID=@tenant AND g.SubjectID=N'bob-test')<>1
  THROW 56504,'Bob document count incorrect',1;
 IF EXISTS(SELECT 1 FROM AgentProduct.DocumentGrant
           WHERE SubjectID=N'bob-test' AND DocumentID=@d1)
  THROW 56505,'Bob has Alice document grant',1;

 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
 IF EXISTS(SELECT 1 FROM AgentProduct.DocumentIndex WHERE TenantID=@tenant)
  THROW 56506,'Missing tenant context leaked a document',1;
 IF EXISTS(SELECT 1 FROM AgentProduct.MeetingIndex WHERE TenantID=@tenant)
  THROW 56507,'Missing tenant context leaked a meeting',1;
 ROLLBACK TRAN;
 PRINT 'PASS: same-tenant user meeting/document grants and missing-context isolation.';
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
 THROW;
END CATCH;
GO
