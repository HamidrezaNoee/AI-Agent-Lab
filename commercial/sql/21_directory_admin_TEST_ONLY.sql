/* LAB ONLY: explicit tenant SysAdmin directory operations.
   Usernames/PM identifiers are not authentication credentials or admin grants.
   First SysAdmin identity must be approved/bootstrapped by a separately
   authorized platform GodAdmin / test DBA, never by PM sync or a public form.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test' OR ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0)<>1
 THROW 59900,'Directory admin migration: TEST DBA only.',1;
IF OBJECT_ID(N'AgentProduct.DirectoryUser',N'U') IS NULL
 THROW 59901,'Run directory migration 19 first.',1;
GO
CREATE OR ALTER PROCEDURE AgentProduct.SetOrgManager
 @TenantID uniqueidentifier,@ActorSubjectID nvarchar(180),
 @PMUserUID nvarchar(64),@ManagerPMUserUID nvarchar(64)=NULL
 WITH EXECUTE AS OWNER
AS
BEGIN
 SET NOCOUNT ON; SET XACT_ABORT ON;
 IF TRY_CONVERT(uniqueidentifier,SESSION_CONTEXT(N'AgentTenantID'))<>@TenantID
  OR @TenantID IS NULL THROW 59910,'Tenant context invalid.',1;
 IF NOT EXISTS(
   SELECT 1 FROM AgentProduct.DirectoryUser u
   JOIN AgentProduct.Membership m ON m.TenantID=u.TenantID AND m.SubjectID=u.SubjectID
   WHERE u.TenantID=@TenantID AND u.SubjectID=@ActorSubjectID
    AND u.OrgRole='SysAdmin' AND u.IsEnabled=1 AND u.PMStatus='ACTIVE'
    AND m.RoleCode IN('Admin','Owner') AND m.IsEnabled=1)
  THROW 59911,'Verified tenant SysAdmin required.',1;
 IF @ManagerPMUserUID=@PMUserUID
  THROW 59912,'An employee cannot be their own manager.',1;
 BEGIN TRAN;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.DirectoryUser
   WHERE TenantID=@TenantID AND PMUserUID=@PMUserUID)
  THROW 59913,'Employee is not registered in this tenant.',1;
 IF @ManagerPMUserUID IS NOT NULL AND NOT EXISTS(
   SELECT 1 FROM AgentProduct.DirectoryUser
   WHERE TenantID=@TenantID AND PMUserUID=@ManagerPMUserUID)
  THROW 59914,'Manager must be inside same tenant directory.',1;
 /* Walk the proposed manager's existing chain towards the root.
    If the employee is encountered, reassignment would create a cycle. */
 DECLARE @cursor nvarchar(64)=@ManagerPMUserUID,@hop int=0;
 WHILE @cursor IS NOT NULL
 BEGIN
  IF @cursor=@PMUserUID THROW 59915,'Reporting-line cycle denied.',1;
  IF @hop>=32 THROW 59916,'Reporting tree depth exceeded.',1;
  SELECT @cursor=ManagerPMUserUID FROM AgentProduct.DirectoryUser WITH (UPDLOCK,HOLDLOCK)
  WHERE TenantID=@TenantID AND PMUserUID=@cursor;
  SET @hop=@hop+1;
 END;
 UPDATE AgentProduct.DirectoryUser SET ManagerPMUserUID=@ManagerPMUserUID
 WHERE TenantID=@TenantID AND PMUserUID=@PMUserUID;
 INSERT AgentProduct.AuditEvent(TenantID,SubjectID,RequestID,EventType,ResourceType,ResourceID)
 VALUES(@TenantID,@ActorSubjectID,NEWID(),'OrgTreeChanged','Directory',@PMUserUID);
 COMMIT TRAN;
 SELECT @PMUserUID AS PMUserUID,@ManagerPMUserUID AS ManagerPMUserUID;
END;
GO
CREATE OR ALTER PROCEDURE AgentProduct.SetOrgRole
 @TenantID uniqueidentifier,@ActorSubjectID nvarchar(180),
 @PMUserUID nvarchar(64),@OrgRole varchar(12)
 WITH EXECUTE AS OWNER
AS
BEGIN
 SET NOCOUNT ON; SET XACT_ABORT ON;
 IF TRY_CONVERT(uniqueidentifier,SESSION_CONTEXT(N'AgentTenantID'))<>@TenantID
  OR @TenantID IS NULL THROW 59920,'Tenant context invalid.',1;
 /* SysAdmin cannot grant/revoke SysAdmin via this endpoint. GodAdmin
    provisioning is separate and must be audited and double-checked. */
 IF @OrgRole NOT IN('Expert','Manager') OR @OrgRole IS NULL
 THROW 59921,'Only Expert and Manager can be assigned by tenant SysAdmin.',1;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.DirectoryUser u
  JOIN AgentProduct.Membership m ON m.TenantID=u.TenantID AND m.SubjectID=u.SubjectID
  WHERE u.TenantID=@TenantID AND u.SubjectID=@ActorSubjectID
   AND u.OrgRole='SysAdmin' AND u.IsEnabled=1 AND u.PMStatus='ACTIVE'
   AND m.RoleCode IN('Admin','Owner') AND m.IsEnabled=1)
 THROW 59922,'Verified tenant SysAdmin required.',1;
 BEGIN TRAN;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.DirectoryUser
    WHERE TenantID=@TenantID AND PMUserUID=@PMUserUID AND OrgRole<>'SysAdmin')
  THROW 59923,'Cannot change missing user or privileged SysAdmin.',1;
 UPDATE AgentProduct.DirectoryUser SET OrgRole=@OrgRole
 WHERE TenantID=@TenantID AND PMUserUID=@PMUserUID AND OrgRole<>'SysAdmin';
 INSERT AgentProduct.AuditEvent(TenantID,SubjectID,RequestID,EventType,ResourceType,ResourceID)
 VALUES(@TenantID,@ActorSubjectID,NEWID(),'OrgRoleChanged','Directory',@PMUserUID);
 COMMIT TRAN;
 SELECT @PMUserUID AS PMUserUID,@OrgRole AS OrgRole;
END;
GO
/* Binding a ProcessMaker UID to a Keycloak subject is a security-sensitive
   operation. Never link by matching username automatically. It needs proof
   from the verified IdP and an approved platform operator; NOT granted to the
   ordinary tenant directory admin SQL login. */
IF USER_ID(N'AI_CommercialDirectoryAdmin') IS NOT NULL
BEGIN
 GRANT EXECUTE ON AgentProduct.SetOrgManager TO [AI_CommercialDirectoryAdmin];
 GRANT EXECUTE ON AgentProduct.SetOrgRole TO [AI_CommercialDirectoryAdmin];
END;
GO
PRINT 'PASS: tenant SysAdmin hierarchy and nonprivileged role procedures created.';
PRINT 'NOTE: OIDC subject binding, SysAdmin bootstrap and GodAdmin are NOT delegated.';
