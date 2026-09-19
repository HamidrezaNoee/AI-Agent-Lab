/* TEST ONLY. Run as test DBA AFTER 01,03,05,07 migrations.
   Each case uses a random synthetic tenant and leaves no persistent data.
   None of these queries touch the legacy MTG/AI tables.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test'
 THROW 56900,'Wrong database',1;
IF OBJECT_ID(N'AgentProduct.ReserveChatRequest',N'P') IS NULL
 OR OBJECT_ID(N'AgentProduct.FinalizeChatRequest',N'P') IS NULL
 THROW 56901,'Run commercial/sql/07_chat_quota_TEST_ONLY.sql first',1;
GO
DECLARE @tenant uniqueidentifier=NEWID(), @rid uniqueidentifier=NEWID();
BEGIN TRY
 BEGIN TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=@tenant;
 INSERT AgentProduct.Tenant(TenantID,TenantName)
 VALUES(@tenant,N'FICTIONAL CHAT QUOTA TEST');
 INSERT AgentProduct.Membership(TenantID,SubjectID,RoleCode)
 VALUES(@tenant,N'quota-test-user',N'Viewer');
 INSERT AgentProduct.Subscription
 (TenantID,PlanCode,IsActive,ExpiresAtUtc,MonthlyRequestLimit)
 VALUES(@tenant,N'FICTIONAL',1,DATEADD(DAY,7,SYSUTCDATETIME()),2);
 EXEC AgentProduct.ReserveChatRequest
  @TenantID=@tenant,@SubjectID=N'quota-test-user',
  @RequestID=@rid,@ModelName=N'gpt-4.1-mini';
 IF (SELECT COUNT(*) FROM AgentProduct.ChatRequest
     WHERE TenantID=@tenant AND Status='Reserved')<>1
  THROW 56902,'Reservation not persisted inside transaction',1;
 EXEC AgentProduct.FinalizeChatRequest
  @TenantID=@tenant,@RequestID=@rid,@State='Completed',
  @InputTokens=20,@OutputTokens=10;
 IF (SELECT COUNT(*) FROM AgentProduct.ChatRequest
     WHERE TenantID=@tenant AND Status='Completed'
       AND InputTokens=20 AND OutputTokens=10)<>1
  THROW 56903,'Completion metering failed',1;
 ROLLBACK TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
 PRINT 'PASS: chat quota reserve and usage finalization (all fictional data rolled back).';
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
 THROW;
END CATCH;
GO
DECLARE @tenant uniqueidentifier=NEWID(), @r1 uniqueidentifier=NEWID(),
 @r2 uniqueidentifier=NEWID(), @expectedError int=0;
BEGIN TRY
 BEGIN TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=@tenant;
 INSERT AgentProduct.Tenant(TenantID,TenantName)
 VALUES(@tenant,N'FICTIONAL ONE-REQUEST TENANT');
 INSERT AgentProduct.Membership(TenantID,SubjectID,RoleCode)
 VALUES(@tenant,N'quota-test-user',N'Viewer');
 INSERT AgentProduct.Subscription
 (TenantID,PlanCode,IsActive,ExpiresAtUtc,MonthlyRequestLimit)
 VALUES(@tenant,N'FICTIONAL',1,DATEADD(DAY,7,SYSUTCDATETIME()),1);
 EXEC AgentProduct.ReserveChatRequest
  @TenantID=@tenant,@SubjectID=N'quota-test-user',
  @RequestID=@r1,@ModelName=N'gpt-4.1-mini';
 -- Must throw 56806; XACT_ABORT may roll back the outer test transaction.
 EXEC AgentProduct.ReserveChatRequest
  @TenantID=@tenant,@SubjectID=N'quota-test-user',
  @RequestID=@r2,@ModelName=N'gpt-4.1-mini';
 IF @@TRANCOUNT>0 ROLLBACK TRAN;
 THROW 56904,'Quota overflow was unexpectedly allowed',1;
END TRY
BEGIN CATCH
 SET @expectedError=ERROR_NUMBER();
 IF @@TRANCOUNT>0 ROLLBACK TRAN;
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
 IF @expectedError<>56806 THROW;
 PRINT 'PASS: second chat request rejected at monthly quota (all fictional data rolled back).';
END CATCH;
GO
BEGIN TRY
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
 DECLARE @missingTenant uniqueidentifier=NEWID(),@missingRid uniqueidentifier=NEWID();
 EXEC AgentProduct.ReserveChatRequest
  @TenantID=@missingTenant,@SubjectID=N'quota-test-user',
  @RequestID=@missingRid,@ModelName=N'gpt-4.1-mini';
 THROW 56905,'Missing tenant context was unexpectedly accepted',1;
END TRY
BEGIN CATCH
 DECLARE @errorNumber int=ERROR_NUMBER();
 IF @@TRANCOUNT>0 ROLLBACK TRAN;
 IF @errorNumber<>56802 THROW;
 PRINT 'PASS: missing SQL tenant context rejected before quota reservation.';
END CATCH;
GO
