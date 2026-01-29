"""Unit tests for database models."""

import uuid

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from private_assistant_commons.database import (
    IntentPattern,
    IntentPatternKeyword,
    Skill,
    SkillIntent,
)


@pytest_asyncio.fixture
async def engine():
    """Create an in-memory SQLite database engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Create intent pattern and skill tables (skip models with ARRAY types)
    async with engine.begin() as conn:
        # Get table objects for the intent pattern and skill models
        tables = [
            IntentPattern.__table__,
            IntentPatternKeyword.__table__,
            Skill.__table__,
            SkillIntent.__table__,
        ]
        # Create only these specific tables
        await conn.run_sync(lambda sync_conn: IntentPattern.metadata.create_all(sync_conn, tables=tables))

    yield engine

    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine: AsyncEngine):
    """Create a database session for testing."""
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session


class TestIntentPattern:
    """Test IntentPattern model."""

    async def test_intent_pattern_creation_minimal(self, session: AsyncSession):
        """Test creating an intent pattern with minimal required fields."""
        pattern = IntentPattern(intent_type="device.on")
        session.add(pattern)
        await session.commit()
        await session.refresh(pattern)

        assert pattern.id is not None
        assert isinstance(pattern.id, uuid.UUID)
        assert pattern.intent_type == "device.on"
        assert pattern.enabled is True
        assert pattern.priority == 0
        assert pattern.description is None
        assert pattern.created_at is not None
        assert pattern.updated_at is not None

    async def test_intent_pattern_creation_full(self, session: AsyncSession):
        """Test creating an intent pattern with all fields."""
        pattern_id = uuid.uuid4()
        pattern = IntentPattern(
            id=pattern_id,
            intent_type="device.off",
            enabled=False,
            priority=10,
            description="Turn off devices",
        )
        session.add(pattern)
        await session.commit()
        await session.refresh(pattern)

        assert pattern.id == pattern_id
        assert pattern.intent_type == "device.off"
        assert pattern.enabled is False
        assert pattern.priority == 10
        assert pattern.description == "Turn off devices"

    async def test_intent_pattern_with_relationships(self, session: AsyncSession):
        """Test intent pattern with keywords relationships."""
        pattern = IntentPattern(intent_type="device.on", description="Turn on devices")
        session.add(pattern)
        await session.commit()
        await session.refresh(pattern)

        # Add keywords
        keyword1 = IntentPatternKeyword(pattern_id=pattern.id, keyword="turn on", keyword_type="primary")
        keyword2 = IntentPatternKeyword(pattern_id=pattern.id, keyword="switch on", keyword_type="primary")
        keyword3 = IntentPatternKeyword(pattern_id=pattern.id, keyword="off", keyword_type="negative")
        session.add_all([keyword1, keyword2, keyword3])

        await session.commit()

        # Reload pattern with relationships
        result = await session.exec(
            select(IntentPattern).where(IntentPattern.id == pattern.id).options(selectinload(IntentPattern.keywords))  # type: ignore[arg-type]
        )
        pattern = result.one()

        # Verify relationships
        assert len(pattern.keywords) == 3

        # Verify keyword types
        primary_keywords = [kw for kw in pattern.keywords if kw.keyword_type == "primary"]
        negative_keywords = [kw for kw in pattern.keywords if kw.keyword_type == "negative"]
        assert len(primary_keywords) == 2
        assert len(negative_keywords) == 1

    async def test_intent_pattern_cascade_delete(self, session: AsyncSession):
        """Test that deleting a pattern cascades to keywords."""
        pattern = IntentPattern(intent_type="device.on")
        session.add(pattern)
        await session.commit()
        await session.refresh(pattern)

        # Add keywords
        keyword = IntentPatternKeyword(pattern_id=pattern.id, keyword="turn on")
        session.add(keyword)
        await session.commit()

        pattern_id = pattern.id

        # Verify keyword exists
        kw_result = await session.exec(
            select(IntentPatternKeyword).where(IntentPatternKeyword.pattern_id == pattern_id)
        )
        assert len(list(kw_result.all())) == 1

        # Delete the pattern
        await session.delete(pattern)
        await session.commit()

        # Verify keywords are deleted
        kw_result = await session.exec(
            select(IntentPatternKeyword).where(IntentPatternKeyword.pattern_id == pattern_id)
        )
        assert len(list(kw_result.all())) == 0

    async def test_intent_pattern_query_by_enabled(self, session: AsyncSession):
        """Test querying patterns by enabled status."""
        # Create enabled and disabled patterns
        enabled_pattern = IntentPattern(intent_type="device.on", enabled=True)
        disabled_pattern = IntentPattern(intent_type="device.off", enabled=False)
        session.add_all([enabled_pattern, disabled_pattern])
        await session.commit()

        # Query enabled patterns
        result = await session.exec(select(IntentPattern).where(IntentPattern.enabled))
        enabled_patterns = list(result.all())
        assert len(enabled_patterns) == 1
        assert enabled_patterns[0].intent_type == "device.on"

        # Query disabled patterns
        result = await session.exec(select(IntentPattern).where(IntentPattern.enabled.is_(False)))  # type: ignore[attr-defined]
        disabled_patterns = list(result.all())
        assert len(disabled_patterns) == 1
        assert disabled_patterns[0].intent_type == "device.off"


class TestIntentPatternKeyword:
    """Test IntentPatternKeyword model."""

    async def test_keyword_creation_minimal(self, session: AsyncSession):
        """Test creating a keyword with minimal required fields."""
        pattern = IntentPattern(intent_type="device.on")
        session.add(pattern)
        await session.commit()
        await session.refresh(pattern)

        keyword = IntentPatternKeyword(pattern_id=pattern.id, keyword="turn on")
        session.add(keyword)
        await session.commit()
        await session.refresh(keyword)

        assert keyword.id is not None
        assert isinstance(keyword.id, uuid.UUID)
        assert keyword.pattern_id == pattern.id
        assert keyword.keyword == "turn on"
        assert keyword.keyword_type == "primary"
        assert keyword.is_regex is False
        assert keyword.weight == 1.0
        assert keyword.created_at is not None

    async def test_keyword_creation_full(self, session: AsyncSession):
        """Test creating a keyword with all fields."""
        pattern = IntentPattern(intent_type="device.off")
        session.add(pattern)
        await session.commit()
        await session.refresh(pattern)

        keyword_id = uuid.uuid4()
        keyword = IntentPatternKeyword(
            id=keyword_id,
            pattern_id=pattern.id,
            keyword="switch off",
            keyword_type="negative",
            weight=2.0,
        )
        session.add(keyword)
        await session.commit()
        await session.refresh(keyword)

        assert keyword.id == keyword_id
        assert keyword.keyword == "switch off"
        assert keyword.keyword_type == "negative"
        assert keyword.weight == 2.0

    async def test_keyword_relationship(self, session: AsyncSession):
        """Test keyword relationship with pattern."""
        pattern = IntentPattern(intent_type="device.on")
        session.add(pattern)
        await session.commit()
        await session.refresh(pattern)

        keyword = IntentPatternKeyword(pattern_id=pattern.id, keyword="turn on")
        session.add(keyword)
        await session.commit()
        await session.refresh(keyword)

        # Access pattern from keyword
        assert keyword.pattern.id == pattern.id
        assert keyword.pattern.intent_type == "device.on"

    async def test_query_keywords_by_type(self, session: AsyncSession):
        """Test querying keywords by type."""
        pattern = IntentPattern(intent_type="device.on")
        session.add(pattern)
        await session.commit()
        await session.refresh(pattern)

        # Add keywords of different types
        primary_kw = IntentPatternKeyword(pattern_id=pattern.id, keyword="turn on", keyword_type="primary")
        negative_kw = IntentPatternKeyword(pattern_id=pattern.id, keyword="off", keyword_type="negative")
        session.add_all([primary_kw, negative_kw])
        await session.commit()

        # Query primary keywords
        result = await session.exec(select(IntentPatternKeyword).where(IntentPatternKeyword.keyword_type == "primary"))
        primary_keywords = list(result.all())
        assert len(primary_keywords) == 1
        assert primary_keywords[0].keyword == "turn on"

        # Query negative keywords
        result = await session.exec(select(IntentPatternKeyword).where(IntentPatternKeyword.keyword_type == "negative"))
        negative_keywords = list(result.all())
        assert len(negative_keywords) == 1
        assert negative_keywords[0].keyword == "off"

    async def test_keyword_with_regex(self, session: AsyncSession):
        """Test creating keywords with regex patterns."""
        pattern = IntentPattern(intent_type="device.on")
        session.add(pattern)
        await session.commit()
        await session.refresh(pattern)

        # Add literal keyword
        literal_kw = IntentPatternKeyword(
            pattern_id=pattern.id, keyword="turn on", keyword_type="primary", is_regex=False
        )

        # Add regex keyword
        regex_kw = IntentPatternKeyword(
            pattern_id=pattern.id, keyword=r"switch (on|off)", keyword_type="primary", is_regex=True
        )

        session.add_all([literal_kw, regex_kw])
        await session.commit()

        # Query all keywords
        result = await session.exec(select(IntentPatternKeyword).where(IntentPatternKeyword.pattern_id == pattern.id))
        keywords = list(result.all())
        assert len(keywords) == 2

        # Verify is_regex flags
        literal_keywords = [kw for kw in keywords if not kw.is_regex]
        regex_keywords = [kw for kw in keywords if kw.is_regex]

        assert len(literal_keywords) == 1
        assert literal_keywords[0].keyword == "turn on"

        assert len(regex_keywords) == 1
        assert regex_keywords[0].keyword == r"switch (on|off)"


class TestIntentPatternUsageExample:
    """Test the example usage pattern from the task description."""

    async def test_load_patterns_from_database(self, session: AsyncSession):
        """Test loading patterns as shown in the example usage."""
        # Create patterns with keywords
        pattern1 = IntentPattern(intent_type="device.on", enabled=True, priority=10, description="Turn on devices")
        pattern2 = IntentPattern(intent_type="device.off", enabled=True, priority=5, description="Turn off devices")
        pattern3 = IntentPattern(intent_type="device.set", enabled=False, priority=0, description="Set device state")
        session.add_all([pattern1, pattern2, pattern3])
        await session.commit()
        await session.refresh(pattern1)
        await session.refresh(pattern2)
        await session.refresh(pattern3)

        # Add keywords to pattern1
        kw1 = IntentPatternKeyword(pattern_id=pattern1.id, keyword="turn on", keyword_type="primary", is_regex=False)
        kw2 = IntentPatternKeyword(pattern_id=pattern1.id, keyword="switch on", keyword_type="primary", is_regex=False)
        kw3 = IntentPatternKeyword(pattern_id=pattern1.id, keyword="off", keyword_type="negative", is_regex=False)
        session.add_all([kw1, kw2, kw3])

        await session.commit()

        # Load patterns from database (example usage)
        result = await session.exec(
            select(IntentPattern).where(IntentPattern.enabled).options(selectinload(IntentPattern.keywords))  # type: ignore[arg-type]
        )
        db_patterns = list(result.all())

        # Verify we got only enabled patterns
        assert len(db_patterns) == 2
        assert all(p.enabled for p in db_patterns)

        # Access relationships
        for db_pattern in db_patterns:
            if db_pattern.intent_type == "device.on":
                primary_keywords = [kw.keyword for kw in db_pattern.keywords if kw.keyword_type == "primary"]
                negative_keywords = [kw.keyword for kw in db_pattern.keywords if kw.keyword_type == "negative"]

                assert set(primary_keywords) == {"turn on", "switch on"}
                assert negative_keywords == ["off"]
