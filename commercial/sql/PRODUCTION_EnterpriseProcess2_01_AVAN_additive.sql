/* AVAN 1.0 ADDITIVE OPERATIONAL MIGRATION — SQL Server / EnterpriseProcess2.
   Reviewed against MTG schema export of 2026-09-02; verify current live schema
   using PRODUCTION_EnterpriseProcess2_00_inventory.sql BEFORE running.
   This script does NOT touch MTG objects, ProcessMaker triggers/cases,
   operational meeting/action/participant/decision data, or existing users.
   Run with a DBA account from an approved backup/change window in SSMS.
*/
USE [EnterpriseProcess2];
GO
SET NOCOUNT ON;
SET XACT_ABORT ON;
IF DB_NAME()<>N'EnterpriseProcess2'
 THROW 60101,N'Wrong database. Expected EnterpriseProcess2.',1;
IF OBJECT_ID(N'MTG.Meeting',N'U') IS NULL
 OR OBJECT_ID(N'MTG.MeetingParticipant',N'U') IS NULL
 OR OBJECT_ID(N'MTG.ActionItem',N'U') IS NULL
 OR OBJECT_ID(N'MTG.Decision',N'U') IS NULL
 THROW 60102,N'Operational MTG schema is incomplete. Nothing was changed.',1;
DECLARE @Required TABLE(TableName sysname, ColumnName sysname);
INSERT @Required VALUES
('Meeting','MeetingID'),('Meeting','MeetingNo'),('Meeting','MeetingTitle'),
('Meeting','MeetingStartDateTime'),('Meeting','Status'),('Meeting','PMCaseUID'),
('Meeting','ChairUserUID'),('Meeting','SecretaryUserUID'),
('Meeting','DiscussionSummary'),('Meeting','ParkingLot'),
('MeetingParticipant','MeetingID'),('MeetingParticipant','UserUID'),
('ActionItem','ActionItemID'),('ActionItem','MeetingID'),('ActionItem','ActionNo'),
('ActionItem','ActionDescription'),('ActionItem','OwnerUserUID'),
('ActionItem','OwnerName'),('ActionItem','OwnerPosition'),
('ActionItem','DueDateTime'),('ActionItem','Status'),('ActionItem','ProgressPercent'),
('ActionItem','SecretaryProgressPercent'),('ActionItem','ClosedAt'),
('Decision','MeetingID'),('Decision','DecisionText');
IF EXISTS(SELECT 1 FROM @Required r
 LEFT JOIN sys.tables t ON t.name=r.TableName AND t.schema_id=SCHEMA_ID(N'MTG')
 LEFT JOIN sys.columns c ON c.object_id=t.object_id AND c.name=r.ColumnName
 WHERE c.column_id IS NULL)
 THROW 60103,N'Operational MTG columns differ from 2026-09-02 baseline. Run inventory and review mapping before migration.',1;
IF SCHEMA_ID(N'AVAN') IS NOT NULL
 AND (OBJECT_ID(N'AVAN.Tenant',N'U') IS NULL OR OBJECT_ID(N'AVAN.UserAccess',N'U') IS NULL)
 THROW 60104,N'Existing AVAN schema has unexpected objects. Manual review required.',1;
IF OBJECT_ID(N'AVAN.Tenant') IS NOT NULL
 AND (COL_LENGTH(N'AVAN.Tenant',N'TenantID') IS NULL
 OR COL_LENGTH(N'AVAN.Tenant',N'CompanyName') IS NULL)
 THROW 60105,N'Existing AVAN tenant schema differs; no automatic upgrade.',1;
IF OBJECT_ID(N'AVAN.UserAccess') IS NOT NULL
 AND (COL_LENGTH(N'AVAN.UserAccess',N'SubjectID') IS NULL
 OR COL_LENGTH(N'AVAN.UserAccess',N'PMUserUID') IS NULL
 OR COL_LENGTH(N'AVAN.UserAccess',N'RoleCode') IS NULL
 OR COL_LENGTH(N'AVAN.UserAccess',N'ManagerPMUserUID') IS NULL)
 THROW 60106,N'Existing AVAN user schema differs; no automatic upgrade.',1;

BEGIN TRY
 BEGIN TRANSACTION;
 IF SCHEMA_ID(N'AVAN') IS NULL
    EXEC(N'CREATE SCHEMA AVAN AUTHORIZATION dbo;');
 IF OBJECT_ID(N'AVAN.Tenant',N'U') IS NULL
 BEGIN
  CREATE TABLE AVAN.Tenant(
   TenantID uniqueidentifier NOT NULL CONSTRAINT PK_AVAN_Tenant PRIMARY KEY,
   CompanyName nvarchar(200) NOT NULL,
   IsEnabled bit NOT NULL CONSTRAINT DF_AVAN_TenantEnabled DEFAULT(0),
   CreatedAtUTC datetime2(0) NOT NULL CONSTRAINT DF_AVAN_TenantCreated DEFAULT(SYSUTCDATETIME())
  );
 END;
 IF OBJECT_ID(N'AVAN.UserAccess',N'U') IS NULL
 BEGIN
  CREATE TABLE AVAN.UserAccess(
   TenantID uniqueidentifier NOT NULL,
   SubjectID nvarchar(180) NOT NULL,
   PMUserUID char(32) NOT NULL,
   DisplayName nvarchar(250) NOT NULL,
   DepartmentName nvarchar(160) NULL,
   RoleCode varchar(12) NOT NULL
      CONSTRAINT CK_AVAN_Role CHECK(RoleCode IN('Expert','Manager','SysAdmin')),
   ManagerPMUserUID char(32) NULL,
   IsEnabled bit NOT NULL CONSTRAINT DF_AVAN_UserEnabled DEFAULT(0),
   PMIsActive bit NOT NULL CONSTRAINT DF_AVAN_PMActive DEFAULT(0),
   PMVerifiedAtUTC datetime2(0) NULL,
   CreatedAtUTC datetime2(0) NOT NULL CONSTRAINT DF_AVAN_UserCreated DEFAULT(SYSUTCDATETIME()),
   CONSTRAINT PK_AVAN_UserAccess PRIMARY KEY(TenantID,SubjectID),
   CONSTRAINT UQ_AVAN_TenantPMUID UNIQUE(TenantID,PMUserUID),
   CONSTRAINT FK_AVAN_UserTenant FOREIGN KEY(TenantID)
     REFERENCES AVAN.Tenant(TenantID),
   CONSTRAINT FK_AVAN_UserManager FOREIGN KEY(TenantID,ManagerPMUserUID)
     REFERENCES AVAN.UserAccess(TenantID,PMUserUID),
   CONSTRAINT CK_AVAN_PMSelfManager CHECK(ManagerPMUserUID IS NULL OR ManagerPMUserUID<>PMUserUID),
   CONSTRAINT CK_AVAN_PMUID CHECK(PMUserUID NOT LIKE '%[^0-9a-fA-F]%')
  );
  CREATE INDEX IX_AVAN_Manager ON AVAN.UserAccess
     (TenantID,ManagerPMUserUID) INCLUDE(PMUserUID,IsEnabled,PMIsActive);
 END;
 COMMIT TRANSACTION;
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
 THROW;
END CATCH;
GO
/* This migration intentionally creates NO administrator account, PM identity
   binding, role grant, license, SQL login, or automatic access to records.
   A verified tenant and matched IdP subject+PMUID must be provisioned through
   a separately authorized, audited onboarding procedure.
*/
SELECT N'AVAN additive schema available. MTG tables and workflow unchanged.' AS Result,
       DB_NAME() AS DatabaseName;
GO
