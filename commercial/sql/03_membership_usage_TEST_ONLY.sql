/* Extend test-only commercial contract with per-user membership and per-tenant usage. */
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME() <> N'EnterpriseProcess2_AI_Test'
 THROW 56200, 'Wrong database.', 1;
IF OBJECT_ID(N'AgentProduct.Tenant',N'U') IS NULL
 THROW 56201, 'Run 01_tenant_boundary_TEST_ONLY.sql first.', 1;
GO
IF OBJECT_ID(N'AgentProduct.Membership',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.Membership(
  TenantID uniqueidentifier NOT NULL,
  SubjectID nvarchar(180) NOT NULL,
  RoleCode varchar(20) NOT NULL,
  IsEnabled bit NOT NULL CONSTRAINT DF_AP_Membership_Enabled DEFAULT(1),
  CONSTRAINT PK_AP_Membership PRIMARY KEY(TenantID,SubjectID),
  CONSTRAINT CK_AP_Membership_Role CHECK(RoleCode IN('Owner','Admin','Analyst','Viewer')),
  CONSTRAINT FK_AP_Membership_Tenant FOREIGN KEY(TenantID) REFERENCES AgentProduct.Tenant(TenantID)
 );
END;
GO
IF OBJECT_ID(N'AgentProduct.RequestUsage',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.RequestUsage(
  UsageID bigint IDENTITY(1,1) NOT NULL CONSTRAINT PK_AP_RequestUsage PRIMARY KEY,
  TenantID uniqueidentifier NOT NULL,
  SubjectID nvarchar(180) NOT NULL,
  RequestID uniqueidentifier NOT NULL,
  ModelName nvarchar(100) NOT NULL,
  InputTokens int NOT NULL CONSTRAINT CK_AP_Usage_In CHECK(InputTokens>=0),
  OutputTokens int NOT NULL CONSTRAINT CK_AP_Usage_Out CHECK(OutputTokens>=0),
  RecordedAtUtc datetime2(0) NOT NULL CONSTRAINT DF_AP_Usage_Time DEFAULT SYSUTCDATETIME(),
  CONSTRAINT UQ_AP_RequestUsage_Request UNIQUE(TenantID,RequestID),
  CONSTRAINT FK_AP_Usage_Tenant FOREIGN KEY(TenantID) REFERENCES AgentProduct.Tenant(TenantID)
 );
 CREATE INDEX IX_AP_Usage_TenantTime ON AgentProduct.RequestUsage(TenantID,RecordedAtUtc);
END;
GO
IF NOT EXISTS(
 SELECT 1 FROM sys.security_predicates sp
 JOIN sys.security_policies p ON p.object_id=sp.object_id
 WHERE p.name=N'AgentProductTenantPolicy'
 AND sp.target_object_id=OBJECT_ID(N'AgentProduct.Membership')
)
 ALTER SECURITY POLICY AgentProduct.AgentProductTenantPolicy
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID)
 ON AgentProduct.Membership;
GO
IF NOT EXISTS(
 SELECT 1 FROM sys.security_predicates sp
 JOIN sys.security_policies p ON p.object_id=sp.object_id
 WHERE p.name=N'AgentProductTenantPolicy'
 AND sp.target_object_id=OBJECT_ID(N'AgentProduct.RequestUsage')
)
 ALTER SECURITY POLICY AgentProduct.AgentProductTenantPolicy
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID)
 ON AgentProduct.RequestUsage;
GO
SELECT name FROM sys.tables WHERE schema_id=SCHEMA_ID(N'AgentProduct');
