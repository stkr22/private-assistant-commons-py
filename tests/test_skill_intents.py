"""Unit tests for Skill and SkillIntent models."""

import uuid

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from private_assistant_commons.database import IntentPattern, Skill, SkillIntent


@pytest_asyncio.fixture
async def engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create skill, intent_pattern, and skill_intent tables
    async with engine.begin() as conn:
        tables = [Skill.__table__, IntentPattern.__table__, SkillIntent.__table__]
        await conn.run_sync(lambda sync_conn: Skill.metadata.create_all(sync_conn, tables=tables))

    yield engine

    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine):
    """Create a database session for testing."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


class TestSkillModel:
    """Test Skill model with help_text functionality."""

    async def test_skill_creation_minimal(self, session: AsyncSession):
        """Test creating a skill with minimal required fields."""
        skill = Skill(name="test-skill")
        session.add(skill)
        await session.commit()
        await session.refresh(skill)

        assert skill.id is not None
        assert isinstance(skill.id, uuid.UUID)
        assert skill.name == "test-skill"
        assert skill.help_text is None
        assert skill.created_at is not None
        assert skill.updated_at is not None

    async def test_skill_creation_with_help_text(self, session: AsyncSession):
        """Test creating a skill with help text."""
        help_text = "Controls lights via Home Assistant MQTT"
        skill = Skill(name="switch-skill", help_text=help_text)
        session.add(skill)
        await session.commit()
        await session.refresh(skill)

        assert skill.id is not None
        assert skill.name == "switch-skill"
        assert skill.help_text == help_text

    async def test_skill_get_by_name(self, session: AsyncSession):
        """Test finding skill by name."""
        skill = Skill(name="media-skill", help_text="Plays media")
        session.add(skill)
        await session.commit()

        found_skill = await Skill.get_by_name(session, "media-skill")
        assert found_skill is not None
        assert found_skill.name == "media-skill"
        assert found_skill.help_text == "Plays media"

        not_found = await Skill.get_by_name(session, "non-existent")
        assert not_found is None

    async def test_skill_ensure_exists_creates_new(self, session: AsyncSession):
        """Test ensure_exists creates a new skill if it doesn't exist."""
        skill = await Skill.ensure_exists(session, "new-skill", help_text="New skill help")

        assert skill.id is not None
        assert skill.name == "new-skill"
        assert skill.help_text == "New skill help"

        # Verify it's in the database
        statement = select(Skill).where(Skill.name == "new-skill")
        result = await session.exec(statement)
        found = result.first()
        assert found is not None
        assert found.name == "new-skill"

    async def test_skill_ensure_exists_returns_existing(self, session: AsyncSession):
        """Test ensure_exists returns existing skill without changes."""
        # Create initial skill
        original = await Skill.ensure_exists(session, "existing-skill", help_text="Original help")
        original_id = original.id
        original_updated = original.updated_at

        # Call ensure_exists again without help_text
        skill = await Skill.ensure_exists(session, "existing-skill")

        assert skill.id == original_id
        assert skill.help_text == "Original help"  # Unchanged
        assert skill.updated_at == original_updated  # Not updated

    async def test_skill_ensure_exists_updates_help_text(self, session: AsyncSession):
        """Test ensure_exists updates help_text if provided and different."""
        # Create initial skill
        original = await Skill.ensure_exists(session, "update-skill", help_text="Old help")
        original_id = original.id

        # Update with new help_text
        updated = await Skill.ensure_exists(session, "update-skill", help_text="New help")

        assert updated.id == original_id
        assert updated.help_text == "New help"
        assert updated.updated_at >= original.updated_at  # >= because timestamps may be same in fast tests

    async def test_skill_ensure_exists_no_update_same_help_text(self, session: AsyncSession):
        """Test ensure_exists doesn't update if help_text is the same."""
        # Create initial skill
        original = await Skill.ensure_exists(session, "same-skill", help_text="Same help")
        original_updated = original.updated_at

        # Call with same help_text
        skill = await Skill.ensure_exists(session, "same-skill", help_text="Same help")

        assert skill.help_text == "Same help"
        assert skill.updated_at == original_updated  # Not updated


