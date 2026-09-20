/* LAB ONLY: per-user confidential-letter grant contract.
   No office automation or ProcessMaker letter source has been mapped/imported.
   Regular, nonconfidential letters can be discovered by org subtree only.
   Confidential letters always require owner identity or explicit grant.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test' OR ISNULL(IS_SRVROLEMEMBER(N'sysadmin'),0)<>1
 THROW 60300,'Letter ACL migration TEST DBA only.',1;
IF OBJECT_ID(N'AgentProduct.LetterIndex',N'U') IS NULL
 THROW 60301,'Run directory schema 19 first.',1;
GO
IF OBJECT_ID(N'AgentProduct.LetterGrant',N'U') IS NULL
BEGIN
 CREATE TABLE AgentProduct.LetterGrant(
  TenantID uniqueidentifier NOT NULL,
  LetterID nvarchar(100) NOT NULL,
  SubjectID nvarchar(180) NOT NULL,
  CONSTRAINT PK_AP_LetterGrant PRIMARY KEY(TenantID,LetterID,SubjectID),
  CONSTRAINT FK_AP_LetterGrant_Letter FOREIGN KEY(TenantID,LetterID)
    REFERENCES AgentProduct.LetterIndex(TenantID,LetterID),
  CONSTRAINT FK_AP_LetterGrant_Membership FOREIGN KEY(TenantID,SubjectID)
    REFERENCES AgentProduct.Membership(TenantID,SubjectID)
 );
 CREATE INDEX IX_AP_LetterGrant_Subject
 ON AgentProduct.LetterGrant(TenantID,SubjectID,LetterID);
END;
GO
IF EXISTS(SELECT 1 FROM sys.security_predicates WHERE
 target_object_id=OBJECT_ID(N'AgentProduct.LetterGrant')
 AND predicate_type_desc='FILTER'
 AND object_id<>OBJECT_ID(N'AgentProduct.AgentProductTenantPolicy'))
 THROW 60302,'Unexpected letter-grant security policy.',1;
IF NOT EXISTS(SELECT 1 FROM sys.security_predicates WHERE
 target_object_id=OBJECT_ID(N'AgentProduct.LetterGrant')
 AND predicate_type_desc='FILTER')
 EXEC sys.sp_executesql N'ALTER SECURITY POLICY AgentProduct.AgentProductTenantPolicy
 ADD FILTER PREDICATE AgentProduct.fn_tenant_filter(TenantID)
 ON AgentProduct.LetterGrant;';
GO
IF USER_ID(N'AI_CommercialReader') IS NOT NULL
BEGIN
 GRANT SELECT ON AgentProduct.LetterIndex TO [AI_CommercialReader];
 GRANT SELECT ON AgentProduct.LetterGrant TO [AI_CommercialReader];
END;
GO
PRINT 'PASS: per-user confidential letter grants and tenant RLS schema created.';
PRINT 'NOTE: no letters imported or exposed from ProcessMaker or office automation.';
