/* OPERATOR TEMPLATE — manually fill EVERY variable after independent identity
   verification. This file intentionally throws before any write when placeholders
   remain. Do NOT blindly execute without confirming the live PM user UID, the
   verified OIDC access-token tenant_id/sub, and approved organizational role.
   No ProcessMaker workflow object/data is changed. AVAN.* only.
*/
USE [EnterpriseProcess2];
GO
SET XACT_ABORT ON;
SET NOCOUNT ON;
IF DB_NAME()<>N'EnterpriseProcess2'
 THROW 60301,N'Unexpected database.',1;
IF OBJECT_ID(N'AVAN.UserAccess',N'U') IS NULL
 THROW 60302,N'First run and review migration 01.',1;

DECLARE @Tenant uniqueidentifier=TRY_CONVERT(uniqueidentifier,N'REPLACE_WITH_VERIFIED_IDP_TENANT_UUID');
DECLARE @Subject nvarchar(180)=N'REPLACE_WITH_VERIFIED_IDP_SUB';
DECLARE @PMUID char(32)='REPLACE_WITH_REAL_PM_USER_UID_32';
DECLARE @DisplayName nvarchar(250)=N'REPLACE_WITH_VERIFIED_PERSON_NAME';
DECLARE @Company nvarchar(200)=N'REPLACE_WITH_REAL_COMPANY_NAME';
DECLARE @Department nvarchar(160)=N'REPLACE_WITH_APPROVED_DEPARTMENT';
DECLARE @Role varchar(12)='Expert'; -- Expert / Manager / SysAdmin; verify independently.
DECLARE @ManagerPMUID char(32)=NULL; -- Only a real ACTIVE user already linked in SAME tenant.
DECLARE @PMVerified bit=0; -- Change to 1 ONLY after checking PM 3.3.x ACTIVE status via trusted source.
DECLARE @IdentityVerified bit=0; -- Change to 1 ONLY after checking OIDC subject and tenant_id.

IF @Tenant IS NULL OR @Subject LIKE N'REPLACE_%'
 OR @PMUID LIKE 'REPLACE_%' OR @DisplayName LIKE N'REPLACE_%'
 OR @Company LIKE N'REPLACE_%' OR @Department LIKE N'REPLACE_%'
 OR @PMVerified<>1 OR @IdentityVerified<>1
 THROW 60303,N'Identity / PM user mapping NOT verified. No changes were made.',1;
IF LEN(RTRIM(@PMUID))<>32 OR @PMUID LIKE '%[^0-9a-fA-F]%'
 THROW 60304,N'Invalid ProcessMaker UID. No changes were made.',1;
IF @Role NOT IN ('Expert','Manager','SysAdmin')
 THROW 60305,N'Unapproved role. No changes were made.',1;
IF EXISTS(SELECT 1 FROM AVAN.Tenant WHERE TenantID<>@Tenant AND IsEnabled=1)
 THROW 60306,N'Operational MTG database supports exactly one active tenant.',1;
IF EXISTS(SELECT 1 FROM AVAN.UserAccess
          WHERE TenantID=@Tenant AND (SubjectID=@Subject OR PMUserUID=@PMUID))
 THROW 60307,N'User already linked; do not overwrite existing verified identities.',1;
IF @ManagerPMUID IS NOT NULL AND NOT EXISTS(
 SELECT 1 FROM AVAN.UserAccess
 WHERE TenantID=@Tenant AND PMUserUID=@ManagerPMUID
   AND IsEnabled=1 AND PMIsActive=1
   AND PMVerifiedAtUTC>=DATEADD(DAY,-7,SYSUTCDATETIME()))
 THROW 60308,N'Manager link must point to a verified active user in this company.',1;

BEGIN TRY
 BEGIN TRANSACTION;
 IF NOT EXISTS(SELECT 1 FROM AVAN.Tenant WHERE TenantID=@Tenant)
   INSERT AVAN.Tenant(TenantID,CompanyName,IsEnabled)
      VALUES(@Tenant,@Company,0);
 INSERT AVAN.UserAccess(
   TenantID,SubjectID,PMUserUID,DisplayName,DepartmentName,
   RoleCode,ManagerPMUserUID,IsEnabled,PMIsActive,PMVerifiedAtUTC
 ) VALUES (
   @Tenant,@Subject,@PMUID,@DisplayName,@Department,
   @Role,@ManagerPMUID,1,1,SYSUTCDATETIME()
 );
 UPDATE AVAN.Tenant SET IsEnabled=1
 WHERE TenantID=@Tenant AND CompanyName=@Company;
 IF @@ROWCOUNT<>1
   THROW 60309,N'Company name / tenant mapping differs. Rolled back.',1;
 COMMIT TRANSACTION;
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK TRANSACTION;
 THROW;
END CATCH;
GO
/* This template is a one-time on-boarded user mapping, NOT a substitute for
   an automated PM user sync/revocation policy or an identity-management UI.
   It does not create a GodAdmin or a SQL/IdP login. */
