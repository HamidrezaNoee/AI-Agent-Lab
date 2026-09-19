/* New EMPTY sandbox database. Never use the production ProcessMaker database. */
USE [master];
GO
IF DB_ID(N'EnterpriseProcess2_AI_Test') IS NOT NULL
    THROW 53001, 'Test database already exists; will not overwrite.', 1;
CREATE DATABASE [EnterpriseProcess2_AI_Test];
GO
SELECT name,state_desc FROM sys.databases WHERE name=N'EnterpriseProcess2_AI_Test';
GO
