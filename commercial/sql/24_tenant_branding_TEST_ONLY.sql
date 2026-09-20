/* Tenant-branded appearance: owned by tenant SysAdmin only, TEST DB.
   Cannot change SQL credentials, read secrets, upload arbitrary logo, or
   widen meeting permissions. Font assets are operator-installed locally.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test' OR ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0)<>1
 THROW 60200,'Brand settings migration: TEST DBA only.',1;
IF OBJECT_ID(N'AgentProduct.TenantBranding',N'U') IS NULL
 THROW 60201,'Run platform schema 23 first.',1;
GO
CREATE OR ALTER PROCEDURE AgentProduct.SetTenantBranding
 @TenantID uniqueidentifier,@ActorSubjectID nvarchar(180),
 @CompanyDisplayName nvarchar(200),@PrimaryColor char(7)
 WITH EXECUTE AS OWNER
AS
BEGIN
 SET NOCOUNT ON;SET XACT_ABORT ON;
 IF @TenantID IS NULL OR TRY_CONVERT(uniqueidentifier,SESSION_CONTEXT(N'AgentTenantID'))<>@TenantID
 THROW 60210,'Invalid tenant context.',1;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.DirectoryUser u
  JOIN AgentProduct.Membership m ON m.TenantID=u.TenantID AND m.SubjectID=u.SubjectID
  WHERE u.TenantID=@TenantID AND u.SubjectID=@ActorSubjectID
    AND u.OrgRole='SysAdmin' AND u.IsEnabled=1 AND u.PMStatus='ACTIVE'
    AND m.IsEnabled=1 AND m.RoleCode IN('Admin','Owner'))
 THROW 60211,'Verified active tenant SysAdmin required.',1;
 IF @CompanyDisplayName IS NULL OR LEN(LTRIM(RTRIM(@CompanyDisplayName)))<2
  OR LEN(@CompanyDisplayName)>200
 THROW 60212,'Invalid company display name.',1;
 IF @PrimaryColor IS NULL OR @PrimaryColor NOT LIKE '#[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F][0-9a-fA-F]'
 THROW 60213,'Invalid hex primary color.',1;
 BEGIN TRAN;
 IF EXISTS(SELECT 1 FROM AgentProduct.TenantBranding WHERE TenantID=@TenantID)
  UPDATE AgentProduct.TenantBranding SET CompanyDisplayName=LTRIM(RTRIM(@CompanyDisplayName)),
    PrimaryColor=UPPER(@PrimaryColor),UpdatedAtUtc=SYSUTCDATETIME()
  WHERE TenantID=@TenantID;
 ELSE INSERT AgentProduct.TenantBranding(TenantID,CompanyDisplayName,PrimaryColor)
 VALUES(@TenantID,LTRIM(RTRIM(@CompanyDisplayName)),UPPER(@PrimaryColor));
 INSERT AgentProduct.AuditEvent(TenantID,SubjectID,RequestID,EventType,ResourceType,ResourceID)
 VALUES(@TenantID,@ActorSubjectID,NEWID(),'TenantBrandChanged','TenantBrand',CONVERT(nvarchar(36),@TenantID));
 COMMIT TRAN;
 SELECT CompanyDisplayName,PrimaryColor FROM AgentProduct.TenantBranding WHERE TenantID=@TenantID;
END;
GO
IF USER_ID(N'AI_CommercialDirectoryAdmin') IS NOT NULL
 GRANT EXECUTE ON AgentProduct.SetTenantBranding TO [AI_CommercialDirectoryAdmin];
GO
PRINT 'PASS: tenant-scoped audited company name and brand color configuration created.';
PRINT 'NOTE: logo uploads and SQL credential changes require a separately reviewed secure storage service.';
