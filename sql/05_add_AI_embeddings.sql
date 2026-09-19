/* Optional semantic-search columns, additive upgrade.
   Run once in SSMS by test DBA after 04_create_AI_knowledge_schema.sql.
   SQL Server 2022 stores float32 embeddings as varbinary; vector ranking is
   performed inside Python for SMALL test corpora (<=5000 active chunks). */
USE [EnterpriseProcess2_AI_Test];
GO
IF DB_NAME() <> N'EnterpriseProcess2_AI_Test'
    THROW 54120, 'Wrong database', 1;
IF OBJECT_ID(N'AI.DocumentChunk', N'U') IS NULL
    THROW 54121, 'First run sql/04_create_AI_knowledge_schema.sql', 1;
GO
IF COL_LENGTH(N'AI.DocumentChunk', N'Embedding') IS NULL
    ALTER TABLE [AI].[DocumentChunk] ADD [Embedding] varbinary(max) NULL;
IF COL_LENGTH(N'AI.DocumentChunk', N'EmbeddingModel') IS NULL
    ALTER TABLE [AI].[DocumentChunk] ADD [EmbeddingModel] nvarchar(80) NULL;
IF COL_LENGTH(N'AI.DocumentChunk', N'EmbeddingDimensions') IS NULL
    ALTER TABLE [AI].[DocumentChunk] ADD [EmbeddingDimensions] int NULL;
GO
SELECT DB_NAME() AS DatabaseName, COL_LENGTH(N'AI.DocumentChunk', N'Embedding') AS EmbeddingColumnExists;
