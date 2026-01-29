-- Migration: Add help_text to skills table and create skill_intents junction table
-- Date: 2026-01-29
-- Description: Adds help_text field for skill documentation and creates skill_intents
--              table to track which intents each skill supports.

-- Add help_text column to existing skills table
ALTER TABLE skills
ADD COLUMN IF NOT EXISTS help_text TEXT;

-- Create skill_intents junction table
CREATE TABLE IF NOT EXISTS skill_intents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_id UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    intent_pattern_id UUID NOT NULL REFERENCES intent_patterns(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),

    -- Ensure unique skill-intent combinations
    CONSTRAINT skill_intent_unique UNIQUE (skill_id, intent_pattern_id)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_skill_intents_skill_id ON skill_intents(skill_id);
CREATE INDEX IF NOT EXISTS idx_skill_intents_intent_pattern_id ON skill_intents(intent_pattern_id);

-- Add comment for documentation
COMMENT ON TABLE skill_intents IS 'Junction table linking skills to their supported intent patterns for documentation and introspection';
COMMENT ON COLUMN skills.help_text IS 'Human-readable description of skill capabilities for help system';
