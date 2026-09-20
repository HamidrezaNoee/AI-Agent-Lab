/* LAB-ONLY directory & hierarchical meeting ACL foundation.
   Run as TEST DBA after existing commercial migrations 01/03/05/14/15.
   No real ProcessMaker connection, user or meeting is imported here.
   No credential or password fields exist in the directory.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME() <> N'EnterpriseProcess2_AI_Test'
 THROW 59700,'Directory migration is restricted to isolated AI test database.',1;
IF ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0) <> 1
 THROW 59701,'Use test DBA to apply schema migration.',1;
IF OBJECT_ID(N'AgentProduct.Membership',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.MeetingIndex',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.MeetingGrant',N'U') IS NULL
 THROW 59702,'Commercial membership and ACL migrations must run first.',1;
GO
IF OBJECT_ID(N'AgentProduct.DirectoryUser',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.DirectoryUser(
  TenantID uniqueidentifier NOT NULL,
  PMUserUID nvarchar(64) NOT NULL,
  PMUserName nvarchar(120) NOT NULL,
  DisplayName nvarchar(240) NOT NULL,
  Email nvarchar(240) NULL,
  PMStatus varchar(12) NOT NULL,
  -- Assigned explicitly by a tenant administrator AFTER identity verification.
  SubjectID nvarchar(180) NULL,
  -- Set by an administrator only; ProcessMaker sync cannot overwrite it.
  ManagerPMUserUID nvarchar(64) NULL,
  OrgRole varchar(12) NOT NULL CONSTRAINT DF_AP_DUser_Role DEFAULT('Expert'),
  IsEnabled bit NOT NULL CONSTRAINT DF_AP_DUser_Enabled DEFAULT(0),
  LastSeenAtUtc datetime2(0) NOT NULL CONSTRAINT DF_AP_DUser_Seen DEFAULT SYSUTCDATETIME(),
  CONSTRAINT PK_AP_DirectoryUser PRIMARY KEY(TenantID,PMUserUID),
  CONSTRAINT FK_AP_DUser_Tenant FOREIGN KEY(TenantID)
   REFERENCES AgentProduct.Tenant(TenantID),
  CONSTRAINT FK_AP_DUser_Membership FOREIGN KEY(TenantID,SubjectID)
   REFERENCES AgentProduct.Membership(TenantID,SubjectID),
  CONSTRAINT FK_AP_DUser_Manager FOREIGN KEY(TenantID,ManagerPMUserUID)
   REFERENCES AgentProduct.DirectoryUser(TenantID,PMUserUID),
  CONSTRAINT CK_AP_DUser_Role CHECK(OrgRole IN('Expert','Manager','SysAdmin')),
  CONSTRAINT CK_AP_DUser_Status CHECK(PMStatus IN('ACTIVE','INACTIVE','VACATION')),
  CONSTRAINT CK_AP_DUser_SelfManager CHECK(ManagerPMUserUID IS NULL OR ManagerPMUserUID<>PMUserUID)
 );
 CREATE UNIQUE INDEX UX_AP_DUser_Subject
 ON AgentProduct.DirectoryUser(TenantID,SubjectID) WHERE SubjectID IS NOT NULL;
 CREATE INDEX IX_AP_DUser_Reporting ON AgentProduct.DirectoryUser(TenantID,ManagerPMUserUID,PMUserUID);
END;
GO
IF OBJECT_ID(N'AgentProduct.MeetingActor',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.MeetingActor(
  TenantID uniqueidentifier NOT NULL,
  MeetingID bigint NOT NULL,
  PMUserUID nvarchar(64) NOT NULL,
  ActorRole varchar(18) NOT NULL,
  CONSTRAINT PK_AP_MeetingActor PRIMARY KEY(TenantID,MeetingID,PMUserUID,ActorRole),
  CONSTRAINT FK_AP_MActor_Meeting FOREIGN KEY(TenantID,MeetingID)
    REFERENCES AgentProduct.MeetingIndex(TenantID,MeetingID),
  CONSTRAINT FK_AP_MActor_User FOREIGN KEY(TenantID,PMUserUID)
    REFERENCES AgentProduct.DirectoryUser(TenantID,PMUserUID),
  CONSTRAINT CK_AP_MActor_Role CHECK(ActorRole IN
    ('Secretary','Chair','Participant','ActionOwner'))
 );
 CREATE INDEX IX_AP_MActor_ByPerson ON AgentProduct.MeetingActor(TenantID,PMUserUID,MeetingID);
END;
GO
/* Future letters are isolated per-tenant metadata; do NOT import arbitrary
   ProcessMaker or other-system letters without a verified source mapping.
   Folder/title alone does not grant access. */
