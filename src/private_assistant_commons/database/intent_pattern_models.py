"""Database models for intent pattern matching.

This module provides SQLModel table definitions for database-backed intent pattern
configurations that replace hardcoded pattern matching in the intent engine.

The intent pattern system consists of:
- IntentPattern: Core pattern configuration for identifying intent types
- IntentPatternKeyword: Primary and negative keywords for pattern matching
- IntentPatternHint: Context hints for confidence boosting

Intent patterns are loaded from the database by the intent-engine and can be
refreshed via MQTT messages, enabling dynamic pattern management without code changes.

Example:
    from private_assistant_commons.database import (
        IntentPattern,
        IntentPatternKeyword,
        IntentPatternHint,
    )

    # Create a pattern for DEVICE_ON intent
    pattern = IntentPattern(
        intent_type="device.on",
        enabled=True,
        priority=10,
        description="Turn on devices"
    )

    # Add primary keywords
    keywords = [
        IntentPatternKeyword(pattern_id=pattern.id, keyword="turn on", keyword_type="primary"),
        IntentPatternKeyword(pattern_id=pattern.id, keyword="switch on", keyword_type="primary"),
    ]

    # Add context hints
    hints = [
        IntentPatternHint(pattern_id=pattern.id, hint="light"),
        IntentPatternHint(pattern_id=pattern.id, hint="lamp"),
    ]

"""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .skill_models import SkillIntent


class IntentPattern(SQLModel, table=True):
    """Intent pattern configuration stored in database.

    Defines the core pattern for identifying a specific intent type.
    Keywords and hints are stored in separate tables for flexibility.

    Attributes:
        id: Unique identifier (UUID for consistency)
        intent_type: IntentType enum value (e.g., DEVICE_ON, QUERY_STATUS)
        enabled: Whether this pattern is active (for soft deletion)
        priority: Ordering priority when multiple patterns match (higher = checked first)
        description: Human-readable description for admin UI
        created_at: Pattern creation timestamp
        updated_at: Last modification timestamp

    """

    __tablename__ = "intent_patterns"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    intent_type: str = Field(index=True)
    enabled: bool = Field(default=True, index=True)
    priority: int = Field(default=0)
    description: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    keywords: list["IntentPatternKeyword"] = Relationship(
        back_populates="pattern", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    hints: list["IntentPatternHint"] = Relationship(
        back_populates="pattern", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    skill_intents: list["SkillIntent"] = Relationship(back_populates="intent_pattern")


class IntentPatternKeyword(SQLModel, table=True):
    """Keywords for intent pattern matching.

    Primary matching keywords (e.g., "turn on", "switch off").
    At least one keyword must be present for a valid pattern.
    Includes both primary and negative keywords via keyword_type field.

    Attributes:
        id: Unique identifier
        pattern_id: Foreign key to intent_pattern
        keyword: The matching keyword (stored lowercase)
        keyword_type: Type of keyword (primary/negative)
        weight: Optional weight for confidence scoring (future use)
        created_at: Timestamp when the keyword was created

    """

    __tablename__ = "intent_pattern_keywords"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pattern_id: UUID = Field(foreign_key="intent_patterns.id", index=True)
    keyword: str = Field(index=True)
    keyword_type: str = Field(default="primary", index=True)
    weight: float = Field(default=1.0)
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    pattern: IntentPattern = Relationship(back_populates="keywords")


class IntentPatternHint(SQLModel, table=True):
    """Context hints for intent pattern confidence boosting.

    Supporting words that strengthen intent confidence when present
    (e.g., "light", "lamp", "device" for DEVICE_ON).

    Attributes:
        id: Unique identifier
        pattern_id: Foreign key to intent_pattern
        hint: The context hint (stored lowercase)
        weight: Optional weight for confidence scoring (future use)
        created_at: Timestamp when the hint was created

    """

    __tablename__ = "intent_pattern_hints"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pattern_id: UUID = Field(foreign_key="intent_patterns.id", index=True)
    hint: str = Field(index=True)
    weight: float = Field(default=1.0)
    created_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    pattern: IntentPattern = Relationship(back_populates="hints")
