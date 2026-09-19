/* Read-only setup/quality checks for hybrid RAG prototype. */
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME() <> N'EnterpriseProcess2_AI_Test'
    THROW 54200, 'Wrong database', 1;
IF OBJECT_ID(N'AI.Document', N'U') IS NULL OR
   OBJECT_ID(N'AI.DocumentChunk', N'U') IS NULL
    THROW 54201, 'Run SQL scripts 04 and 05 first', 1;
GO
SELECT
    (SELECT COUNT_BIG(*) FROM MTG.Meeting WHERE MeetingNo LIKE N'SIM-MTG-A-%')
        AS SyntheticMeetings,
    (SELECT COUNT_BIG(*) FROM AI.Document WHERE IsCurrent=1 AND IsSynthetic=1)
        AS ActiveSyntheticDocuments,
    (SELECT COUNT_BIG(*) FROM AI.DocumentChunk c JOIN AI.Document d
     ON d.DocumentID=c.DocumentID WHERE d.IsCurrent=1 AND d.IsSynthetic=1)
        AS ActiveSyntheticChunks,
    (SELECT COUNT_BIG(*) FROM AI.DocumentChunk c JOIN AI.Document d
     ON d.DocumentID=c.DocumentID
     WHERE d.IsCurrent=1 AND d.IsSynthetic=1 AND c.Embedding IS NOT NULL)
        AS ActiveEmbeddedChunks;
GO
SELECT d.DocumentID,d.OriginalFileName,d.VersionNo,d.Sha256,d.IsCurrent,
       COUNT(c.ChunkID) AS Chunks, MIN(c.ChunkNo) AS FirstChunk,
       MAX(c.ChunkNo) AS LastChunk
FROM AI.Document d
LEFT JOIN AI.DocumentChunk c ON c.DocumentID=d.DocumentID
WHERE d.IsSynthetic=1
GROUP BY d.DocumentID,d.OriginalFileName,d.VersionNo,d.Sha256,d.IsCurrent
ORDER BY d.OriginalFileName,d.VersionNo DESC;
GO
SELECT TOP (20) d.DocumentID,c.ChunkNo,c.StartChar,c.EndChar,
       SUBSTRING(c.ChunkText,1,120) AS Excerpt
FROM AI.DocumentChunk c
JOIN AI.Document d ON d.DocumentID=c.DocumentID
WHERE d.IsCurrent=1 AND d.IsSynthetic=1
ORDER BY d.DocumentID,c.ChunkNo;
GO
-- All these data-quality checks should return zero.
SELECT
    (SELECT COUNT(*) FROM (
      SELECT OriginalFileName FROM AI.Document WHERE IsCurrent=1
      GROUP BY OriginalFileName HAVING COUNT(*) > 1
    ) x) AS MultipleCurrentVersions,
    (SELECT COUNT(*) FROM AI.DocumentChunk
     WHERE StartChar<0 OR EndChar<=StartChar
       OR LEN(ChunkText) > 1000) AS InvalidChunkRanges,
    (SELECT COUNT(*) FROM AI.DocumentChunk
     WHERE Embedding IS NOT NULL
       AND (EmbeddingDimensions IS NULL OR
            DATALENGTH(Embedding) <> 4*EmbeddingDimensions))
       AS InvalidEmbeddingLengths;
