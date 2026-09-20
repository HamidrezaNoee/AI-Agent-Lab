/* Platform control plane for a future VERIFIED GodAdmin (LAB ONLY).
   NO default GodAdmin is seeded; bootstrap must be manual after the true
   Keycloak subject has been checked independently by an authorized DBA.
   AI_CommercialPlatformAdmin gets EXECUTE ONLY, not MTG, meeting or doc SELECT.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test' OR ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0)<>1
 THROW 60100,'Platform control plane is TEST DBA only.',1;
IF OBJECT_ID(N'AgentProduct.TenantModule',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.DirectoryUser',N'U') IS NULL
 THROW 60101,'Run commercial base, optional module and directory migrations first.',1;
GO
IF OBJECT_ID(N'AgentProduct.PlatformOperator',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.PlatformOperator(
  SubjectID nvarchar(180) NOT NULL CONSTRAINT PK_AP_PlatformOperator PRIMARY KEY,
  IsEnabled bit NOT NULL CONSTRAINT DF_AP_POperator_Enabled DEFAULT(0),
  CreatedAtUtc datetime2(0) NOT NULL CONSTRAINT DF_AP_POperator_Created DEFAULT SYSUTCDATETIME()
 );
END;
GO
/* Deliberately GLOBAL metadata only. Do NOT insert any meeting/doc content.
   GodAdmin has a platform catalog but does not bypass tenant RLS. */
