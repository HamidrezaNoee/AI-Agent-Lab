/* AI Agent commercial authorization v2 - TEST DB ONLY.
   ProcessMaker identities are imported into a local shadow directory; PM passwords
   are NEVER copied. Reporting hierarchy expands visibility, but never tenant scope.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test' THROW 57100,'Wrong database',1;
IF SCHEMA_ID(N'AgentProduct') IS NULL THROW 57101,'Run commercial base migrations first',1;
GO

IF OBJECT_ID(N'AgentProduct.UserDirectory',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.UserDirectory(
  TenantID uniqueidentifier NOT NULL,
  SubjectID nvarchar(180) NOT NULL,
  ProcessMakerUserUID varchar(64) NULL,
  ProcessMakerUsername nvarchar(120) NULL,
  DisplayName nvarchar(200) NOT NULL,
  Email nvarchar(320) NULL,
  UserKind varchar(20) NOT NULL CONSTRAINT DF_AP_UserDirectory_Kind DEFAULT('Expert'),
  IsEnabled bit NOT NULL CONSTRAINT DF_AP_UserDirectory_Enabled DEFAULT(1),
  LastSyncedAtUtc datetime2(0) NULL,
  CONSTRAINT PK_AP_UserDirectory PRIMARY KEY(TenantID,SubjectID),
  CONSTRAINT UQ_AP_UserDirectory_PM UNIQUE(TenantID,ProcessMakerUserUID),
  CONSTRAINT CK_AP_UserDirectory_Kind CHECK(UserKind IN('GodAdmin','SysAdmin','Manager','Expert')),
  CONSTRAINT FK_AP_UserDirectory_Membership FOREIGN KEY(TenantID,SubjectID)
    REFERENCES AgentProduct.Membership(TenantID,SubjectID)
 );
 CREATE INDEX IX_AP_UserDirectory_PMUsername ON AgentProduct.UserDirectory(TenantID,ProcessMakerUsername);
END;
GO

IF OBJECT_ID(N'AgentProduct.OrganizationNode',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.OrganizationNode(
  TenantID uniqueidentifier NOT NULL,
  NodeID bigint IDENTITY(1,1) NOT NULL,
  ParentNodeID bigint NULL,
  NodeCode nvarchar(80) NULL,
  NodeName nvarchar(200) NOT NULL,
  NodeType varchar(30) NOT NULL CONSTRAINT DF_AP_OrgNode_Type DEFAULT('Position'),
  IsEnabled bit NOT NULL CONSTRAINT DF_AP_OrgNode_Enabled DEFAULT(1),
  CONSTRAINT PK_AP_OrganizationNode PRIMARY KEY(TenantID,NodeID),
  CONSTRAINT UQ_AP_OrganizationNode_Code UNIQUE(TenantID,NodeCode),
  CONSTRAINT FK_AP_OrganizationNode_Parent FOREIGN KEY(TenantID,ParentNodeID)
    REFERENCES AgentProduct.OrganizationNode(TenantID,NodeID),
  CONSTRAINT CK_AP_OrganizationNode_Type CHECK(NodeType IN('Company','Department','Position','Team'))
 );
 CREATE INDEX IX_AP_OrganizationNode_Parent ON AgentProduct.OrganizationNode(TenantID,ParentNodeID);
END;
GO

IF OBJECT_ID(N'AgentProduct.UserOrganizationAssignment',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.UserOrganizationAssignment(
  TenantID uniqueidentifier NOT NULL,
  SubjectID nvarchar(180) NOT NULL,
  NodeID bigint NOT NULL,
  IsPrimary bit NOT NULL CONSTRAINT DF_AP_UserOrg_Primary DEFAULT(1),
  EffectiveFromUtc datetime2(0) NOT NULL CONSTRAINT DF_AP_UserOrg_From DEFAULT SYSUTCDATETIME(),
  EffectiveToUtc datetime2(0) NULL,
  CONSTRAINT PK_AP_UserOrganizationAssignment PRIMARY KEY(TenantID,SubjectID,NodeID,EffectiveFromUtc),
  CONSTRAINT FK_AP_UserOrg_User FOREIGN KEY(TenantID,SubjectID) REFERENCES AgentProduct.UserDirectory(TenantID,SubjectID),
  CONSTRAINT FK_AP_UserOrg_Node FOREIGN KEY(TenantID,NodeID) REFERENCES AgentProduct.OrganizationNode(TenantID,NodeID)
 );
 CREATE INDEX IX_AP_UserOrg_Node ON AgentProduct.UserOrganizationAssignment(TenantID,NodeID,SubjectID);
END;
GO

IF OBJECT_ID(N'AgentProduct.MeetingParticipantIndex',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.MeetingParticipantIndex(
  TenantID uniqueidentifier NOT NULL,
  MeetingID bigint NOT NULL,
  SubjectID nvarchar(180) NOT NULL,
  ParticipantRole varchar(20) NOT NULL,
  Source varchar(20) NOT NULL CONSTRAINT DF_AP_MeetingParticipant_Source DEFAULT('ProcessMaker'),
  CONSTRAINT PK_AP_MeetingParticipantIndex PRIMARY KEY(TenantID,MeetingID,SubjectID,ParticipantRole),
  CONSTRAINT CK_AP_MeetingParticipant_Role CHECK(ParticipantRole IN('Secretary','Chair','ActionOwner','Participant')),
  CONSTRAINT FK_AP_MeetingParticipant_Meeting FOREIGN KEY(TenantID,MeetingID) REFERENCES AgentProduct.MeetingIndex(TenantID,MeetingID),
  CONSTRAINT FK_AP_MeetingParticipant_User FOREIGN KEY(TenantID,SubjectID) REFERENCES AgentProduct.UserDirectory(TenantID,SubjectID)
 );
 CREATE INDEX IX_AP_MeetingParticipant_User ON AgentProduct.MeetingParticipantIndex(TenantID,SubjectID,MeetingID);
END;
GO

IF OBJECT_ID(N'AgentProduct.SystemSetting',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.SystemSetting(
  TenantID uniqueidentifier NOT NULL,
  SettingKey nvarchar(100) NOT NULL,
  SettingValue nvarchar(max) NULL,
  IsSecret bit NOT NULL CONSTRAINT DF_AP_SystemSetting_Secret DEFAULT(0),
  UpdatedBy nvarchar(180) NOT NULL,
  UpdatedAtUtc datetime2(0) NOT NULL CONSTRAINT DF_AP_SystemSetting_Time DEFAULT SYSUTCDATETIME(),
  CONSTRAINT PK_AP_SystemSetting PRIMARY KEY(TenantID,SettingKey)
 );
END;
GO

IF OBJECT_ID(N'AgentProduct.SyncRun',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.SyncRun(
  SyncRunID bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_AP_SyncRun PRIMARY KEY,
  TenantID uniqueidentifier NOT NULL,
  SourceSystem varchar(30) NOT NULL,
  StartedAtUtc datetime2(0) NOT NULL CONSTRAINT DF_AP_SyncRun_Start DEFAULT SYSUTCDATETIME(),
  CompletedAtUtc datetime2(0) NULL,
  Status varchar(20) NOT NULL,
  ReadCount int NOT NULL CONSTRAINT DF_AP_SyncRun_Read DEFAULT(0),
  UpsertCount int NOT NULL CONSTRAINT DF_AP_SyncRun_Upsert DEFAULT(0),
  DisabledCount int NOT NULL CONSTRAINT DF_AP_SyncRun_Disabled DEFAULT(0),
  ErrorMessage nvarchar(1000) NULL
 );
 CREATE INDEX IX_AP_SyncRun_TenantTime ON AgentProduct.SyncRun(TenantID,StartedAtUtc DESC);
END;
GO

IF OBJECT_ID(N'AgentProduct.AuditEvent',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.AuditEvent(
  AuditID bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_AP_AuditEvent PRIMARY KEY,
  TenantID uniqueidentifier NOT NULL,
  SubjectID nvarchar(180) NOT NULL,
  EventType nvarchar(100) NOT NULL,
  TargetType nvarchar(100) NULL,
  TargetKey nvarchar(200) NULL,
  Detail nvarchar(1000) NULL,
  CreatedAtUtc datetime2(0) NOT NULL CONSTRAINT DF_AP_AuditEvent_Time DEFAULT SYSUTCDATETIME()
 );
 CREATE INDEX IX_AP_AuditEvent_TenantTime ON AgentProduct.AuditEvent(TenantID,CreatedAtUtc DESC);
END;
GO

/* Add all new tenant tables to the existing RLS policy. */
DECLARE @targets TABLE(ObjectName sysname);
INSERT @targets VALUES
(N'AgentProduct.UserDirectory'),(N'AgentProduct.OrganizationNode'),
(N'AgentProduct.UserOrganizationAssignment'),(N'AgentProduct.MeetingParticipantIndex'),
(N'AgentProduct.SystemSetting'),(N'AgentProduct.SyncRun'),(N'AgentProduct.AuditEvent');
DECLARE @name sysname,@obj int,@ddl nvarchar(max);
DECLARE c CURSOR LOCAL FAST_FORWARD FOR SELECT ObjectName FROM @targets;
OPEN c; FETCH NEXT FROM c INTO @name;
WHILE @@FETCH_STATUS=0
BEGIN
 SET @obj=OBJECT_ID(@name);
 IF NOT EXISTS(SELECT 1 FROM sys.security_predicates WHERE target_object_id=@obj AND predicate_type_desc=N'FILTER')
 BEGIN
  SET @ddl=N'ALTER SECURITY POLICY AgentProduct.AgentProductTenantPolicy ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID) ON '+@name+N';';
  EXEC sys.sp_executesql @ddl;
 END;
 FETCH NEXT FROM c INTO @name;
