/*
Synthetic-document knowledge store for the Meeting AI prototype.
EXECUTE ONLY on the isolated test database, with an administrator login.
Document chunks are NOT embeddings and are NOT a semantic search index.
*/
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME() <> N'EnterpriseProcess2_AI_Test'
    THROW 54001, 'Safety check: wrong database.', 1;
IF OBJECT_ID(N'MTG.Meeting', N'U') IS NULL
    THROW 54002, 'MTG test schema is missing.', 1;
GO

IF SCHEMA_ID(N'AI') IS NULL EXEC(N'CREATE SCHEMA [AI] AUTHORIZATION [dbo]');
GO
IF OBJECT_ID(N'AI.Document', N'U') IS NULL
BEGIN
    CREATE TABLE [AI].[Document](
        DocumentID bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
        OriginalFileName nvarchar(260) NOT NULL,
        Title nvarchar(300) NOT NULL,
        FileType varchar(10) NOT NULL,
        Sha256 char(64) NOT NULL,
        VersionNo int NOT NULL,
        IsCurrent bit NOT NULL CONSTRAINT DF_AI_Document_IsCurrent DEFAULT (1),
        IsSynthetic bit NOT NULL CONSTRAINT DF_AI_Document_IsSynthetic DEFAULT (1),
        RelatedMeetingID bigint NULL,
        CharCount int NOT NULL,
        ImportedAt datetime2(0) NOT NULL CONSTRAINT DF_AI_Document_ImportedAt DEFAULT SYSUTCDATETIME(),
        CONSTRAINT FK_AI_Document_Meeting FOREIGN KEY(RelatedMeetingID)
            REFERENCES MTG.Meeting(MeetingID),
        CONSTRAINT UQ_AI_Document_NameVersion UNIQUE(OriginalFileName, VersionNo),
        CONSTRAINT CK_AI_Document_Synthetic CHECK (IsSynthetic = 1),
        CONSTRAINT CK_AI_Document_CharCount CHECK (CharCount > 0)
    );
END;
GO
IF OBJECT_ID(N'AI.DocumentChunk', N'U') IS NULL
BEGIN
    CREATE TABLE [AI].[DocumentChunk](
        ChunkID bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
        DocumentID bigint NOT NULL,
        ChunkNo int NOT NULL,
        StartChar int NOT NULL,
        EndChar int NOT NULL,
        ChunkText nvarchar(max) NOT NULL,
        Embedding varbinary(max) NULL,
        EmbeddingModel varchar(100) NULL,
        CONSTRAINT FK_AI_DocumentChunk_Document FOREIGN KEY(DocumentID)
            REFERENCES AI.Document(DocumentID),
        CONSTRAINT UQ_AI_DocumentChunk_Number UNIQUE(DocumentID, ChunkNo),
        CONSTRAINT CK_AI_DocumentChunk_Range CHECK
            (ChunkNo >= 1 AND StartChar >= 0 AND EndChar > StartChar)
    );
    CREATE INDEX IX_AI_DocumentChunk_DocumentID ON AI.DocumentChunk(DocumentID);
END;
GO
/* Upgrade pre-existing test tables without dropping any data. */
IF COL_LENGTH(N'AI.DocumentChunk', N'Embedding') IS NULL
    ALTER TABLE [AI].[DocumentChunk] ADD Embedding varbinary(max) NULL;
IF COL_LENGTH(N'AI.DocumentChunk', N'EmbeddingModel') IS NULL
    ALTER TABLE [AI].[DocumentChunk] ADD EmbeddingModel varchar(100) NULL;
GO
IF USER_ID(N'AI_MeetingAgent') IS NULL
    THROW 54003, 'Create/map the read-only AI_MeetingAgent user first.', 1;
GRANT SELECT ON OBJECT::[AI].[Document] TO [AI_MeetingAgent];
GRANT SELECT ON OBJECT::[AI].[DocumentChunk] TO [AI_MeetingAgent];
GO
SELECT
    OBJECT_ID(N'AI.Document', N'U') AS DocumentTableID,
    OBJECT_ID(N'AI.DocumentChunk', N'U') AS ChunkTableID,
    DB_NAME() AS DatabaseName;
