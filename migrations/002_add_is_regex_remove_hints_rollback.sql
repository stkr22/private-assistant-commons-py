-- Rollback: Remove is_regex from intent_pattern_keywords and recreate intent_pattern_hints
-- Date: 2026-01-29
-- Description: Reverts migration 002 - removes is_regex column and recreates hints table
-- WARNING: This rollback will recreate the hints table structure but cannot restore data

-- Remove is_regex column from intent_pattern_keywords table
ALTER TABLE intent_pattern_keywords
DROP COLUMN IF EXISTS is_regex;

-- Recreate intent_pattern_hints table (structure only, data cannot be restored)
CREATE TABLE IF NOT EXISTS intent_pattern_hints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_id UUID NOT NULL REFERENCES intent_patterns(id) ON DELETE CASCADE,
    hint TEXT NOT NULL,
    weight DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),

    -- Indexes for performance
    CONSTRAINT fk_intent_pattern_hints_pattern FOREIGN KEY (pattern_id) REFERENCES intent_patterns(id) ON DELETE CASCADE
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_intent_pattern_hints_pattern_id ON intent_pattern_hints(pattern_id);
CREATE INDEX IF NOT EXISTS idx_intent_pattern_hints_hint ON intent_pattern_hints(hint);

-- Add comment for documentation
COMMENT ON TABLE intent_pattern_hints IS 'Context hints for intent pattern confidence boosting (recreated by rollback - data not restored)';
