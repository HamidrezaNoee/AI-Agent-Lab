/* GRANT only necessary SELECT permissions to a separately provisioned SQL
   login AVAN_Reader. FIRST create SQL Server login with a strong RANDOM
   password in SSMS/your secret vault; never put its password in this script.
   This does not provision an OIDC login or ProcessMaker identity.
*/
USE [EnterpriseProcess2];
GO
SET NOCOUNT ON;
IF DB_NAME()<>N'EnterpriseProcess2'
 THROW 60201,N'Wrong database.',1;
IF OBJECT_ID(N'AVAN.Tenant',N'U') IS NULL
 OR OBJECT_ID(N'AVAN.UserAccess',N'U') IS NULL
 THROW 60202,N'Apply and review AVAN additive migration 01 first.',1;
IF SUSER_ID(N'AVAN_Reader') IS NULL
 THROW 60203,N'Create restricted SQL SERVER login AVAN_Reader out-of-band with a strong secret first.',1;
IF USER_ID(N'AVAN_Reader') IS NULL
 EXEC(N'CREATE USER [AVAN_Reader] FOR LOGIN [AVAN_Reader] WITH DEFAULT_SCHEMA=[AVAN];');
IF EXISTS(SELECT 1 FROM sys.database_role_members m
 JOIN sys.database_principals r ON r.principal_id=m.role_principal_id
 JOIN sys.database_principals u ON u.principal_id=m.member_principal_id
 WHERE u.name=N'AVAN_Reader'
 AND r.name IN(N'db_owner',N'db_datareader',N'db_datawriter',N'db_ddladmin',N'db_securityadmin'))
 THROW 60204,N'AVAN_Reader already has excess database-role permissions. Resolve first.',1;
IF EXISTS(SELECT 1 FROM sys.database_permissions p
 JOIN sys.database_principals u ON u.principal_id=p.grantee_principal_id
 WHERE u.name=N'AVAN_Reader'
 AND p.state IN('G','W')
 AND p.permission_name IN ('CONTROL','ALTER','INSERT','UPDATE','DELETE','EXECUTE'))
 THROW 60205,N'AVAN_Reader has unexpected existing mutation/execute permissions. Resolve first.',1;

GRANT SELECT ON OBJECT::AVAN.Tenant TO [AVAN_Reader];
GRANT SELECT ON OBJECT::AVAN.UserAccess TO [AVAN_Reader];
GRANT SELECT ON OBJECT::MTG.Meeting TO [AVAN_Reader];
GRANT SELECT ON OBJECT::MTG.MeetingParticipant TO [AVAN_Reader];
GRANT SELECT ON OBJECT::MTG.ActionItem TO [AVAN_Reader];
GRANT SELECT ON OBJECT::MTG.Decision TO [AVAN_Reader];
GO
SELECT N'AVAN_Reader has SELECT only on six explicitly named operational objects.' AS Result;
GO
/* Never grant AVAN_Reader db_datareader, db_owner, MTG.Document content access,
   ProcessMaker internal MySQL access, or UPDATE/INSERT/DELETE/EXECUTE on MTG. */
