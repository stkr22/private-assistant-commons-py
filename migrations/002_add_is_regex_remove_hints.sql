-- Migration: Add is_regex to intent_pattern_keywords and remove intent_pattern_hints
-- Date: 2026-01-29
-- Description: Adds is_regex field to support regex patterns in keywords.
--              Removes intent_pattern_hints table as hints are no longer used.

-- Add is_regex column to intent_pattern_keywords table
ALTER TABLE intent_pattern_keywords
ADD COLUMN IF NOT EXISTS is_regex BOOLEAN NOT NULL DEFAULT FALSE;

-- Create index on is_regex for performance
CREATE INDEX IF NOT EXISTS idx_intent_pattern_keywords_is_regex ON intent_pattern_keywords(is_regex);

-- Drop intent_pattern_hints table (CASCADE will handle foreign key dependencies)
DROP TABLE IF EXISTS intent_pattern_hints CASCADE;

-- Add comment for documentation
COMMENT ON COLUMN intent_pattern_keywords.is_regex IS 'Whether the keyword should be treated as a regex pattern';
