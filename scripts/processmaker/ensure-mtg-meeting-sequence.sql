-- AVAN / ProcessMaker meeting-number prerequisite
-- Run once with a ProcessMaker workspace database administrator.
-- This migration is idempotent and does not delete or rewrite existing cases.
-- Select the target ProcessMaker workspace database before executing this file.

CREATE TABLE IF NOT EXISTS MTG_MEETING_SEQUENCE
(
    MEETING_NO INT UNSIGNED NOT NULL AUTO_INCREMENT,
    APP_UID VARCHAR(32) NOT NULL,
    PRO_UID VARCHAR(32) NOT NULL,
    CREATED_AT DATETIME NOT NULL,

    PRIMARY KEY (MEETING_NO),
    UNIQUE KEY UQ_MTG_MEETING_SEQUENCE_APP (APP_UID),
    KEY IX_MTG_MEETING_SEQUENCE_PROCESS (PRO_UID)
)
ENGINE=InnoDB
DEFAULT CHARSET=utf8
AUTO_INCREMENT=1001;

SELECT
    TABLE_SCHEMA,
    TABLE_NAME,
    ENGINE,
    AUTO_INCREMENT
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
  AND TABLE_NAME = 'MTG_MEETING_SEQUENCE';
