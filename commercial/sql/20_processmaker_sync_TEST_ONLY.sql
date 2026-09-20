/* Secure, additive LAB-only ProcessMaker user sync procedures.
   NEVER writes PM database; input must be a complete whitelist-only REST snapshot.
   Requires 19_directory_hierarchy_TEST_ONLY.sql.
   Accounts are created DISABLED and UNBOUND; sync NEVER assigns OIDC SubjectID,
   reporting-line ManagerPMUserUID, OrgRole or user-managed IsEnabled.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test' OR ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0)<>1
 THROW 59800,'Run only as TEST DBA in isolated AI database.',1;
IF OBJECT_ID(N'AgentProduct.DirectoryUser',N'U') IS NULL
 THROW 59801,'Run isolated directory migration 19 first.',1;
GO
CREATE OR ALTER PROCEDURE AgentProduct.SyncProcessMakerUsers
 @TenantID uniqueidentifier,
 @ActorSubjectID nvarchar(180),
 @UsersJson nvarchar(max),
 @ExpectedCount int,
 @DeactivateMissing bit=0
 WITH EXECUTE AS OWNER
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 IF @TenantID IS NULL OR
 TRY_CONVERT(uniqueidentifier,SESSION_CONTEXT(N'AgentTenantID'))<>@TenantID
 THROW 59810,'Tenant context missing or mismatched.',1;
 IF @ExpectedCount IS NULL OR @ExpectedCount<1 OR @ExpectedCount>5000
  OR @UsersJson IS NULL OR DATALENGTH(@UsersJson)>10485760 OR ISJSON(@UsersJson)<>1
 THROW 59811,'Invalid or empty ProcessMaker snapshot.',1;
 IF LEFT(LTRIM(@UsersJson),1)<>N'['
 THROW 59812,'ProcessMaker snapshot must be a JSON array.',1;
 IF NOT EXISTS (
  SELECT 1 FROM AgentProduct.DirectoryUser u
  JOIN AgentProduct.Membership m ON m.TenantID=u.TenantID AND m.SubjectID=u.SubjectID
  JOIN AgentProduct.Tenant t ON t.TenantID=m.TenantID
  JOIN AgentProduct.Subscription s ON s.TenantID=t.TenantID
  WHERE u.TenantID=@TenantID AND u.SubjectID=@ActorSubjectID
    AND u.OrgRole='SysAdmin' AND u.IsEnabled=1 AND u.PMStatus='ACTIVE'
    AND m.RoleCode IN('Admin','Owner') AND m.IsEnabled=1 AND t.IsEnabled=1
    AND s.IsActive=1 AND s.ExpiresAtUtc>SYSUTCDATETIME()
 ) THROW 59813,'Verified active tenant SysAdmin required for directory sync.',1;
 DECLARE @rows TABLE(
 PMUserUID nvarchar(64) NOT NULL PRIMARY KEY,
 UserName nvarchar(120) NOT NULL,
 DisplayName nvarchar(240) NOT NULL,
 Email nvarchar(240) NULL,
 PMStatus varchar(12) NOT NULL
 );
 BEGIN TRY
 INSERT @rows(PMUserUID,UserName,DisplayName,Email,PMStatus)
 SELECT LOWER(PMUserUID), UserName, DisplayName, NULLIF(Email,N''), UPPER(PMStatus)
 FROM OPENJSON(@UsersJson) WITH (
 PMUserUID nvarchar(64) '$.pm_uid',
 UserName nvarchar(120) '$.username',
 DisplayName nvarchar(240) '$.display_name',
 Email nvarchar(240) '$.email',
 PMStatus varchar(12) '$.status'
 );
 END TRY
 BEGIN CATCH
  THROW 59814,'Invalid or duplicate ProcessMaker user identifiers.',1;
 END CATCH;
 IF (SELECT COUNT(*) FROM @rows)<>@ExpectedCount
 THROW 59815,'Snapshot record count did not match expected complete REST result.',1;
 IF EXISTS(
 SELECT 1 FROM @rows WHERE LEN(PMUserUID)<>32
 OR PMUserUID COLLATE Latin1_General_BIN2 LIKE '%[^0-9a-f]%'
 OR LEN(LTRIM(RTRIM(UserName)))=0 OR LEN(LTRIM(RTRIM(DisplayName)))=0
 OR PMStatus NOT IN('ACTIVE','INACTIVE','VACATION'))
 THROW 59816,'Malformed source UID, name or status.',1;
 DECLARE @missing int=(SELECT COUNT(*) FROM AgentProduct.DirectoryUser d
 WHERE d.TenantID=@TenantID AND NOT EXISTS(SELECT 1 FROM @rows r WHERE r.PMUserUID=d.PMUserUID));
 DECLARE @existing int=(SELECT COUNT(*) FROM AgentProduct.DirectoryUser WHERE TenantID=@TenantID);
 IF @DeactivateMissing=1 AND @missing>0 AND
     (@missing>10 AND @missing*5>@existing)
 THROW 59817,'Large deletion detected: manual reconciliation required.',1;
 DECLARE @new int=0,@updated int=0,@deactivated int=0;
 BEGIN TRY
 BEGIN TRAN;
 UPDATE d SET
  d.PMUserName=r.UserName,d.DisplayName=r.DisplayName,
  d.Email=r.Email,d.PMStatus=r.PMStatus,d.LastSeenAtUtc=SYSUTCDATETIME()
 FROM AgentProduct.DirectoryUser d JOIN @rows r ON r.PMUserUID=d.PMUserUID
 WHERE d.TenantID=@TenantID;
 SET @updated=@@ROWCOUNT;
 INSERT AgentProduct.DirectoryUser
 (TenantID,PMUserUID,PMUserName,DisplayName,Email,PMStatus)
 SELECT @TenantID,r.PMUserUID,r.UserName,r.DisplayName,r.Email,r.PMStatus
 FROM @rows r WHERE NOT EXISTS(
 SELECT 1 FROM AgentProduct.DirectoryUser d
 WHERE d.TenantID=@TenantID AND d.PMUserUID=r.PMUserUID);
 SET @new=@@ROWCOUNT;
 IF @DeactivateMissing=1
 BEGIN
  UPDATE d SET PMStatus='INACTIVE',LastSeenAtUtc=SYSUTCDATETIME()
  FROM AgentProduct.DirectoryUser d
  WHERE d.TenantID=@TenantID AND d.PMStatus<>'INACTIVE'
    AND NOT EXISTS(SELECT 1 FROM @rows r WHERE r.PMUserUID=d.PMUserUID);
  SET @deactivated=@@ROWCOUNT;
 END;
 INSERT AgentProduct.AuditEvent(TenantID,SubjectID,RequestID,EventType,ResourceType,ResourceID)
 VALUES(@TenantID,@ActorSubjectID,NEWID(),'PMDirectorySync','Directory',CONVERT(nvarchar(20),@ExpectedCount));
 COMMIT TRAN;
 END TRY
 BEGIN CATCH
  IF @@TRANCOUNT>0 ROLLBACK TRAN;
  THROW;
 END CATCH;
 SELECT @ExpectedCount AS Seen, @new AS NewDisabledUnbound, @updated AS ExistingProfiles,
 @missing AS MissingFromSource, @deactivated AS MarkedInactive,
 CAST(0 AS bit) AS IdentitiesAutoLinked, CAST(0 AS bit) AS RolesAutoGranted;
END;
GO
/* Only a SEPARATE, authorized ADMIN SQL login may EXEC this narrow procedure.
   The existing AI_CommercialReader MUST NOT get EXEC permission. */
IF USER_ID(N'AI_CommercialDirectoryAdmin') IS NOT NULL
 GRANT EXECUTE ON AgentProduct.SyncProcessMakerUsers TO [AI_CommercialDirectoryAdmin];
GO
PRINT 'PASS: tenant-bound, audited ProcessMaker user sync procedure created; no users imported.';