END
CLOSE c; DEALLOCATE c;
GO

/* Expand old role constraint without weakening tenant membership checks. */
IF EXISTS(SELECT 1 FROM sys.check_constraints WHERE name=N'CK_AP_Membership_Role')
 ALTER TABLE AgentProduct.Membership DROP CONSTRAINT CK_AP_Membership_Role;
ALTER TABLE AgentProduct.Membership ADD CONSTRAINT CK_AP_Membership_Role
 CHECK(RoleCode IN('GodAdmin','SysAdmin','Manager','Expert'));
GO

CREATE OR ALTER FUNCTION AgentProduct.fn_descendant_nodes(
 @TenantID uniqueidentifier,@RootNodeID bigint
)
RETURNS @Nodes TABLE(NodeID bigint PRIMARY KEY)
AS
BEGIN
 DECLARE @changed int=1;
 INSERT @Nodes(NodeID) VALUES(@RootNodeID);
 WHILE @changed>0
 BEGIN
  INSERT @Nodes(NodeID)
   SELECT n.NodeID FROM AgentProduct.OrganizationNode n
   JOIN @Nodes p ON p.NodeID=n.ParentNodeID
   WHERE n.TenantID=@TenantID AND n.IsEnabled=1
     AND NOT EXISTS(SELECT 1 FROM @Nodes x WHERE x.NodeID=n.NodeID);
  SET @changed=@@ROWCOUNT;
 END
 RETURN;
