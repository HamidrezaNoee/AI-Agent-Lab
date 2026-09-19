/* Synthetic-only commercial milestone 3. Run in SSMS after SQL files 01,03,05.
   Separate read-only gateway account may EXECUTE these narrowly scoped procedures;
   it must NOT receive INSERT/UPDATE rights on AgentProduct tables.
   No real MTG or AI data is read or modified.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME() <> N'EnterpriseProcess2_AI_Test'
 THROW 56800, 'Wrong DB: test-only quota migration.', 1;
IF OBJECT_ID(N'AgentProduct.Subscription',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.Membership',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.fn_tenant_filter',N'IF') IS NULL
 THROW 56801, 'Run commercial SQL migrations 01 and 03 first.', 1;
GO
IF OBJECT_ID(N'AgentProduct.ChatRequest',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.ChatRequest(
  TenantID uniqueidentifier NOT NULL,
  RequestID uniqueidentifier NOT NULL,
  SubjectID nvarchar(180) NOT NULL,
  ModelName nvarchar(80) NOT NULL,
  Status varchar(12) NOT NULL
    CONSTRAINT CK_AP_ChatRequest_Status CHECK(Status IN('Reserved','Completed','Failed')),
  ReservedAtUtc datetime2(0) NOT NULL
    CONSTRAINT DF_AP_ChatRequest_Reserved DEFAULT SYSUTCDATETIME(),
  FinalizedAtUtc datetime2(0) NULL,
  InputTokens int NULL CONSTRAINT CK_AP_ChatRequest_Input CHECK(InputTokens>=0),
  OutputTokens int NULL CONSTRAINT CK_AP_ChatRequest_Output CHECK(OutputTokens>=0),
  CONSTRAINT PK_AP_ChatRequest PRIMARY KEY(TenantID,RequestID),
  CONSTRAINT FK_AP_ChatRequest_Tenant FOREIGN KEY(TenantID)
    REFERENCES AgentProduct.Tenant(TenantID)
 );
 CREATE INDEX IX_AP_ChatRequest_Period
 ON AgentProduct.ChatRequest(TenantID,ReservedAtUtc) INCLUDE(Status);
END;
GO
IF NOT EXISTS(
 SELECT 1 FROM sys.security_predicates sp
 JOIN sys.security_policies p ON p.object_id=sp.object_id
 WHERE p.name=N'AgentProductTenantPolicy'
 AND sp.target_object_id=OBJECT_ID(N'AgentProduct.ChatRequest')
)
 ALTER SECURITY POLICY AgentProduct.AgentProductTenantPolicy
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID)
 ON AgentProduct.ChatRequest;
GO
CREATE OR ALTER PROCEDURE AgentProduct.ReserveChatRequest
 @TenantID uniqueidentifier, @SubjectID nvarchar(180),
 @RequestID uniqueidentifier, @ModelName nvarchar(80)
 WITH EXECUTE AS OWNER
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 IF @TenantID IS NULL OR @RequestID IS NULL OR
    @SubjectID IS NULL OR LEN(@SubjectID)=0 OR
    @ModelName IS NULL OR LEN(@ModelName)=0 OR
    TRY_CONVERT(uniqueidentifier,SESSION_CONTEXT(N'AgentTenantID')) <> @TenantID
    THROW 56802,'Invalid tenant session or request.',1;
 DECLARE @now datetime2(0)=SYSUTCDATETIME();
 DECLARE @monthStart datetime2(0)=CONVERT(datetime2(0),
   DATEFROMPARTS(YEAR(@now),MONTH(@now),1));
 DECLARE @limit int, @count bigint, @lockResult int;
 BEGIN TRAN;
 EXEC @lockResult = sys.sp_getapplock
  @Resource = CONCAT('APChatQuota:', CONVERT(varchar(36),@TenantID)),
  @LockMode='Exclusive',@LockOwner='Transaction',@LockTimeout=5000;
 IF @lockResult < 0 THROW 56803,'Quota lock unavailable.',1;
 SELECT @limit=s.MonthlyRequestLimit
 FROM AgentProduct.Subscription s
 JOIN AgentProduct.Tenant t ON t.TenantID=s.TenantID
 JOIN AgentProduct.Membership m ON m.TenantID=s.TenantID
 WHERE s.TenantID=@TenantID AND m.SubjectID=@SubjectID AND m.IsEnabled=1
  AND t.IsEnabled=1 AND s.IsActive=1 AND s.ExpiresAtUtc > @now;
 IF @limit IS NULL THROW 56804,'Inactive membership or subscription.',1;
 IF EXISTS(SELECT 1 FROM AgentProduct.ChatRequest
  WHERE TenantID=@TenantID AND RequestID=@RequestID)
  THROW 56805,'Duplicate request id.',1;
 SELECT @count=COUNT_BIG(*)
 FROM AgentProduct.ChatRequest
 WHERE TenantID=@TenantID AND ReservedAtUtc>=@monthStart
   AND ReservedAtUtc<DATEADD(MONTH,1,@monthStart);
 IF @count>=@limit THROW 56806,'Monthly request quota exceeded.',1;
 INSERT AgentProduct.ChatRequest
  (TenantID,RequestID,SubjectID,ModelName,Status,ReservedAtUtc)
 VALUES(@TenantID,@RequestID,@SubjectID,@ModelName,'Reserved',@now);
 COMMIT TRAN;
 SELECT @RequestID AS RequestID,@count+1 AS UsedThisMonth,
        @limit AS MonthlyLimit;
END;
GO
CREATE OR ALTER PROCEDURE AgentProduct.FinalizeChatRequest
 @TenantID uniqueidentifier, @RequestID uniqueidentifier,
 @State varchar(12), @InputTokens int=NULL, @OutputTokens int=NULL
 WITH EXECUTE AS OWNER
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 IF @TenantID IS NULL OR @RequestID IS NULL OR
    TRY_CONVERT(uniqueidentifier,SESSION_CONTEXT(N'AgentTenantID'))<>@TenantID
    THROW 56810,'Invalid tenant context.',1;
 IF @State NOT IN ('Completed','Failed') OR @State IS NULL
    THROW 56811,'Invalid final state.',1;
 IF @InputTokens<0 OR @OutputTokens<0
    THROW 56812,'Invalid token count.',1;
 UPDATE AgentProduct.ChatRequest
 SET Status=@State,FinalizedAtUtc=SYSUTCDATETIME(),
     InputTokens=@InputTokens,OutputTokens=@OutputTokens
 WHERE TenantID=@TenantID AND RequestID=@RequestID AND Status='Reserved';
 IF @@ROWCOUNT<>1 THROW 56813,'Request not found or already finalized.',1;
END;
GO
/* Grant only narrow EXECUTE, not table writes; only after separate test login exists. */
IF USER_ID(N'AI_CommercialReader') IS NOT NULL
BEGIN
 GRANT EXECUTE ON OBJECT::AgentProduct.ReserveChatRequest TO [AI_CommercialReader];
 GRANT EXECUTE ON OBJECT::AgentProduct.FinalizeChatRequest TO [AI_CommercialReader];
END;
GO
SELECT DB_NAME() AS TestDB,
 OBJECT_ID(N'AgentProduct.ChatRequest',N'U') AS QuotaTable,
 OBJECT_ID(N'AgentProduct.ReserveChatRequest',N'P') AS ReserveProcedure,
 OBJECT_ID(N'AgentProduct.FinalizeChatRequest',N'P') AS FinalizeProcedure;