class TestSkillIntentModel:
    """Test SkillIntent junction table model."""

    async def test_skill_intent_creation(self, session: AsyncSession):
        """Test creating a skill-intent mapping."""
        # Create an intent pattern first
        intent_pattern = IntentPattern(intent_type="device.on")
        session.add(intent_pattern)
        await session.commit()
        await session.refresh(intent_pattern)

        # Create a skill
        skill = Skill(name="test-skill")
        session.add(skill)
        await session.commit()
        await session.refresh(skill)

        # Create skill-intent mapping
        skill_intent = SkillIntent(skill_id=skill.id, intent_pattern_id=intent_pattern.id)
        session.add(skill_intent)
        await session.commit()
        await session.refresh(skill_intent)

        assert skill_intent.id is not None
        assert isinstance(skill_intent.id, uuid.UUID)
        assert skill_intent.skill_id == skill.id
        assert skill_intent.intent_pattern_id == intent_pattern.id
        assert skill_intent.created_at is not None
        assert skill_intent.updated_at is not None

    async def test_skill_intent_relationship(self, session: AsyncSession):
        """Test relationship between Skill and SkillIntent."""
        # Create intent patterns
        pattern1 = IntentPattern(intent_type="device.on")
        pattern2 = IntentPattern(intent_type="device.off")
        session.add(pattern1)
        session.add(pattern2)
        await session.commit()
        await session.refresh(pattern1)
        await session.refresh(pattern2)

        # Create skill
        skill = Skill(name="relationship-skill")
        session.add(skill)
        await session.commit()
        await session.refresh(skill)

        # Create multiple skill-intent mappings
        intent1 = SkillIntent(skill_id=skill.id, intent_pattern_id=pattern1.id)
        intent2 = SkillIntent(skill_id=skill.id, intent_pattern_id=pattern2.id)
        session.add(intent1)
        session.add(intent2)
        await session.commit()

        # Query intents and verify relationships
        intent_statement = select(SkillIntent).where(SkillIntent.skill_id == skill.id)
        intent_result = await session.exec(intent_statement)
        intents = intent_result.all()

        assert len(intents) == 2
        assert {i.intent_pattern_id for i in intents} == {pattern1.id, pattern2.id}

    async def test_skill_intent_upsert_creates_new(self, session: AsyncSession):
        """Test upsert creates new skill-intent mapping."""
        # Create intent pattern
        pattern = IntentPattern(intent_type="device.set")
        session.add(pattern)
        await session.commit()
        await session.refresh(pattern)

        # Create skill
        skill = Skill(name="upsert-skill")
        session.add(skill)
        await session.commit()
        await session.refresh(skill)

        # Upsert skill-intent mapping
        skill_intent = await SkillIntent.upsert(session, skill.id, pattern.id)

        assert skill_intent.id is not None
        assert skill_intent.skill_id == skill.id
        assert skill_intent.intent_pattern_id == pattern.id

    async def test_skill_intent_upsert_returns_existing(self, session: AsyncSession):
        """Test upsert returns existing skill-intent mapping if already exists."""
        # Create intent pattern
        pattern = IntentPattern(intent_type="media.play")
        session.add(pattern)
        await session.commit()
        await session.refresh(pattern)

        # Create skill
        skill = Skill(name="existing-mapping-skill")
        session.add(skill)
        await session.commit()
        await session.refresh(skill)

        # Create initial mapping
        original = await SkillIntent.upsert(session, skill.id, pattern.id)
        original_id = original.id

        # Call upsert again - should return existing
        existing = await SkillIntent.upsert(session, skill.id, pattern.id)

        assert existing.id == original_id
        assert existing.skill_id == skill.id
        assert existing.intent_pattern_id == pattern.id


class TestSkillIntentIntegration:
    """Integration tests for skill registration with intents."""

    async def test_skill_with_multiple_intents(self, session: AsyncSession):
        """Test creating a skill with multiple intent mappings."""
        # Create intent patterns
        patterns = []
        for intent_type in ["device.on", "device.off", "device.set"]:
            pattern = IntentPattern(intent_type=intent_type)
            session.add(pattern)
            patterns.append(pattern)
        await session.commit()
        for pattern in patterns:
            await session.refresh(pattern)

        # Create skill
        skill = await Skill.ensure_exists(session, "multi-intent-skill", help_text="Handles multiple intents")

        # Add multiple intents
        for pattern in patterns:
            await SkillIntent.upsert(session, skill.id, pattern.id)

        # Verify all intents are registered
        statement = select(SkillIntent).where(SkillIntent.skill_id == skill.id)
        result = await session.exec(statement)
        registered_intents = result.all()

        assert len(registered_intents) == 3
        registered_pattern_ids = {si.intent_pattern_id for si in registered_intents}
        expected_pattern_ids = {p.id for p in patterns}
        assert registered_pattern_ids == expected_pattern_ids

    async def test_remove_stale_intents(self, session: AsyncSession):
        """Test removing intents that are no longer supported."""
        # Create intent patterns
        patterns = []
        for intent_type in ["device.on", "device.off", "device.set"]:
            pattern = IntentPattern(intent_type=intent_type)
            session.add(pattern)
            patterns.append(pattern)
        await session.commit()
        for pattern in patterns:
            await session.refresh(pattern)

        # Create skill
        skill = await Skill.ensure_exists(session, "remove-intent-skill")

        # Add initial intents
        for pattern in patterns:
            await SkillIntent.upsert(session, skill.id, pattern.id)

        # Verify all three exist
        statement = select(SkillIntent).where(SkillIntent.skill_id == skill.id)
        result = await session.exec(statement)
        assert len(result.all()) == 3

        # Remove one intent (simulating skill no longer supporting it)
        pattern_to_remove = next(p for p in patterns if p.intent_type == "device.set")
        delete_statement = select(SkillIntent).where(
            SkillIntent.skill_id == skill.id, SkillIntent.intent_pattern_id == pattern_to_remove.id
        )
        delete_result = await session.exec(delete_statement)
        to_delete = delete_result.first()
        if to_delete:
            await session.delete(to_delete)
            await session.commit()

        # Verify only two remain
        final_statement = select(SkillIntent).where(SkillIntent.skill_id == skill.id)
        final_result = await session.exec(final_statement)
        final_intents = final_result.all()

        assert len(final_intents) == 2
        remaining_pattern_ids = {si.intent_pattern_id for si in final_intents}
        expected_pattern_ids = {p.id for p in patterns if p.intent_type != "device.set"}
        assert remaining_pattern_ids == expected_pattern_ids