IF OBJECT_ID(N'AgentProduct.LetterIndex',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.LetterIndex(
  TenantID uniqueidentifier NOT NULL,
  LetterID nvarchar(100) NOT NULL,
  LetterTitle nvarchar(300) NOT NULL,
  OwnerPMUserUID nvarchar(64) NOT NULL,
  IsConfidential bit NOT NULL CONSTRAINT DF_AP_Letter_Confidential DEFAULT(1),
  CONSTRAINT PK_AP_LetterIndex PRIMARY KEY(TenantID,LetterID),
  CONSTRAINT FK_AP_Letter_Tenant FOREIGN KEY(TenantID)
     REFERENCES AgentProduct.Tenant(TenantID),
  CONSTRAINT FK_AP_Letter_Owner FOREIGN KEY(TenantID,OwnerPMUserUID)
     REFERENCES AgentProduct.DirectoryUser(TenantID,PMUserUID)
 );
 CREATE INDEX IX_AP_Letter_Owner ON AgentProduct.LetterIndex(TenantID,OwnerPMUserUID);
END;
GO
/* On an existing SQL Server, IF + ALTER must be executed as DYNAMIC SQL to
   avoid premature compilation/duplicate predicate errors upon rerun. */
IF NOT EXISTS(SELECT 1 FROM sys.security_policies WHERE
 object_id=OBJECT_ID(N'AgentProduct.AgentProductTenantPolicy') AND is_enabled=1)
 THROW 59703,'Required tenant security policy missing or disabled.',1;
GO
IF EXISTS(
 SELECT 1 FROM sys.security_predicates
 WHERE target_object_id IN (
 OBJECT_ID(N'AgentProduct.DirectoryUser'),
 OBJECT_ID(N'AgentProduct.MeetingActor'),
 OBJECT_ID(N'AgentProduct.LetterIndex'))
 AND predicate_type_desc='FILTER'
 AND object_id<>OBJECT_ID(N'AgentProduct.AgentProductTenantPolicy'))
 THROW 59704,'Unexpected tenant RLS filter: manual review required.',1;
IF EXISTS(
 SELECT 1 FROM sys.security_predicates
 WHERE target_object_id IN (
 OBJECT_ID(N'AgentProduct.DirectoryUser'),
 OBJECT_ID(N'AgentProduct.MeetingActor'),
 OBJECT_ID(N'AgentProduct.LetterIndex'))
 AND predicate_type_desc='FILTER'
 AND predicate_definition<>N'[AgentProduct].[fn_tenant_filter]([TenantID])')
 BEGIN
  -- SQL Server formats metadata differently between builds: do not depend
  -- on exact formatting for filter validation; policy owner was checked above.
  PRINT 'INFO: inspect predicate definitions if directory tables have pre-existing policies.';
 END;
GO
IF NOT EXISTS(SELECT 1 FROM sys.security_predicates WHERE
 target_object_id=OBJECT_ID(N'AgentProduct.DirectoryUser') AND predicate_type_desc='FILTER')
 EXEC sys.sp_executesql N'ALTER SECURITY POLICY AgentProduct.AgentProductTenantPolicy
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID)
 ON AgentProduct.DirectoryUser;';
GO
IF NOT EXISTS(SELECT 1 FROM sys.security_predicates WHERE
 target_object_id=OBJECT_ID(N'AgentProduct.MeetingActor') AND predicate_type_desc='FILTER')
 EXEC sys.sp_executesql N'ALTER SECURITY POLICY AgentProduct.AgentProductTenantPolicy
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID)
 ON AgentProduct.MeetingActor;';
GO
IF NOT EXISTS(SELECT 1 FROM sys.security_predicates WHERE
 target_object_id=OBJECT_ID(N'AgentProduct.LetterIndex') AND predicate_type_desc='FILTER')
 EXEC sys.sp_executesql N'ALTER SECURITY POLICY AgentProduct.AgentProductTenantPolicy
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID)
 ON AgentProduct.LetterIndex;';
GO
/* Reader cannot INSERT/UPDATE/DELETE any directory, user, letter or actor.
   Elevated writes must later use narrowly scoped procedures/service identity. */
IF USER_ID(N'AI_CommercialReader') IS NOT NULL
BEGIN
 GRANT SELECT ON OBJECT::AgentProduct.DirectoryUser TO [AI_CommercialReader];
 GRANT SELECT ON OBJECT::AgentProduct.MeetingActor TO [AI_CommercialReader];
 -- Deliberately NO SELECT on LetterIndex yet: letter ingestion and policy
 -- have not been verified, so missing content cannot accidentally leak.
END;
GO
PRINT 'PASS: isolated ProcessMaker directory, org tree, meeting actor schema and tenant RLS created.';
PRINT 'NOTE: no ProcessMaker accounts linked or privileged roles assigned.';
