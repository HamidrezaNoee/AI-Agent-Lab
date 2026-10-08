-- Dedicated Agent database only. No ProcessMaker or meeting mirror objects.
USE [AVANAgent];
GO
IF OBJECT_ID(N'dbo.AgentState',N'U') IS NULL
BEGIN
 CREATE TABLE dbo.AgentState(
   StateKey char(64) NOT NULL CONSTRAINT PK_AgentState PRIMARY KEY,
   Payload varbinary(max) NOT NULL,
   UpdatedAt datetime2(3) NOT NULL CONSTRAINT DF_AgentState_Updated DEFAULT SYSUTCDATETIME()
 );
END;
GO
IF OBJECT_ID(N'dbo.AgentAudit',N'U') IS NULL
BEGIN
 CREATE TABLE dbo.AgentAudit(
   EventID char(32) NOT NULL CONSTRAINT PK_AgentAudit PRIMARY KEY,
   TenantID nvarchar(64) NOT NULL,
   ActorID nvarchar(256) NOT NULL,
   EventCode varchar(80) NOT NULL,
   HappenedAt datetime2(3) NOT NULL,
   Detail nvarchar(max) NOT NULL
 );
 CREATE INDEX IX_AgentAudit_TenantTime ON dbo.AgentAudit(TenantID,HappenedAt);
END;
GO
