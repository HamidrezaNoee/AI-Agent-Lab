/* Run as test DBA after creating the schema and the AI_MeetingAgent SERVER LOGIN. */
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME() <> N'EnterpriseProcess2_AI_Test' THROW 53004, 'Wrong database', 1;
IF SUSER_ID(N'AI_MeetingAgent') IS NULL THROW 53005, 'Missing server login AI_MeetingAgent', 1;
IF USER_ID(N'AI_MeetingAgent') IS NULL CREATE USER [AI_MeetingAgent] FOR LOGIN [AI_MeetingAgent];
GRANT SELECT ON OBJECT::[MTG].[Meeting] TO [AI_MeetingAgent];
GRANT SELECT ON OBJECT::[MTG].[ActionItem] TO [AI_MeetingAgent];
GRANT SELECT ON OBJECT::[MTG].[ActionReview] TO [AI_MeetingAgent];
GRANT SELECT ON OBJECT::[MTG].[Decision] TO [AI_MeetingAgent];
GRANT SELECT ON OBJECT::[MTG].[ActionUpdate] TO [AI_MeetingAgent];
GRANT SELECT ON OBJECT::[MTG].[AgendaItem] TO [AI_MeetingAgent];
GRANT SELECT ON OBJECT::[MTG].[MeetingParticipant] TO [AI_MeetingAgent];
GO
