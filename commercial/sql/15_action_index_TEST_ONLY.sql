/* Optional monitoring/action projection, isolated synthetic LAB only.
   Requires commercial migrations 01,03,05 and 14 first.
   This is NOT a copy of operational ProcessMaker action records.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test'
 THROW 59300,'Wrong test database.',1;
IF ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0)<>1
 THROW 59301,'Run as test DBA.',1;
IF OBJECT_ID(N'AgentProduct.MeetingGrant',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.TenantModule',N'U') IS NULL
 THROW 59302,'Run migrations 05 and 14 first.',1;
GO
IF OBJECT_ID(N'AgentProduct.ActionIndex',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.ActionIndex(
  TenantID uniqueidentifier NOT NULL,
  MeetingID bigint NOT NULL,
  ActionNo nvarchar(24) NOT NULL,
  ActionTitle nvarchar(1000) NOT NULL,
  OwnerUnit nvarchar(100) NOT NULL,
  DueAtUtc datetime2(0) NOT NULL,
  ProgressPercent tinyint NOT NULL
   CONSTRAINT CK_AP_Action_Progress CHECK(ProgressPercent BETWEEN 0 AND 100),
  IsClosed bit NOT NULL CONSTRAINT DF_AP_Action_Closed DEFAULT(0),
  CONSTRAINT PK_AP_ActionIndex PRIMARY KEY(TenantID,MeetingID,ActionNo),
  CONSTRAINT FK_AP_ActionIndex_Meeting FOREIGN KEY(TenantID,MeetingID)
   REFERENCES AgentProduct.MeetingIndex(TenantID,MeetingID)
 );
 CREATE INDEX IX_AP_ActionIndex_Due
 ON AgentProduct.ActionIndex(TenantID,DueAtUtc,ProgressPercent)
 INCLUDE(MeetingID,IsClosed);
END;
GO
IF NOT EXISTS(SELECT 1 FROM sys.security_policies WHERE
 object_id=OBJECT_ID(N'AgentProduct.AgentProductTenantPolicy') AND is_enabled=1)
 THROW 59303,'Tenant RLS policy missing or disabled.',1;
IF EXISTS(SELECT 1 FROM sys.security_predicates WHERE
 target_object_id=OBJECT_ID(N'AgentProduct.ActionIndex')
 AND predicate_type_desc='FILTER'
 AND object_id<>OBJECT_ID(N'AgentProduct.AgentProductTenantPolicy'))
 THROW 59304,'Unexpected ActionIndex filter.',1;
IF NOT EXISTS(SELECT 1 FROM sys.security_predicates WHERE
 target_object_id=OBJECT_ID(N'AgentProduct.ActionIndex')
 AND predicate_type_desc='FILTER')
 EXEC sys.sp_executesql N'ALTER SECURITY POLICY AgentProduct.AgentProductTenantPolicy
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID)
 ON AgentProduct.ActionIndex;';
GO
IF USER_ID(N'AI_CommercialReader') IS NOT NULL
 GRANT SELECT ON OBJECT::AgentProduct.ActionIndex TO [AI_CommercialReader];
GO
PRINT 'PASS: lab ActionIndex available to read-only monitoring module.';
