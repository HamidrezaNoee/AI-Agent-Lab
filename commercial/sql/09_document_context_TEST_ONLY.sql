/* Test-only document context: link document to a meeting in SAME tenant.
   NULL means tenant-wide document, NOT a specific meeting's attachment.
   Run after 01,03,05; execute before enabling /v1/chat/answer.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test'
 THROW 57000,'Wrong database',1;
IF OBJECT_ID(N'AgentProduct.DocumentIndex',N'U') IS NULL
 OR OBJECT_ID(N'AgentProduct.MeetingIndex',N'U') IS NULL
 THROW 57001,'Run commercial SQL 01 and 05 first',1;
GO
IF COL_LENGTH(N'AgentProduct.DocumentIndex',N'RelatedMeetingID') IS NULL
 ALTER TABLE AgentProduct.DocumentIndex ADD RelatedMeetingID bigint NULL;
GO
IF NOT EXISTS(
 SELECT 1 FROM sys.foreign_keys
 WHERE name=N'FK_AP_DocumentIndex_RelatedMeeting'
 AND parent_object_id=OBJECT_ID(N'AgentProduct.DocumentIndex')
)
 ALTER TABLE AgentProduct.DocumentIndex
 ADD CONSTRAINT FK_AP_DocumentIndex_RelatedMeeting
 FOREIGN KEY(TenantID,RelatedMeetingID)
 REFERENCES AgentProduct.MeetingIndex(TenantID,MeetingID);
GO
SELECT DB_NAME() AS TestDB,
 COL_LENGTH(N'AgentProduct.DocumentIndex',N'RelatedMeetingID') AS MeetingLinkColumn,
 (SELECT COUNT_BIG(*) FROM AgentProduct.DocumentIndex WHERE RelatedMeetingID IS NOT NULL)
 AS MeetingLinkedDocumentsVisibleInCurrentTenantContext;