IF OBJECT_ID(N'AgentProduct.PlatformTenantCatalog',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.PlatformTenantCatalog(
  TenantID uniqueidentifier NOT NULL CONSTRAINT PK_AP_PlatformTenantCatalog PRIMARY KEY,
  TenantName nvarchar(200) NOT NULL,
  IsEnabled bit NOT NULL CONSTRAINT DF_AP_Catalog_Enabled DEFAULT(0),
  LicenseID uniqueidentifier NULL,
  UpdatedAtUtc datetime2(0) NOT NULL CONSTRAINT DF_AP_Catalog_Updated DEFAULT SYSUTCDATETIME()
 );
END;
GO
/* Backfill existing explicit FICTIONAL test tenants only: metadata cannot be
   blindly SELECTed across tenants because the source Tenant table has RLS.
   Production backfill must use a separate audited per-tenant migration. */
DECLARE @labTenant uniqueidentifier;
DECLARE @labIds TABLE(TenantID uniqueidentifier PRIMARY KEY);
INSERT @labIds VALUES
 ('11111111-1111-4111-8111-111111111111'),
 ('22222222-2222-4222-8222-222222222222');
DECLARE test_catalog CURSOR LOCAL FAST_FORWARD FOR SELECT TenantID FROM @labIds;
OPEN test_catalog;
FETCH NEXT FROM test_catalog INTO @labTenant;
WHILE @@FETCH_STATUS=0
BEGIN
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=@labTenant;
 INSERT AgentProduct.PlatformTenantCatalog(TenantID,TenantName,IsEnabled)
 SELECT t.TenantID,t.TenantName,t.IsEnabled
 FROM AgentProduct.Tenant t
 WHERE t.TenantID=@labTenant AND NOT EXISTS(
   SELECT 1 FROM AgentProduct.PlatformTenantCatalog c WHERE c.TenantID=t.TenantID);
 FETCH NEXT FROM test_catalog INTO @labTenant;
END;
CLOSE test_catalog;
DEALLOCATE test_catalog;
EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=NULL;
GO
IF OBJECT_ID(N'AgentProduct.TenantBranding',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.TenantBranding(
  TenantID uniqueidentifier NOT NULL CONSTRAINT PK_AP_TenantBranding PRIMARY KEY,
  CompanyDisplayName nvarchar(200) NOT NULL,
  PrimaryColor char(7) NOT NULL CONSTRAINT DF_AP_Brand_Color DEFAULT('#126D68'),
  LogoAssetPath nvarchar(255) NULL,
  UpdatedAtUtc datetime2(0) NOT NULL CONSTRAINT DF_AP_Brand_Updated DEFAULT SYSUTCDATETIME(),
  CONSTRAINT FK_AP_Brand_Tenant FOREIGN KEY(TenantID) REFERENCES AgentProduct.Tenant(TenantID)
 );
END;
GO
IF OBJECT_ID(N'AgentProduct.TenantLicense',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.TenantLicense(
  TenantID uniqueidentifier NOT NULL CONSTRAINT PK_AP_TenantLicense PRIMARY KEY,
  LicenseID uniqueidentifier NOT NULL,
  InstallationID char(64) NOT NULL,
  LicenseToken nvarchar(max) NOT NULL,
  MaxActiveUsers int NOT NULL CONSTRAINT CK_AP_License_Users CHECK(MaxActiveUsers BETWEEN 1 AND 100000),
  ModulesMask tinyint NOT NULL,
  IssuedAtUtc datetime2(0) NOT NULL,
  ExpiresAtUtc datetime2(0) NULL,
  UpdatedAtUtc datetime2(0) NOT NULL CONSTRAINT DF_AP_License_Updated DEFAULT SYSUTCDATETIME(),
  CONSTRAINT CK_AP_License_Modules CHECK(ModulesMask BETWEEN 1 AND 15 AND ModulesMask&1=1),
  CONSTRAINT FK_AP_License_Tenant FOREIGN KEY(TenantID) REFERENCES AgentProduct.Tenant(TenantID)
 );
END;
GO
IF NOT EXISTS(SELECT 1 FROM sys.security_policies WHERE
 object_id=OBJECT_ID(N'AgentProduct.AgentProductTenantPolicy') AND is_enabled=1)
 THROW 60102,'Tenant row security policy missing or disabled.',1;
IF EXISTS(SELECT 1 FROM sys.security_predicates WHERE
 target_object_id IN(OBJECT_ID(N'AgentProduct.TenantBranding'),OBJECT_ID(N'AgentProduct.TenantLicense'))
 AND predicate_type_desc='FILTER' AND object_id<>OBJECT_ID(N'AgentProduct.AgentProductTenantPolicy'))
 THROW 60103,'Unexpected RLS policy on platform tenant tables.',1;
GO
IF NOT EXISTS(SELECT 1 FROM sys.security_predicates WHERE
 target_object_id=OBJECT_ID(N'AgentProduct.TenantBranding') AND predicate_type_desc='FILTER')
 EXEC sys.sp_executesql N'ALTER SECURITY POLICY AgentProduct.AgentProductTenantPolicy
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID)
 ON AgentProduct.TenantBranding;';
GO
IF NOT EXISTS(SELECT 1 FROM sys.security_predicates WHERE
 target_object_id=OBJECT_ID(N'AgentProduct.TenantLicense') AND predicate_type_desc='FILTER')
 EXEC sys.sp_executesql N'ALTER SECURITY POLICY AgentProduct.AgentProductTenantPolicy
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID)
 ON AgentProduct.TenantLicense;';
GO
/* A GodAdmin token role alone NEVER authorizes control-plane operations.
   The verified IdP subject must additionally be pre-registered/enabled here.
   No global SQL login is granted direct access to customer meeting/doc tables. */
CREATE OR ALTER PROCEDURE AgentProduct.IsPlatformOperator
 @SubjectID nvarchar(180)
 WITH EXECUTE AS OWNER
AS
BEGIN
 SET NOCOUNT ON;
 SELECT CASE WHEN EXISTS(SELECT 1 FROM AgentProduct.PlatformOperator
                        WHERE SubjectID=@SubjectID AND IsEnabled=1)
 THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END AS Authorized;
END;
GO
CREATE OR ALTER PROCEDURE AgentProduct.GetPlatformTenants
 @SubjectID nvarchar(180)
 WITH EXECUTE AS OWNER
AS
BEGIN
 SET NOCOUNT ON;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.PlatformOperator WHERE SubjectID=@SubjectID AND IsEnabled=1)
 THROW 60110,'GodAdmin platform operator not registered.',1;
 SELECT c.TenantID,c.TenantName,c.IsEnabled,c.LicenseID,c.UpdatedAtUtc
 FROM AgentProduct.PlatformTenantCatalog c
 ORDER BY c.UpdatedAtUtc,c.TenantID;
END;
GO
CREATE OR ALTER PROCEDURE AgentProduct.CreatePlatformTenant
 @SubjectID nvarchar(180),@TenantID uniqueidentifier,@TenantName nvarchar(200)
 WITH EXECUTE AS OWNER
