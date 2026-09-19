/*
COMMERCIAL SECURITY FOUNDATION — isolated synthetic lab only.
Does NOT modify MTG tables and does NOT migrate real ProcessMaker records.
Run as TEST DBA on EnterpriseProcess2_AI_Test. No real customer content.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME() <> N'EnterpriseProcess2_AI_Test'
    THROW 56001, 'Wrong database: commercial security lab only.', 1;
IF OBJECT_ID(N'MTG.Meeting',N'U') IS NULL
    THROW 56002, 'Expected synthetic MTG lab is missing.', 1;
GO
IF SCHEMA_ID(N'AgentProduct') IS NULL
    EXEC(N'CREATE SCHEMA AgentProduct AUTHORIZATION dbo');
GO
IF OBJECT_ID(N'AgentProduct.Tenant',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.Tenant(
  TenantID uniqueidentifier NOT NULL CONSTRAINT PK_AP_Tenant PRIMARY KEY,
  TenantName nvarchar(200) NOT NULL,
  IsEnabled bit NOT NULL CONSTRAINT DF_AP_Tenant_Enabled DEFAULT(1),
  CreatedAtUtc datetime2(0) NOT NULL CONSTRAINT DF_AP_Tenant_Created DEFAULT SYSUTCDATETIME()
 );
END;
GO
IF OBJECT_ID(N'AgentProduct.MeetingIndex',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.MeetingIndex(
  TenantID uniqueidentifier NOT NULL,
  MeetingID bigint NOT NULL,
  MeetingNo nvarchar(50) NOT NULL,
  MeetingTitle nvarchar(1000) NOT NULL,
  MeetingStatus varchar(40) NOT NULL,
  CONSTRAINT PK_AP_MeetingIndex PRIMARY KEY(TenantID,MeetingID),
  CONSTRAINT FK_AP_MeetingIndex_Tenant FOREIGN KEY(TenantID) REFERENCES AgentProduct.Tenant(TenantID)
 );
 CREATE INDEX IX_AP_MeetingIndex_Number ON AgentProduct.MeetingIndex(TenantID,MeetingNo);
END;
GO
IF OBJECT_ID(N'AgentProduct.DocumentIndex',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.DocumentIndex(
  TenantID uniqueidentifier NOT NULL,
  DocumentID uniqueidentifier NOT NULL,
  DocumentTitle nvarchar(300) NOT NULL,
  CurrentVersion int NOT NULL CONSTRAINT CK_AP_Doc_Version CHECK(CurrentVersion>=1),
  IsActive bit NOT NULL CONSTRAINT DF_AP_Doc_Active DEFAULT(1),
  CONSTRAINT PK_AP_DocumentIndex PRIMARY KEY(TenantID,DocumentID),
  CONSTRAINT FK_AP_DocumentIndex_Tenant FOREIGN KEY(TenantID) REFERENCES AgentProduct.Tenant(TenantID)
 );
END;
GO
IF OBJECT_ID(N'AgentProduct.DocumentChunk',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.DocumentChunk(
  TenantID uniqueidentifier NOT NULL,
  DocumentID uniqueidentifier NOT NULL,
  ChunkNo int NOT NULL CONSTRAINT CK_AP_Chunk_No CHECK(ChunkNo>=1),
  DocumentVersion int NOT NULL CONSTRAINT CK_AP_Chunk_Version CHECK(DocumentVersion>=1),
  ChunkText nvarchar(max) NOT NULL,
  CONSTRAINT PK_AP_DocumentChunk PRIMARY KEY(TenantID,DocumentID,DocumentVersion,ChunkNo),
  CONSTRAINT FK_AP_DocumentChunk_Doc FOREIGN KEY(TenantID,DocumentID)
    REFERENCES AgentProduct.DocumentIndex(TenantID,DocumentID)
 );
END;
GO
IF OBJECT_ID(N'AgentProduct.Subscription',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.Subscription(
  TenantID uniqueidentifier NOT NULL CONSTRAINT PK_AP_Subscription PRIMARY KEY,
  PlanCode nvarchar(40) NOT NULL,
  IsActive bit NOT NULL,
  ExpiresAtUtc datetime2(0) NOT NULL,
  MonthlyRequestLimit int NOT NULL CONSTRAINT CK_AP_Subscription_Limit CHECK(MonthlyRequestLimit>=0),
  CONSTRAINT FK_AP_Subscription_Tenant FOREIGN KEY(TenantID) REFERENCES AgentProduct.Tenant(TenantID)
 );
END;
GO
IF OBJECT_ID(N'AgentProduct.AuditEvent',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.AuditEvent(
  AuditID bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_AP_AuditEvent PRIMARY KEY,
  TenantID uniqueidentifier NOT NULL,
  SubjectID nvarchar(180) NOT NULL,
  RequestID uniqueidentifier NOT NULL,
  EventType varchar(45) NOT NULL,
  ResourceType varchar(30) NULL,
  ResourceID nvarchar(100) NULL,
  OccurredAtUtc datetime2(0) NOT NULL CONSTRAINT DF_AP_Audit_Time DEFAULT SYSUTCDATETIME(),
  CONSTRAINT FK_AP_Audit_Tenant FOREIGN KEY(TenantID) REFERENCES AgentProduct.Tenant(TenantID)
 );
 CREATE INDEX IX_AP_Audit_TenantTime ON AgentProduct.AuditEvent(TenantID,OccurredAtUtc DESC);
END;
GO
IF OBJECT_ID(N'AgentProduct.fn_tenant_filter',N'IF') IS NULL
 EXEC(N'
 CREATE FUNCTION AgentProduct.fn_tenant_filter(@tenant uniqueidentifier)
 RETURNS TABLE WITH SCHEMABINDING
 AS RETURN
  SELECT 1 AS fn_accessResult
  WHERE @tenant = TRY_CONVERT(uniqueidentifier, SESSION_CONTEXT(N''AgentTenantID''));
 ');
GO
IF NOT EXISTS(
 SELECT 1 FROM sys.security_policies
 WHERE name=N'AgentProductTenantPolicy' AND schema_id=SCHEMA_ID(N'AgentProduct')
)
EXEC(N'
 CREATE SECURITY POLICY AgentProduct.AgentProductTenantPolicy
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID) ON AgentProduct.Tenant,
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID) ON AgentProduct.MeetingIndex,
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID) ON AgentProduct.DocumentIndex,
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID) ON AgentProduct.DocumentChunk,
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID) ON AgentProduct.Subscription,
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID) ON AgentProduct.AuditEvent
 WITH (STATE=ON);
');
GO
/* Do not grant read permissions to the original AI_MeetingAgent SQL login.
   Commercial integration requires a separate SQL login with grants only to
   these AgentProduct tables and no permissions on MTG or AI lab tables. */
SELECT DB_NAME() AS TestDB, p.name AS SecurityPolicy, p.is_enabled,
       (SELECT COUNT(*) FROM sys.security_predicates WHERE object_id=p.object_id) AS ProtectedTables
FROM sys.security_policies p
WHERE p.name=N'AgentProductTenantPolicy';
GO
