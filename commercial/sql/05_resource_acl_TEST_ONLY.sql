/* Commercial security lab: per-user grants. Execute only in isolated AI test DB.
   No production MTG data is copied or read. All permissions are explicit.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME() <> N'EnterpriseProcess2_AI_Test'
 THROW 56400, 'Wrong database', 1;
IF OBJECT_ID(N'AgentProduct.Membership',N'U') IS NULL
 THROW 56401, 'Run commercial SQL scripts 01 and 03 first', 1;
GO
IF OBJECT_ID(N'AgentProduct.MeetingGrant',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.MeetingGrant(
  TenantID uniqueidentifier NOT NULL,
  MeetingID bigint NOT NULL,
  SubjectID nvarchar(180) NOT NULL,
  CONSTRAINT PK_AP_MeetingGrant PRIMARY KEY(TenantID,MeetingID,SubjectID),
  CONSTRAINT FK_AP_MeetingGrant_Meeting FOREIGN KEY(TenantID,MeetingID)
   REFERENCES AgentProduct.MeetingIndex(TenantID,MeetingID),
  CONSTRAINT FK_AP_MeetingGrant_Membership FOREIGN KEY(TenantID,SubjectID)
   REFERENCES AgentProduct.Membership(TenantID,SubjectID)
 );
 CREATE INDEX IX_AP_MeetingGrant_User
   ON AgentProduct.MeetingGrant(TenantID,SubjectID,MeetingID);
END;
GO
IF OBJECT_ID(N'AgentProduct.DocumentGrant',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.DocumentGrant(
  TenantID uniqueidentifier NOT NULL,
  DocumentID uniqueidentifier NOT NULL,
  SubjectID nvarchar(180) NOT NULL,
  CONSTRAINT PK_AP_DocumentGrant PRIMARY KEY(TenantID,DocumentID,SubjectID),
  CONSTRAINT FK_AP_DocumentGrant_Document FOREIGN KEY(TenantID,DocumentID)
   REFERENCES AgentProduct.DocumentIndex(TenantID,DocumentID),
  CONSTRAINT FK_AP_DocumentGrant_Membership FOREIGN KEY(TenantID,SubjectID)
   REFERENCES AgentProduct.Membership(TenantID,SubjectID)
 );
 CREATE INDEX IX_AP_DocumentGrant_User
   ON AgentProduct.DocumentGrant(TenantID,SubjectID,DocumentID);
END;
GO
IF NOT EXISTS(
 SELECT 1 FROM sys.security_predicates sp
 JOIN sys.security_policies p ON p.object_id=sp.object_id
 WHERE p.name=N'AgentProductTenantPolicy'
   AND sp.target_object_id=OBJECT_ID(N'AgentProduct.MeetingGrant')
)
 ALTER SECURITY POLICY AgentProduct.AgentProductTenantPolicy
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID)
 ON AgentProduct.MeetingGrant;
GO
IF NOT EXISTS(
 SELECT 1 FROM sys.security_predicates sp
 JOIN sys.security_policies p ON p.object_id=sp.object_id
 WHERE p.name=N'AgentProductTenantPolicy'
   AND sp.target_object_id=OBJECT_ID(N'AgentProduct.DocumentGrant')
)
 ALTER SECURITY POLICY AgentProduct.AgentProductTenantPolicy
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID)
 ON AgentProduct.DocumentGrant;
GO
IF USER_ID(N'AI_CommercialReader') IS NOT NULL
BEGIN
 GRANT SELECT ON OBJECT::AgentProduct.MeetingGrant TO AI_CommercialReader;
 GRANT SELECT ON OBJECT::AgentProduct.DocumentGrant TO AI_CommercialReader;
 GRANT SELECT ON OBJECT::AgentProduct.DocumentIndex TO AI_CommercialReader;
 GRANT SELECT ON OBJECT::AgentProduct.DocumentChunk TO AI_CommercialReader;
END;
GO
SELECT DB_NAME() AS TestDB,
 OBJECT_ID(N'AgentProduct.MeetingGrant',N'U') AS MeetingGrantTable,
 OBJECT_ID(N'AgentProduct.DocumentGrant',N'U') AS DocumentGrantTable;