AS
BEGIN
 SET NOCOUNT ON;SET XACT_ABORT ON;
 IF @TenantID IS NULL OR TRY_CONVERT(uniqueidentifier,SESSION_CONTEXT(N'AgentTenantID'))<>@TenantID
 THROW 60111,'Selected tenant context required.',1;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.PlatformOperator WHERE SubjectID=@SubjectID AND IsEnabled=1)
 THROW 60112,'GodAdmin platform operator not registered.',1;
 IF @TenantName IS NULL OR LEN(LTRIM(RTRIM(@TenantName)))<2 OR LEN(@TenantName)>200
 THROW 60113,'Invalid company name.',1;
 BEGIN TRAN;
 IF EXISTS(SELECT 1 FROM AgentProduct.Tenant WHERE TenantID=@TenantID)
 THROW 60114,'Tenant already exists.',1;
 INSERT AgentProduct.Tenant(TenantID,TenantName,IsEnabled)
 VALUES(@TenantID,LTRIM(RTRIM(@TenantName)),0);
 INSERT AgentProduct.Subscription(TenantID,PlanCode,IsActive,ExpiresAtUtc,MonthlyRequestLimit)
 VALUES(@TenantID,N'Unlicensed',0,DATEADD(DAY,1,SYSUTCDATETIME()),0);
 INSERT AgentProduct.TenantBranding(TenantID,CompanyDisplayName)
 VALUES(@TenantID,LTRIM(RTRIM(@TenantName)));
 INSERT AgentProduct.PlatformTenantCatalog(TenantID,TenantName,IsEnabled)
 VALUES(@TenantID,LTRIM(RTRIM(@TenantName)),0);
 INSERT AgentProduct.AuditEvent(TenantID,SubjectID,RequestID,EventType,ResourceType,ResourceID)
 VALUES(@TenantID,@SubjectID,NEWID(),'TenantCreated','Tenant',CONVERT(nvarchar(36),@TenantID));
 COMMIT TRAN;
 SELECT @TenantID AS TenantID;
END;
GO
CREATE OR ALTER PROCEDURE AgentProduct.GetTenantLicenseSeatCount
 @SubjectID nvarchar(180),@TenantID uniqueidentifier
 WITH EXECUTE AS OWNER
AS
BEGIN
 SET NOCOUNT ON;
 IF @TenantID IS NULL OR TRY_CONVERT(uniqueidentifier,SESSION_CONTEXT(N'AgentTenantID'))<>@TenantID
 THROW 60117,'Selected tenant context required.',1;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.PlatformOperator
               WHERE SubjectID=@SubjectID AND IsEnabled=1)
 THROW 60118,'Registered GodAdmin required.',1;
 SELECT COUNT_BIG(*) AS ActiveUsers FROM AgentProduct.Membership
 WHERE TenantID=@TenantID AND IsEnabled=1;
END;
GO
/* Activation input MUST be checked with pinned public signing key BEFORE
   this procedure is called; backend additionally re-verifies at runtime.
   SQL cannot verify ECDSA without a vetted managed crypto implementation.
*/
CREATE OR ALTER PROCEDURE AgentProduct.ActivateSignedLicense
 @SubjectID nvarchar(180),@TenantID uniqueidentifier,
 @LicenseID uniqueidentifier,@InstallationID char(64),@LicenseToken nvarchar(max),
 @MaxActiveUsers int,@ModulesMask tinyint,@IssuedAtUtc datetime2(0),
 @ExpiresAtUtc datetime2(0)=NULL
 WITH EXECUTE AS OWNER
