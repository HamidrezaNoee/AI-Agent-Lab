/* TEST-ONLY synthetic verification of hierarchy authorization. No PM production reads. */
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test' THROW 57200,'Wrong database',1;
IF OBJECT_ID(N'AgentProduct.UserDirectory',N'U') IS NULL THROW 57201,'Run 15 first',1;
GO
BEGIN TRAN;
BEGIN TRY
 DECLARE @T uniqueidentifier='11111111-1111-4111-8111-111111111111';
 EXEC sys.sp_set_session_context @key=N'AgentTenantID',@value=@T;

 /* Reuse existing fictional lab subjects and add hierarchy-only identities. */
 UPDATE AgentProduct.Membership SET RoleCode='Expert' WHERE TenantID=@T AND SubjectID='lab-alice';
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.Membership WHERE TenantID=@T AND SubjectID='lab-manager')
  INSERT AgentProduct.Membership(TenantID,SubjectID,RoleCode,IsEnabled) VALUES(@T,'lab-manager','Manager',1);
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.Membership WHERE TenantID=@T AND SubjectID='lab-sysadmin')
  INSERT AgentProduct.Membership(TenantID,SubjectID,RoleCode,IsEnabled) VALUES(@T,'lab-sysadmin','SysAdmin',1);

 MERGE AgentProduct.UserDirectory AS t USING(VALUES
 (@T,N'lab-alice','pm-alice',N'alice',N'کارشناس ساختگی',N'Expert'),
 (@T,N'lab-manager','pm-manager',N'manager',N'مدیر ساختگی',N'Manager'),
 (@T,N'lab-sysadmin',NULL,NULL,N'مدیر سیستم ساختگی',N'SysAdmin')
 )s(TenantID,SubjectID,PMUID,PMUser,DisplayName,Kind)
 ON t.TenantID=s.TenantID AND t.SubjectID=s.SubjectID
 WHEN MATCHED THEN UPDATE SET DisplayName=s.DisplayName,UserKind=s.Kind,IsEnabled=1
 WHEN NOT MATCHED THEN INSERT(TenantID,SubjectID,ProcessMakerUserUID,ProcessMakerUsername,DisplayName,UserKind,IsEnabled)
 VALUES(s.TenantID,s.SubjectID,s.PMUID,s.PMUser,s.DisplayName,s.Kind,1);

 DECLARE @root bigint,@child bigint;
 INSERT AgentProduct.OrganizationNode(TenantID,NodeCode,NodeName,NodeType)
 VALUES(@T,N'ROOT-LAB',N'مدیریت ساختگی',N'Department');SET @root=SCOPE_IDENTITY();
 INSERT AgentProduct.OrganizationNode(TenantID,ParentNodeID,NodeCode,NodeName,NodeType)
 VALUES(@T,@root,N'CHILD-LAB',N'کارشناس ساختگی',N'Position');SET @child=SCOPE_IDENTITY();
 INSERT AgentProduct.UserOrganizationAssignment(TenantID,SubjectID,NodeID) VALUES
 (@T,'lab-manager',@root),(@T,'lab-alice',@child);
 INSERT AgentProduct.MeetingParticipantIndex(TenantID,MeetingID,SubjectID,ParticipantRole)
 VALUES(@T,900001,'lab-alice','ActionOwner');

 IF NOT EXISTS(SELECT 1 FROM AgentProduct.fn_can_view_meeting(@T,'lab-alice',900001) WHERE Allowed=1)
  THROW 57210,'Expert must see own involved meeting',1;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.fn_can_view_meeting(@T,'lab-manager',900001) WHERE Allowed=1)
  THROW 57211,'Manager must see subordinate involved meeting',1;
 IF NOT EXISTS(SELECT 1 FROM AgentProduct.fn_can_view_meeting(@T,'lab-sysadmin',900001) WHERE Allowed=1)
  THROW 57212,'SysAdmin must see tenant meeting',1;

 SELECT N'PASS: expert direct involvement, manager subtree and sysadmin tenant visibility.' AS Result;
 ROLLBACK;
END TRY
BEGIN CATCH
 IF @@TRANCOUNT>0 ROLLBACK;
 THROW;
END CATCH;
GO
