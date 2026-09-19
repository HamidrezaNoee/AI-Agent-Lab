/* RUN FIRST, ALONE, in SSMS with an ADMINISTRATOR connection.
   ONE batch: a THROW stops the rest. Do not concatenate other migrations.
   This script does NOT create, reset or modify tables or test data.
*/
USE [EnterpriseProcess2_AI_Test];
SET NOCOUNT ON;
IF DB_NAME() <> N'EnterpriseProcess2_AI_Test'
    THROW 58000, 'Wrong database. Open the synthetic test database.', 1;
IF OBJECT_ID(N'MTG.Meeting', N'U') IS NULL
    THROW 58001, 'Synthetic MTG.Meeting missing or invisible; check database and account.', 1;
IF ISNULL(IS_SRVROLEMEMBER(N'sysadmin'), 0) <> 1
   AND ISNULL(IS_MEMBER(N'db_owner'), 0) <> 1
    THROW 58002, 'Connect with TEST database db_owner or TEST server sysadmin for schema migrations; AI_MeetingAgent is read-only.', 1;

SELECT
    DB_NAME() AS CurrentDatabase,
    @@SERVERNAME AS ConnectedServer,
    ORIGINAL_LOGIN() AS OriginalLogin,
    USER_NAME() AS DatabaseUser,
    IS_SRVROLEMEMBER(N'sysadmin') AS IsServerSysadmin,
    IS_MEMBER(N'db_owner') AS IsDatabaseOwner,
    SCHEMA_ID(N'AgentProduct') AS AgentProductSchemaID,
    OBJECT_ID(N'AgentProduct.Tenant',N'U') AS TenantTableID,
    OBJECT_ID(N'AgentProduct.DocumentIndex',N'U') AS DocumentIndexTableID,
    OBJECT_ID(N'AgentProduct.Subscription',N'U') AS SubscriptionTableID,
    OBJECT_ID(N'AgentProduct.Membership',N'U') AS MembershipTableID,
    OBJECT_ID(N'AgentProduct.MeetingGrant',N'U') AS MeetingGrantTableID,
    OBJECT_ID(N'AgentProduct.ReserveChatRequest',N'P') AS ReserveChatRequestID;
PRINT 'PASS: test database, MTG fixture and migration administrator verified.';