AS
BEGIN
 SET NOCOUNT ON;SET XACT_ABORT ON;
 IF @TenantID IS NULL OR TRY_CONVERT(uniqueidentifier,SESSION_CONTEXT(N'AgentTenantID'))<>@TenantID
 THROW 60120,'Selected tenant context required.',1;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.PlatformOperator WHERE SubjectID=@SubjectID AND IsEnabled=1)
 THROW 60121,'GodAdmin platform operator not registered.',1;
 IF @LicenseID IS NULL OR @InstallationID NOT LIKE REPLICATE('[0-9A-F]',64)
  OR @MaxActiveUsers NOT BETWEEN 1 AND 100000
  OR @ModulesMask<1 OR @ModulesMask>15 OR @ModulesMask&1<>1
  OR @IssuedAtUtc>DATEADD(MINUTE,10,SYSUTCDATETIME())
  OR (@ExpiresAtUtc IS NOT NULL AND @ExpiresAtUtc<=SYSUTCDATETIME())
  OR DATALENGTH(@LicenseToken)>16000
 THROW 60122,'Invalid signed-license metadata.',1;
 BEGIN TRAN;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.Tenant WITH(UPDLOCK,HOLDLOCK) WHERE TenantID=@TenantID)
 THROW 60123,'Tenant not found.',1;
 IF EXISTS(SELECT 1 FROM AgentProduct.TenantLicense WHERE TenantID=@TenantID)
 BEGIN
 UPDATE AgentProduct.TenantLicense SET
 LicenseID=@LicenseID,InstallationID=@InstallationID,LicenseToken=@LicenseToken,
 MaxActiveUsers=@MaxActiveUsers,ModulesMask=@ModulesMask,
 IssuedAtUtc=@IssuedAtUtc,ExpiresAtUtc=@ExpiresAtUtc,UpdatedAtUtc=SYSUTCDATETIME()
 WHERE TenantID=@TenantID;
 END
 ELSE
 INSERT AgentProduct.TenantLicense
 (TenantID,LicenseID,InstallationID,LicenseToken,MaxActiveUsers,ModulesMask,IssuedAtUtc,ExpiresAtUtc)
 VALUES(@TenantID,@LicenseID,@InstallationID,@LicenseToken,@MaxActiveUsers,@ModulesMask,@IssuedAtUtc,@ExpiresAtUtc);
 DECLARE @module tinyint=2;
 WHILE @module<=4
 BEGIN
  IF EXISTS(SELECT 1 FROM AgentProduct.TenantModule WHERE TenantID=@TenantID AND ModuleCode=@module)
   UPDATE AgentProduct.TenantModule
   SET IsLicensed=CASE WHEN @ModulesMask & POWER(CAST(2 AS int),@module-1)<>0 THEN 1 ELSE 0 END,
       IsEnabled=CASE WHEN @ModulesMask & POWER(CAST(2 AS int),@module-1)<>0 THEN IsEnabled ELSE 0 END,
       LicenseUntilUtc=@ExpiresAtUtc,ModifiedAtUtc=SYSUTCDATETIME()
   WHERE TenantID=@TenantID AND ModuleCode=@module;
  ELSE
   INSERT AgentProduct.TenantModule(TenantID,ModuleCode,IsLicensed,IsEnabled,LicenseUntilUtc)
   VALUES(@TenantID,@module,
    CASE WHEN @ModulesMask & POWER(CAST(2 AS int),@module-1)<>0 THEN 1 ELSE 0 END,
    0,@ExpiresAtUtc);
  SET @module=@module+1;
 END;
 UPDATE AgentProduct.Tenant SET IsEnabled=1 WHERE TenantID=@TenantID;
 UPDATE AgentProduct.PlatformTenantCatalog
 SET IsEnabled=1,LicenseID=@LicenseID,UpdatedAtUtc=SYSUTCDATETIME()
 WHERE TenantID=@TenantID;
 UPDATE AgentProduct.Subscription SET PlanCode=N'SignedLicense',IsActive=1,
 ExpiresAtUtc=ISNULL(@ExpiresAtUtc,CONVERT(datetime2(0),'9999-12-31T00:00:00')),
 MonthlyRequestLimit=CASE WHEN MonthlyRequestLimit<100 THEN 100 ELSE MonthlyRequestLimit END
 WHERE TenantID=@TenantID;
 INSERT AgentProduct.AuditEvent(TenantID,SubjectID,RequestID,EventType,ResourceType,ResourceID)
 VALUES(@TenantID,@SubjectID,NEWID(),'LicenseActivated','TenantLicense',CONVERT(nvarchar(36),@LicenseID));
 COMMIT TRAN;
 SELECT @TenantID AS TenantID,@LicenseID AS LicenseID,@ModulesMask AS ModulesMask;
END;
GO
IF USER_ID(N'AI_CommercialReader') IS NOT NULL
BEGIN
 GRANT SELECT ON AgentProduct.TenantLicense TO [AI_CommercialReader];
 GRANT SELECT ON AgentProduct.TenantBranding TO [AI_CommercialReader];
END;
IF USER_ID(N'AI_CommercialPlatformAdmin') IS NOT NULL
BEGIN
 GRANT EXECUTE ON AgentProduct.IsPlatformOperator TO [AI_CommercialPlatformAdmin];
 GRANT EXECUTE ON AgentProduct.GetPlatformTenants TO [AI_CommercialPlatformAdmin];
 GRANT EXECUTE ON AgentProduct.CreatePlatformTenant TO [AI_CommercialPlatformAdmin];
 GRANT EXECUTE ON AgentProduct.GetTenantLicenseSeatCount TO [AI_CommercialPlatformAdmin];
 GRANT EXECUTE ON AgentProduct.ActivateSignedLicense TO [AI_CommercialPlatformAdmin];
END;
GO
PRINT 'PASS: isolated signed-license tenant control-plane objects created; NO GodAdmin seeded.';
PRINT 'NOTE: license tokens must be cryptographically verified before activation and on requests.';
