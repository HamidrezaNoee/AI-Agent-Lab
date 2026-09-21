/* AVAN GodAdmin-only configuration writer. No SELECT/INSERT/UPDATE/DELETE
   permission on any MTG object or the publisher-signed license token.
   Use a separate credential from AVAN_Reader and the temporary DBA login. */
USE [EnterpriseProcess2];
GO
SET NOCOUNT ON;
IF DB_NAME()<>N'EnterpriseProcess2'
 THROW 60501,N'Wrong database.',1;
IF OBJECT_ID(N'AVAN.Tenant',N'U') IS NULL
 OR OBJECT_ID(N'AVAN.UserAccess',N'U') IS NULL
 THROW 60502,N'Apply approved additive AVAN migration first.',1;
IF SUSER_ID(N'AVAN_ConfigWriter') IS NULL
 THROW 60503,N'Dedicated configuration SQL login not found.',1;
IF USER_ID(N'AVAN_ConfigWriter') IS NULL
 EXEC(N'CREATE USER [AVAN_ConfigWriter] FOR LOGIN [AVAN_ConfigWriter] WITH DEFAULT_SCHEMA=[AVAN];');
IF EXISTS(SELECT 1 FROM sys.database_role_members m
 JOIN sys.database_principals r ON r.principal_id=m.role_principal_id
 JOIN sys.database_principals u ON u.principal_id=m.member_principal_id
 WHERE u.name=N'AVAN_ConfigWriter'
 AND r.name IN(N'db_owner',N'db_datareader',N'db_datawriter',
               N'db_ddladmin',N'db_securityadmin'))
 THROW 60504,N'Config writer already has excessive database role access.',1;
IF EXISTS(SELECT 1 FROM sys.database_permissions p
 JOIN sys.database_principals u ON u.principal_id=p.grantee_principal_id
 WHERE u.name=N'AVAN_ConfigWriter' AND p.state IN('G','W')
 AND p.permission_name IN ('CONTROL','ALTER','DELETE'))
 THROW 60505,N'Config writer already has prohibited broad permissions.',1;
GRANT SELECT,INSERT,UPDATE ON OBJECT::AVAN.Tenant TO [AVAN_ConfigWriter];
GRANT SELECT,INSERT,UPDATE ON OBJECT::AVAN.UserAccess TO [AVAN_ConfigWriter];
GO
SELECT N'AVAN_ConfigWriter limited to company and user provisioning; no MTG rights.' AS Result;
GO
