/* Modular commercial entitlements (LAB ONLY).
   Run as TEST DBA after migrations 01/03/05/07 on EnterpriseProcess2_AI_Test.
   Module 1=core; optional module 2=secretary, 3=analytics, 4=monitoring.
   Missing/expired/not-licensed/disabled row => DENY. No payment integration.
   NEVER run in operational EnterpriseProcess / EnterpriseProcess2.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test'
 THROW 59200,'LAB ONLY: wrong database.',1;
IF ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0)<>1
 THROW 59201,'Run module migration with TEST DBA.',1;
IF OBJECT_ID(N'AgentProduct.Tenant',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.Membership',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.AuditEvent',N'U') IS NULL
 THROW 59202,'Commercial dependencies missing or invalid.',1;
GO
IF OBJECT_ID(N'AgentProduct.TenantModule',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.TenantModule(
  TenantID uniqueidentifier NOT NULL,
  ModuleCode tinyint NOT NULL CONSTRAINT CK_AP_TModule_Code CHECK(ModuleCode IN(2,3,4)),
  IsLicensed bit NOT NULL CONSTRAINT DF_AP_TModule_Licensed DEFAULT(0),
  IsEnabled bit NOT NULL CONSTRAINT DF_AP_TModule_Enabled DEFAULT(0),
  LicenseUntilUtc datetime2(0) NULL,
  ModifiedAtUtc datetime2(0) NOT NULL CONSTRAINT DF_AP_TModule_Modified DEFAULT SYSUTCDATETIME(),
  CONSTRAINT PK_AP_TenantModule PRIMARY KEY(TenantID,ModuleCode),
  CONSTRAINT FK_AP_TenantModule_Tenant FOREIGN KEY(TenantID) REFERENCES AgentProduct.Tenant(TenantID)
 );
END;
GO
/* Ensure only the expected enabled tenant RLS policy owns the filter. */
IF NOT EXISTS(SELECT 1 FROM sys.security_policies
 WHERE object_id=OBJECT_ID(N'AgentProduct.AgentProductTenantPolicy') AND is_enabled=1)
 THROW 59203,'Expected tenant row-security policy is missing/disabled.',1;
IF EXISTS(SELECT 1 FROM sys.security_predicates
 WHERE target_object_id=OBJECT_ID(N'AgentProduct.TenantModule')
   AND predicate_type_desc='FILTER'
   AND object_id<>OBJECT_ID(N'AgentProduct.AgentProductTenantPolicy'))
 THROW 59204,'Unexpected RLS FILTER on TenantModule.',1;
IF NOT EXISTS(SELECT 1 FROM sys.security_predicates
 WHERE target_object_id=OBJECT_ID(N'AgentProduct.TenantModule')
   AND predicate_type_desc='FILTER')
 EXEC sys.sp_executesql N'ALTER SECURITY POLICY AgentProduct.AgentProductTenantPolicy
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID)
 ON AgentProduct.TenantModule;';
GO
/* Existing agent AuditEvent stores enable/disable audit. Only a licensed,
   tenant-local Owner/Admin can change IsEnabled. Cannot self-grant license.
   EXECUTE AS OWNER necessary because API login cannot UPDATE entitlement. */
CREATE OR ALTER PROCEDURE AgentProduct.SetTenantModuleEnabled
 @TenantID uniqueidentifier, @SubjectID nvarchar(180),
 @ModuleCode tinyint, @Enabled bit
 WITH EXECUTE AS OWNER
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 IF @ModuleCode NOT IN(2,3,4) OR @ModuleCode IS NULL OR @Enabled IS NULL
  THROW 59210,'Invalid optional module or enabled flag.',1;
 IF @TenantID IS NULL OR TRY_CONVERT(uniqueidentifier,SESSION_CONTEXT(N'AgentTenantID'))<>@TenantID
  OR SESSION_CONTEXT(N'AgentTenantID') IS NULL
  THROW 59211,'Invalid tenant context.',1;
 IF @SubjectID IS NULL OR LEN(LTRIM(RTRIM(@SubjectID)))=0
  THROW 59212,'Missing verified user subject.',1;
 BEGIN TRAN;
 IF NOT EXISTS(
 SELECT 1 FROM AgentProduct.Membership m
 JOIN AgentProduct.Tenant t ON t.TenantID=m.TenantID
 JOIN AgentProduct.Subscription s ON s.TenantID=m.TenantID
 WHERE m.TenantID=@TenantID AND m.SubjectID=@SubjectID
 AND m.RoleCode IN('Owner','Admin') AND m.IsEnabled=1 AND t.IsEnabled=1
 AND s.IsActive=1 AND s.ExpiresAtUtc>SYSUTCDATETIME()
 )
  THROW 59213,'Tenant administrator membership/subscription required.',1;
 IF NOT EXISTS(
 SELECT 1 FROM AgentProduct.TenantModule WITH(UPDLOCK,HOLDLOCK)
 WHERE TenantID=@TenantID AND ModuleCode=@ModuleCode
 AND IsLicensed=1 AND LicenseUntilUtc>SYSUTCDATETIME()
 )
  THROW 59214,'No active purchased license for the requested module.',1;
 UPDATE AgentProduct.TenantModule
 SET IsEnabled=@Enabled,ModifiedAtUtc=SYSUTCDATETIME()
 WHERE TenantID=@TenantID AND ModuleCode=@ModuleCode;
 INSERT AgentProduct.AuditEvent
 (TenantID,SubjectID,RequestID,EventType,ResourceType,ResourceID)
 VALUES(@TenantID,@SubjectID,NEWID(),
  CASE WHEN @Enabled=1 THEN 'ModuleEnabled' ELSE 'ModuleDisabled' END,
  'TenantModule',CONVERT(nvarchar(10),@ModuleCode));
 COMMIT TRAN;
 SELECT ModuleCode,IsLicensed,IsEnabled,LicenseUntilUtc
 FROM AgentProduct.TenantModule WHERE TenantID=@TenantID AND ModuleCode=@ModuleCode;
END;
GO
/* Standalone API account gets only SELECT on entitlement rows and EXECUTE
   on the narrow audited toggle; it cannot set IsLicensed or LicenseUntilUtc. */
IF USER_ID(N'AI_CommercialReader') IS NOT NULL
BEGIN
 GRANT SELECT ON OBJECT::AgentProduct.TenantModule TO [AI_CommercialReader];
 GRANT EXECUTE ON OBJECT::AgentProduct.SetTenantModuleEnabled TO [AI_CommercialReader];
END;
GO
PRINT 'PASS: tenant-isolated optional module entitlement schema and admin toggle created.';
PRINT 'NOTE: no modules are licensed by this migration. Payment fulfillment remains separate.';
