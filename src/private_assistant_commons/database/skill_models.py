"""Database models for skill management.

This module provides SQLModel table definitions for managing skills and their
supported intents in the Private Assistant ecosystem.

Skills are components that handle specific types of commands (e.g., switch-skill,
media-skill). Each skill declares which intents it can handle by linking to the
IntentPattern table via the SkillIntent junction table.

Example:
    from private_assistant_commons.database import Skill, SkillIntent

    # Create a skill with help text
    skill = Skill(name="switch-skill", help_text="Controls switches via MQTT")

    # Link skill to supported intents
    skill_intent = SkillIntent(skill_id=skill.id, intent_pattern_id=pattern.id)

"""

from datetime import datetime
from typing import TYPE_CHECKING, Self
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel, select

if TYPE_CHECKING:
    from .device_models import GlobalDevice
    from .intent_pattern_models import IntentPattern


class Skill(SQLModel, table=True):
    """Skill model for tracking which skill owns each device.

    Skills are components that manage specific types of devices (e.g., switch-skill,
    media-skill). Each device must be associated with exactly one skill that handles
    its operations.

    Attributes:
        id: Unique identifier for the skill
        name: Unique skill name (e.g., "switch-skill", "media-skill")
        help_text: Optional description of skill capabilities for help system
        created_at: Timestamp when the skill was registered
        updated_at: Timestamp when the skill was last modified

    """

    __tablename__ = "skills"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)
    help_text: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    devices: list["GlobalDevice"] = Relationship(back_populates="skill")
    skill_intents: list["SkillIntent"] = Relationship(back_populates="skill")

    @classmethod
    async def get_by_name(cls, session, name: str) -> Self | None:
        """Find skill by name.

        Args:
            session: AsyncSession for database operations
            name: Skill name to search for

        Returns:
            Skill instance if found, None otherwise

        """
        result = await session.exec(select(cls).where(cls.name == name))
        return result.first()  # type: ignore[no-any-return]

    @classmethod
    async def ensure_exists(cls, session, name: str, help_text: str | None = None) -> Self:
        """Ensure skill exists in database, creating if necessary (idempotent).

        Args:
            session: AsyncSession for database operations
            name: Skill name to ensure exists
            help_text: Optional description of skill capabilities for help system

        Returns:
            Skill instance (existing or newly created)

        """
        skill = await cls.get_by_name(session, name)
        if skill is None:
            skill = cls(name=name, help_text=help_text)
            session.add(skill)
        # Update help_text if provided and different
        elif help_text is not None and skill.help_text != help_text:
            skill.help_text = help_text
            skill.updated_at = datetime.now()
            session.add(skill)

        await session.commit()
        await session.refresh(skill)
        return skill


class SkillIntent(SQLModel, table=True):
    """Junction table linking skills to their supported intents.

    This table stores which intents each skill can handle by referencing the
    IntentPattern table. It mirrors the runtime supported_intents dict for
    documentation and introspection purposes.

    Attributes:
        id: Unique identifier
        skill_id: Foreign key to skills table
        intent_pattern_id: Foreign key to intent_patterns table
        created_at: Timestamp when registered
        updated_at: Timestamp when last modified

    """

    __tablename__ = "skill_intents"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    skill_id: UUID = Field(foreign_key="skills.id", index=True)
    intent_pattern_id: UUID = Field(foreign_key="intent_patterns.id", index=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    skill: Skill = Relationship(back_populates="skill_intents")
    intent_pattern: "IntentPattern" = Relationship(back_populates="skill_intents")

    @classmethod
    async def upsert(cls, session, skill_id: UUID, intent_pattern_id: UUID) -> Self:
        """Create skill-intent mapping if it doesn't exist (idempotent).

        Args:
            session: AsyncSession for database operations
            skill_id: UUID of the skill
            intent_pattern_id: UUID of the intent pattern

        Returns:
            SkillIntent instance (existing or newly created)

        """
        statement = select(cls).where(cls.skill_id == skill_id, cls.intent_pattern_id == intent_pattern_id)
        result = await session.exec(statement)
        skill_intent = result.first()

        if skill_intent is None:
            skill_intent = cls(skill_id=skill_id, intent_pattern_id=intent_pattern_id)
            session.add(skill_intent)
            await session.commit()
            await session.refresh(skill_intent)

        return skill_intent  # type: ignore[no-any-return]
