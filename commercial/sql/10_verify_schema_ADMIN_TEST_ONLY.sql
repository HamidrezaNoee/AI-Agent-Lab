/* RUN AFTER base migrations 01,03,05,09,07 — read-only verification.
   Execute alone using the SAME test DBA SSMS connection. This is one batch:
   a missing object raises one clear error instead of cascading across GO.
*/
USE [EnterpriseProcess2_AI_Test];
SET NOCOUNT ON;
IF DB_NAME() <> N'EnterpriseProcess2_AI_Test'
    THROW 58100,'Wrong database.',1;
IF ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0)<>1
   AND ISNULL(IS_MEMBER(N'db_owner'),0)<>1
    THROW 58101,'Verify with TEST DBA: object visibility requires admin rights.',1;
IF SCHEMA_ID(N'AgentProduct') IS NULL
    THROW 58102,'Missing AgentProduct schema: run 01_tenant_boundary_TEST_ONLY.sql.',1;
IF OBJECT_ID(N'AgentProduct.Tenant',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.MeetingIndex',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.DocumentIndex',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.DocumentChunk',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.Subscription',N'U') IS NULL
    THROW 58103,'Base table(s) missing: rerun SQL 01 alone and inspect its messages.',1;
IF OBJECT_ID(N'AgentProduct.Membership',N'U') IS NULL
    THROW 58104,'Missing Membership: run SQL 03.',1;
IF OBJECT_ID(N'AgentProduct.MeetingGrant',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.DocumentGrant',N'U') IS NULL
    THROW 58105,'Missing per-user grants: run SQL 05.',1;
IF COL_LENGTH(N'AgentProduct.DocumentIndex',N'RelatedMeetingID') IS NULL
    THROW 58106,'Missing document meeting-link column: run SQL 09.',1;
IF OBJECT_ID(N'AgentProduct.ChatRequest',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.ReserveChatRequest',N'P') IS NULL
 OR OBJECT_ID(N'AgentProduct.FinalizeChatRequest',N'P') IS NULL
    THROW 58107,'Missing quota objects: run SQL 07.',1;
IF OBJECT_ID(N'AgentProduct.fn_tenant_filter',N'IF') IS NULL
 OR NOT EXISTS(SELECT 1 FROM sys.security_policies
               WHERE name=N'AgentProductTenantPolicy'
                 AND schema_id=SCHEMA_ID(N'AgentProduct') AND is_enabled=1)
    THROW 58108,'Tenant RLS policy missing or disabled: inspect SQL 01.',1;

SELECT DB_NAME() AS TestDB,@@SERVERNAME AS SQLInstance,
  ORIGINAL_LOGIN() AS MigrationLogin,
  OBJECT_ID(N'AgentProduct.Tenant',N'U') AS TenantTable,
  OBJECT_ID(N'AgentProduct.DocumentIndex',N'U') AS DocumentTable,
  OBJECT_ID(N'AgentProduct.ChatRequest',N'U') AS QuotaTable,
  OBJECT_ID(N'AgentProduct.ReserveChatRequest',N'P') AS QuotaReserveProcedure,
  OBJECT_ID(N'AgentProduct.FinalizeChatRequest',N'P') AS QuotaFinalizeProcedure;
PRINT 'PASS: all commercial test schema dependencies exist. Now run isolation and quota tests.';
