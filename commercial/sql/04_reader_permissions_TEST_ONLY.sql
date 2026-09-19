/* Least-privilege account for the TEST commercial gateway.
   Create SQL Server LOGIN [AI_CommercialReader] separately in SSMS with a strong
   NEW password and no server/db admin roles. DO NOT reuse AI_MeetingAgent.
   This script grants only test AgentProduct read permissions. */
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME() <> N'EnterpriseProcess2_AI_Test'
 THROW 56300, 'Wrong database.', 1;
IF OBJECT_ID(N'AgentProduct.Membership',N'U') IS NULL
 THROW 56301, 'Run 01 and 03 commercial scripts first.', 1;
IF SUSER_ID(N'AI_CommercialReader') IS NULL
 THROW 56302, 'Create separate AI_CommercialReader SERVER LOGIN in SSMS first.', 1;
IF IS_SRVROLEMEMBER(N'sysadmin',N'AI_CommercialReader')=1
 THROW 56303, 'Commercial reader must not be sysadmin.', 1;
GO
IF USER_ID(N'AI_CommercialReader') IS NULL
 CREATE USER [AI_CommercialReader] FOR LOGIN [AI_CommercialReader];
ELSE
 ALTER USER [AI_CommercialReader] WITH LOGIN=[AI_CommercialReader];
GO
IF EXISTS(
 SELECT 1
 FROM sys.database_role_members drm
 JOIN sys.database_principals dp ON dp.principal_id=drm.role_principal_id
 WHERE drm.member_principal_id=USER_ID(N'AI_CommercialReader')
   AND dp.name IN (N'db_owner',N'db_datareader',N'db_datawriter',N'db_securityadmin')
)
 THROW 56304, 'Commercial reader has excessive existing database roles.', 1;
GO
GRANT CONNECT TO [AI_CommercialReader];
GRANT SELECT ON OBJECT::AgentProduct.Tenant TO [AI_CommercialReader];
GRANT SELECT ON OBJECT::AgentProduct.Membership TO [AI_CommercialReader];
GRANT SELECT ON OBJECT::AgentProduct.Subscription TO [AI_CommercialReader];
GRANT SELECT ON OBJECT::AgentProduct.MeetingIndex TO [AI_CommercialReader];
/* Explicitly bar the commercial SQL account from the original unscoped lab tables. */
DENY SELECT ON SCHEMA::[MTG] TO [AI_CommercialReader];
DENY SELECT ON SCHEMA::[AI] TO [AI_CommercialReader];
GO
SELECT DB_NAME() AS TargetDB, USER_ID(N'AI_CommercialReader') AS ReaderUserID;
