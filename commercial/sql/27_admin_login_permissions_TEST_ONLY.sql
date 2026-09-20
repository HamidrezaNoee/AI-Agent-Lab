/* Isolated LAB optional ADMIN SQL permissions; NO LOGIN passwords in repository.
   Run only AFTER 19,20,21,23,24,25,26 and AFTER a TEST DBA separately
   provisions unique SQL logins with independent strong passwords:
      AI_CommercialDirectoryAdmin
      AI_CommercialPlatformAdmin
   Neither account may be sysadmin/db_owner/db_datareader or share Reader secret.
   Never run on ProcessMaker's operational EnterpriseProcess databases.
*/
USE [EnterpriseProcess2_AI_Test];
GO
SET NOCOUNT ON;
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test'
 OR ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0)<>1
 THROW 60500,'Optional admin login grants require isolated TEST DBA.',1;
IF SUSER_ID(N'AI_CommercialDirectoryAdmin') IS NULL
 OR SUSER_ID(N'AI_CommercialPlatformAdmin') IS NULL
 THROW 60501,'Create two separate nonadministrative SQL logins securely before this script.',1;
IF OBJECT_ID(N'AgentProduct.SyncProcessMakerUsers',N'P') IS NULL
 OR OBJECT_ID(N'AgentProduct.SetOrgManager',N'P') IS NULL
 OR OBJECT_ID(N'AgentProduct.SetOrgRole',N'P') IS NULL
 OR OBJECT_ID(N'AgentProduct.SetTenantBranding',N'P') IS NULL
 OR OBJECT_ID(N'AgentProduct.SetTenantLogo',N'P') IS NULL
 OR OBJECT_ID(N'AgentProduct.IsPlatformOperator',N'P') IS NULL
 OR OBJECT_ID(N'AgentProduct.GetPlatformTenants',N'P') IS NULL
 OR OBJECT_ID(N'AgentProduct.CreatePlatformTenant',N'P') IS NULL
 OR OBJECT_ID(N'AgentProduct.GetTenantLicenseSeatCount',N'P') IS NULL
 OR OBJECT_ID(N'AgentProduct.ActivateSignedLicense',N'P') IS NULL
 THROW 60502,'Run the listed restricted directory/platform migrations first.',1;
GO
IF USER_ID(N'AI_CommercialDirectoryAdmin') IS NULL
 EXEC sys.sp_executesql N'CREATE USER [AI_CommercialDirectoryAdmin] FOR LOGIN [AI_CommercialDirectoryAdmin];';
IF USER_ID(N'AI_CommercialPlatformAdmin') IS NULL
 EXEC sys.sp_executesql N'CREATE USER [AI_CommercialPlatformAdmin] FOR LOGIN [AI_CommercialPlatformAdmin];';
GO
IF ISNULL(IS_SRVROLEMEMBER(N'sysadmin',N'AI_CommercialDirectoryAdmin'),0)<>0
 OR ISNULL(IS_SRVROLEMEMBER(N'sysadmin',N'AI_CommercialPlatformAdmin'),0)<>0
 THROW 60503,'A commercial control-plane account must never be server sysadmin.',1;
IF EXISTS(SELECT 1 FROM sys.database_role_members d
 JOIN sys.database_principals m ON d.member_principal_id=m.principal_id
 JOIN sys.database_principals r ON d.role_principal_id=r.principal_id
 WHERE m.name IN(N'AI_CommercialDirectoryAdmin',N'AI_CommercialPlatformAdmin')
 AND r.name IN(N'db_owner',N'db_datareader',N'db_datawriter'))
 THROW 60504,'Remove broad database roles from control-plane accounts.',1;
GO
GRANT EXECUTE ON AgentProduct.SyncProcessMakerUsers TO [AI_CommercialDirectoryAdmin];
GRANT EXECUTE ON AgentProduct.SetOrgManager TO [AI_CommercialDirectoryAdmin];
GRANT EXECUTE ON AgentProduct.SetOrgRole TO [AI_CommercialDirectoryAdmin];
GRANT EXECUTE ON AgentProduct.SetTenantBranding TO [AI_CommercialDirectoryAdmin];
GRANT EXECUTE ON AgentProduct.SetTenantLogo TO [AI_CommercialDirectoryAdmin];

GRANT EXECUTE ON AgentProduct.IsPlatformOperator TO [AI_CommercialPlatformAdmin];
GRANT EXECUTE ON AgentProduct.GetPlatformTenants TO [AI_CommercialPlatformAdmin];
GRANT EXECUTE ON AgentProduct.CreatePlatformTenant TO [AI_CommercialPlatformAdmin];
GRANT EXECUTE ON AgentProduct.GetTenantLicenseSeatCount TO [AI_CommercialPlatformAdmin];
GRANT EXECUTE ON AgentProduct.ActivateSignedLicense TO [AI_CommercialPlatformAdmin];
GO
IF SCHEMA_ID(N'MTG') IS NOT NULL
BEGIN
 EXEC sys.sp_executesql N'DENY SELECT ON SCHEMA::[MTG] TO [AI_CommercialDirectoryAdmin];';
 EXEC sys.sp_executesql N'DENY SELECT ON SCHEMA::[MTG] TO [AI_CommercialPlatformAdmin];';
END;
IF SCHEMA_ID(N'AI') IS NOT NULL
BEGIN
 EXEC sys.sp_executesql N'DENY SELECT ON SCHEMA::[AI] TO [AI_CommercialDirectoryAdmin];';
 EXEC sys.sp_executesql N'DENY SELECT ON SCHEMA::[AI] TO [AI_CommercialPlatformAdmin];';
END;
GO
PRINT 'PASS: two separate low-privilege TEST control-plane SQL users mapped with narrow EXECUTE only.';
PRINT 'NOTE: no password configured here; no broad tenant meeting/document SELECT granted.';
