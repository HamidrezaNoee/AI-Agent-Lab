/* Verify commercial SQL reader *without* knowing or exposing its password.
   Run ONLY as TEST sysadmin in EnterpriseProcess2_AI_Test after grants 04,05,07.
   Read-only checks. No change to user roles, schema or test data.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test'
 THROW 59100,'Wrong database',1;
IF ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0)<>1
 THROW 59101,'Use the test SQL sysadmin to impersonate the lab reader.',1;
IF SUSER_ID(N'AI_CommercialReader') IS NULL
 THROW 59102,'Create the separate SQL login AI_CommercialReader first.',1;
GO
BEGIN TRY
 EXECUTE AS LOGIN=N'AI_CommercialReader';
 DECLARE @db sysname=DB_NAME(), @user sysname=USER_NAME();
 DECLARE @admin int=ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0),
         @owner int=ISNULL(IS_MEMBER(N'db_owner'),0),
         @legacy int=ISNULL(HAS_PERMS_BY_NAME(N'MTG.Meeting',N'OBJECT',N'SELECT'),0),
         @legacyAI int=ISNULL(HAS_PERMS_BY_NAME(N'AI.Document',N'OBJECT',N'SELECT'),0),
         @write int=ISNULL(HAS_PERMS_BY_NAME(N'AgentProduct.Tenant',N'OBJECT',N'INSERT'),0),
         @canRead int=ISNULL(HAS_PERMS_BY_NAME(N'AgentProduct.MeetingIndex',N'OBJECT',N'SELECT'),0),
         @canGrant int=ISNULL(HAS_PERMS_BY_NAME(N'AgentProduct.MeetingGrant',N'OBJECT',N'SELECT'),0),
         @canDoc int=ISNULL(HAS_PERMS_BY_NAME(N'AgentProduct.DocumentChunk',N'OBJECT',N'SELECT'),0),
         @canReserve int=ISNULL(HAS_PERMS_BY_NAME(N'AgentProduct.ReserveChatRequest',N'OBJECT',N'EXECUTE'),0);
 IF @db<>N'EnterpriseProcess2_AI_Test' OR @user<>N'AI_CommercialReader'
  THROW 59103,'Reader is not mapped to the intended test database.',1;
 IF @admin<>0 OR @owner<>0 OR @legacy<>0 OR @legacyAI<>0 OR @write<>0
  THROW 59104,'Reader has unsafe privileges (admin, legacy read or write).',1;
 IF @canRead<>1 OR @canGrant<>1 OR @canDoc<>1 OR @canReserve<>1
  THROW 59105,'Reader is missing some AgentProduct SELECT/EXEC permissions.',1;
 REVERT;
 PRINT 'PASS: separate commercial SQL login has limited AgentProduct permissions.';
 PRINT 'PASS: no admin role, direct tenant INSERT or unscoped MTG/AI reads.';
END TRY
BEGIN CATCH
 DECLARE @errmsg nvarchar(2048)=ERROR_MESSAGE(),
         @errno int=ERROR_NUMBER();
 IF ORIGINAL_LOGIN()<>SUSER_SNAME() REVERT;
 THROW 59106,'Commercial reader permission verification failed; check grants and account roles.',1;
END CATCH;
GO
