/* Read-only verification after LAB migrations 14,15 and fixtures 16,17.
   DB administrator only. Does NOT create records, enable modules or use OpenAI.
*/
USE [EnterpriseProcess2_AI_Test];
GO
SET NOCOUNT ON;
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test'
 THROW 59600,'Wrong database.',1;
IF ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0)<>1
 THROW 59601,'Use TEST SQL admin.',1;
IF OBJECT_ID(N'AgentProduct.TenantModule',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.ActionIndex',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.SetTenantModuleEnabled',N'P') IS NULL
 THROW 59602,'Run modules SQL 14 and 15 first.',1;
IF NOT EXISTS(SELECT 1 FROM sys.security_policies
 WHERE object_id=OBJECT_ID(N'AgentProduct.AgentProductTenantPolicy') AND is_enabled=1)
 THROW 59603,'Expected enabled RLS policy missing.',1;
IF (SELECT COUNT(*) FROM sys.security_predicates
 WHERE object_id=OBJECT_ID(N'AgentProduct.AgentProductTenantPolicy')
 AND target_object_id IN (OBJECT_ID(N'AgentProduct.TenantModule'),
                          OBJECT_ID(N'AgentProduct.ActionIndex'))
 AND predicate_type_desc='FILTER')<>2
 THROW 59604,'Modules/action tenant RLS filters missing.',1;
GO
DECLARE @a uniqueidentifier='11111111-1111-4111-8111-111111111111';
EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=@a;
DECLARE @meetings int=(SELECT COUNT(*) FROM AgentProduct.MeetingIndex
 WHERE TenantID=@a AND MeetingID BETWEEN 910001 AND 910100);
DECLARE @actions int=(SELECT COUNT(*) FROM AgentProduct.ActionIndex
 WHERE TenantID=@a AND MeetingID BETWEEN 910001 AND 910100);
IF @meetings<>100 OR @actions<>300
 THROW 59605,'Expected 100 synthetic meetings and 300 actions not present; run 16 ONCE.',1;
IF (SELECT COUNT(*) FROM AgentProduct.TenantModule
 WHERE TenantID=@a AND IsLicensed=1 AND LicenseUntilUtc>SYSUTCDATETIME())<>3
 THROW 59606,'Synthetic three-module license fixture missing; run 17 ONCE.',1;
IF NOT EXISTS(SELECT 1 FROM AgentProduct.Membership
 WHERE TenantID=@a AND SubjectID=N'lab-admin' AND RoleCode=N'Admin')
 THROW 59607,'Synthetic admin membership missing; run 17 ONCE.',1;
PRINT 'PASS: 100 distinct automotive meeting indexes and 300 action indexes exist in isolated TEST tenant A.';
PRINT 'PASS: three synthetic purchased modules and test admin exist in tenant A.';
PRINT 'PASS: tenant RLS filters exist on module and action index tables.';
EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
GO
