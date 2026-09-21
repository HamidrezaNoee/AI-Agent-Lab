/* AVAN production preflight; READ ONLY. Run in SSMS against the intended
   SQL Server instance. No INSERT, UPDATE, DELETE, ALTER or account changes. */
SET NOCOUNT ON;
IF DB_NAME()<>N'EnterpriseProcess2'
    THROW 60100, N'Wrong database: select EnterpriseProcess2 explicitly.', 1;

SELECT DB_NAME() AS DatabaseName, @@SERVERNAME AS ServerName,
       SYSUTCDATETIME() AS CheckedAtUTC,
       SERVERPROPERTY('ProductVersion') AS SQLVersion;
DECLARE @Required TABLE(TableName sysname, ColumnName sysname);
INSERT @Required(TableName, ColumnName) VALUES
('Meeting','MeetingID'),('Meeting','MeetingNo'),('Meeting','MeetingTitle'),
('Meeting','MeetingStartDateTime'),('Meeting','Status'),
('Meeting','ChairUserUID'),('Meeting','SecretaryUserUID'),
('Meeting','PMCaseUID'),('Meeting','ParkingLot'),
('MeetingParticipant','MeetingID'),('MeetingParticipant','UserUID'),
('MeetingParticipant','MeetingRole'),
('ActionItem','ActionItemID'),('ActionItem','MeetingID'),
('ActionItem','ActionNo'),('ActionItem','OwnerUserUID'),
('ActionItem','OwnerName'),('ActionItem','OwnerPosition'),
('ActionItem','ActionDescription'),('ActionItem','DueDateTime'),
('ActionItem','ProgressPercent'),('ActionItem','SecretaryProgressPercent'),
('ActionItem','Status'),('ActionItem','ClosedAt'),
('Decision','MeetingID'),('Decision','DecisionText');

SELECT r.TableName,r.ColumnName,
       CASE WHEN c.column_id IS NULL THEN 'MISSING' ELSE 'PRESENT' END AS Availability,
       TYPE_NAME(c.user_type_id) AS SqlDataType,
       c.max_length,c.is_nullable
FROM @Required r
LEFT JOIN sys.tables t ON t.name=r.TableName AND t.schema_id=SCHEMA_ID(N'MTG')
LEFT JOIN sys.columns c ON c.object_id=t.object_id AND c.name=r.ColumnName
ORDER BY r.TableName,r.ColumnName;

SELECT t.name AS TableName,c.column_id,c.name AS ColumnName,
       TYPE_NAME(c.user_type_id) AS SqlDataType,c.max_length,c.is_nullable
FROM sys.tables t JOIN sys.columns c ON c.object_id=t.object_id
WHERE t.schema_id=SCHEMA_ID(N'MTG')
 AND t.name IN(N'Meeting',N'MeetingParticipant',N'ActionItem',N'Decision')
ORDER BY t.name,c.column_id;
SELECT s.name AS SchemaName,t.name AS TableName
FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
WHERE s.name IN(N'MTG',N'AVAN') ORDER BY s.name,t.name;
SELECT N'No data or schema was changed.' AS Result;