END;
GO

CREATE OR ALTER FUNCTION AgentProduct.fn_subject_scope(
 @TenantID uniqueidentifier,@SubjectID nvarchar(180)
)
RETURNS @Subjects TABLE(SubjectID nvarchar(180) PRIMARY KEY)
AS
BEGIN
 INSERT @Subjects VALUES(@SubjectID);
 IF EXISTS(SELECT 1 FROM AgentProduct.Membership
           WHERE TenantID=@TenantID AND SubjectID=@SubjectID AND IsEnabled=1
             AND RoleCode IN('Manager','SysAdmin'))
 BEGIN
  IF EXISTS(SELECT 1 FROM AgentProduct.Membership WHERE TenantID=@TenantID AND SubjectID=@SubjectID AND RoleCode IN('SysAdmin'))
   INSERT @Subjects SELECT SubjectID FROM AgentProduct.Membership
    WHERE TenantID=@TenantID AND IsEnabled=1 AND SubjectID<>@SubjectID;
  ELSE
   INSERT @Subjects
    SELECT DISTINCT ua.SubjectID
    FROM AgentProduct.UserOrganizationAssignment me
    CROSS APPLY AgentProduct.fn_descendant_nodes(@TenantID,me.NodeID) d
    JOIN AgentProduct.UserOrganizationAssignment ua ON ua.TenantID=@TenantID AND ua.NodeID=d.NodeID
      AND ua.EffectiveToUtc IS NULL
    JOIN AgentProduct.Membership m ON m.TenantID=ua.TenantID AND m.SubjectID=ua.SubjectID AND m.IsEnabled=1
    WHERE me.TenantID=@TenantID AND me.SubjectID=@SubjectID AND me.EffectiveToUtc IS NULL
      AND NOT EXISTS(SELECT 1 FROM @Subjects x WHERE x.SubjectID=ua.SubjectID);
 END
 RETURN;
