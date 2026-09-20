/* Isolated LAB branding logo mapping. Always server-selected opaque PNG filename.
   No arbitrary user path, remote URL or executable SVG/HTML uploads.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test' OR ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0)<>1
 THROW 60400,'Logo mapping: TEST DBA only.',1;
IF OBJECT_ID(N'AgentProduct.TenantBranding',N'U') IS NULL
 THROW 60401,'Run platform branding migration 23 first.',1;
GO
CREATE OR ALTER PROCEDURE AgentProduct.SetTenantLogo
 @TenantID uniqueidentifier,@ActorSubjectID nvarchar(180),
 @LogoFileName nvarchar(255)
 WITH EXECUTE AS OWNER
AS
BEGIN
 SET NOCOUNT ON;SET XACT_ABORT ON;
 IF @TenantID IS NULL OR TRY_CONVERT(uniqueidentifier,SESSION_CONTEXT(N'AgentTenantID'))<>@TenantID
  THROW 60410,'Tenant context invalid.',1;
 IF @LogoFileName IS NULL OR LEN(@LogoFileName)<>36
  OR @LogoFileName COLLATE Latin1_General_BIN2 NOT LIKE
     REPLICATE('[0-9a-f]',32)+'.png'
  THROW 60411,'Only server-issued opaque PNG filenames are accepted.',1;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.DirectoryUser u
  JOIN AgentProduct.Membership m ON m.TenantID=u.TenantID AND m.SubjectID=u.SubjectID
  WHERE u.TenantID=@TenantID AND u.SubjectID=@ActorSubjectID
    AND u.IsEnabled=1 AND u.PMStatus='ACTIVE'
    AND u.OrgRole='SysAdmin' AND m.IsEnabled=1
    AND m.RoleCode IN('Owner','Admin'))
  THROW 60412,'Verified tenant SysAdmin required.',1;
 BEGIN TRAN;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.TenantBranding
 WHERE TenantID=@TenantID)
  THROW 60413,'Tenant branding row is missing.',1;
 UPDATE AgentProduct.TenantBranding
 SET LogoAssetPath=@LogoFileName,UpdatedAtUtc=SYSUTCDATETIME()
 WHERE TenantID=@TenantID;
 INSERT AgentProduct.AuditEvent(TenantID,SubjectID,RequestID,EventType,ResourceType,ResourceID)
 VALUES(@TenantID,@ActorSubjectID,NEWID(),'TenantLogoChanged','TenantBrand',CONVERT(nvarchar(36),@TenantID));
 COMMIT TRAN;
 SELECT LogoAssetPath FROM AgentProduct.TenantBranding WHERE TenantID=@TenantID;
END;
GO
IF USER_ID(N'AI_CommercialDirectoryAdmin') IS NOT NULL
 GRANT EXECUTE ON AgentProduct.SetTenantLogo TO [AI_CommercialDirectoryAdmin];
GO
PRINT 'PASS: restricted tenant logo mapping procedure created (no logo or customer data imported).';
