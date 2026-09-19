USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME()<>N'EnterpriseProcess2_AI_Test' THROW 53006,'Wrong database',1;
SELECT 'Meetings' Entity,COUNT_BIG(*) Actual,CONVERT(bigint,1100) Expected FROM MTG.Meeting WHERE MeetingNo LIKE N'SIM-MTG-A-%'
UNION ALL SELECT 'Decisions',COUNT_BIG(*),6600 FROM MTG.Decision d JOIN MTG.Meeting m ON m.MeetingID=d.MeetingID WHERE m.MeetingNo LIKE N'SIM-MTG-A-%'
UNION ALL SELECT 'Actions',COUNT_BIG(*),8800 FROM MTG.ActionItem a JOIN MTG.Meeting m ON m.MeetingID=a.MeetingID WHERE m.MeetingNo LIKE N'SIM-MTG-A-%'
UNION ALL SELECT 'Updates',COUNT_BIG(*),17600 FROM MTG.ActionUpdate u JOIN MTG.ActionItem a ON a.ActionItemID=u.ActionItemID JOIN MTG.Meeting m ON m.MeetingID=a.MeetingID WHERE m.MeetingNo LIKE N'SIM-MTG-A-%'
UNION ALL SELECT 'Reviews',COUNT_BIG(*),17600 FROM MTG.ActionReview r JOIN MTG.ActionItem a ON a.ActionItemID=r.ActionItemID JOIN MTG.Meeting m ON m.MeetingID=a.MeetingID WHERE m.MeetingNo LIKE N'SIM-MTG-A-%';
SELECT TOP (10) m.MeetingID,m.MeetingNo,m.MeetingTitle,a.ActionNo,a.DecisionNo,a.Status,a.ProgressPercent
FROM MTG.Meeting m JOIN MTG.ActionItem a ON a.MeetingID=m.MeetingID WHERE m.MeetingNo LIKE N'SIM-MTG-A-%'
ORDER BY m.MeetingID,a.ActionNo;
GO