END;
GO

CREATE OR ALTER FUNCTION AgentProduct.fn_can_view_meeting(
 @TenantID uniqueidentifier,@SubjectID nvarchar(180),@MeetingID bigint
)
RETURNS TABLE WITH SCHEMABINDING AS RETURN
(
 SELECT CAST(CASE WHEN
   EXISTS(SELECT 1 FROM AgentProduct.Membership m
          WHERE m.TenantID=@TenantID AND m.SubjectID=@SubjectID AND m.IsEnabled=1
            AND m.RoleCode IN('SysAdmin'))
   OR EXISTS(SELECT 1 FROM AgentProduct.MeetingParticipantIndex p
             WHERE p.TenantID=@TenantID AND p.MeetingID=@MeetingID
               AND p.SubjectID IN(SELECT s.SubjectID FROM AgentProduct.fn_subject_scope(@TenantID,@SubjectID) s)
               AND p.ParticipantRole IN('Secretary','Chair','ActionOwner','Participant'))
   THEN 1 ELSE 0 END AS bit) AS Allowed
);
GO

IF USER_ID(N'AI_CommercialReader') IS NOT NULL
BEGIN
 GRANT SELECT ON AgentProduct.UserDirectory TO AI_CommercialReader;
 GRANT SELECT ON AgentProduct.OrganizationNode TO AI_CommercialReader;
 GRANT SELECT ON AgentProduct.UserOrganizationAssignment TO AI_CommercialReader;
 GRANT SELECT ON AgentProduct.MeetingParticipantIndex TO AI_CommercialReader;
 GRANT SELECT ON AgentProduct.SyncRun TO AI_CommercialReader;
 GRANT SELECT ON AgentProduct.AuditEvent TO AI_CommercialReader;
 GRANT SELECT ON OBJECT::AgentProduct.fn_descendant_nodes TO AI_CommercialReader;
 GRANT SELECT ON OBJECT::AgentProduct.fn_subject_scope TO AI_CommercialReader;
 GRANT SELECT ON OBJECT::AgentProduct.fn_can_view_meeting TO AI_CommercialReader;
 /* Deliberately NO SELECT on SystemSetting: connection secrets never go to reader/API responses. */
END;
GO
SELECT N'PASS: authorization-v2 schema created in isolated test database only.' AS Result;
