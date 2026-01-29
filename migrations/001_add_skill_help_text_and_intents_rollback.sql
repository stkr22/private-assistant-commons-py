-- Rollback: Remove help_text from skills table and drop skill_intents table
-- Date: 2026-01-29
-- Description: Reverts migration 001 - removes skill_intents table and help_text column

-- Drop skill_intents table (CASCADE will drop dependent objects if any)
DROP TABLE IF EXISTS skill_intents CASCADE;

-- Remove help_text column from skills table
ALTER TABLE skills
DROP COLUMN IF EXISTS help_text;
