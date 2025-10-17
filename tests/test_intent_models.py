"""Unit tests for intent classification models."""

import uuid
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from private_assistant_commons import (
    ClassifiedIntent,
    ClientRequest,
    ConfidenceLevel,
    ConfidenceModifier,
    Entity,
    EntityType,
    IntentRequest,
    IntentType,
    RecentAction,
    SkillContext,
)

# Test constants to avoid magic values
TEST_NUMBER_VALUE = 5
TEST_CONFIDENCE_HIGH = 0.95
TEST_CONFIDENCE_MEDIUM = 0.89
TEST_CONFIDENCE_THRESHOLD_CUSTOM = 0.8
TEST_RECENCY_WINDOW = 300
TEST_RECENCY_WINDOW_CUSTOM = 600
TEST_MAX_FOLLOW_UP = 5
TEST_MAX_FOLLOW_UP_CUSTOM = 10
TEST_COMMAND_COUNT = 2
TEST_ENTITY_COUNT = 2
TEST_ALTERNATIVE_COUNT = 2
TEST_ERROR_COUNT_MIN = 2


class TestEntity:
    """Test Entity model."""

    def test_entity_creation_full(self):
        """Test creating an entity with all fields."""
        entity_id = uuid.uuid4()
        linked_id = uuid.uuid4()
        entity = Entity(
            id=entity_id,
            type=EntityType.NUMBER,
            raw_text="five",
            normalized_value=TEST_NUMBER_VALUE,
            confidence=TEST_CONFIDENCE_HIGH,
            metadata={"unit": "minutes"},
            linked_to=[linked_id],
        )
        assert entity.id == entity_id
        assert entity.type == EntityType.NUMBER
        assert entity.raw_text == "five"
        assert entity.normalized_value == TEST_NUMBER_VALUE
        assert entity.confidence == TEST_CONFIDENCE_HIGH
        assert entity.metadata == {"unit": "minutes"}
        assert entity.linked_to == [linked_id]

    def test_entity_validation_error(self):
        """Test validation errors for invalid entity."""
        with pytest.raises(ValidationError) as exc_info:
            Entity(
                type="invalid_type",  # Not a valid EntityType
                raw_text="lights",
                normalized_value="lights",
            )
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("type",)

    def test_device_entity_with_metadata(self):
        """Test DEVICE entity with device_type metadata."""
        # Generic device reference
        generic_device = Entity(
            type=EntityType.DEVICE,
            raw_text="lights",
            normalized_value="light",
            metadata={
                "device_type": "light",
                "is_generic": True,
            },
        )
        assert generic_device.type == EntityType.DEVICE
        assert generic_device.metadata["device_type"] == "light"
        assert generic_device.metadata["is_generic"] is True


class TestClassifiedIntent:
    """Test ClassifiedIntent model."""

    def test_classified_intent_creation_full(self):
        """Test creating a classified intent with all fields."""
        device_entity = Entity(
            type=EntityType.DEVICE,
            raw_text="lights",
            normalized_value="lights",
        )
        room_entity = Entity(
            type=EntityType.ROOM,
            raw_text="bedroom",
            normalized_value="bedroom",
        )
        timestamp = datetime.now()

        intent = ClassifiedIntent(
            intent_type=IntentType.DEVICE_OFF,
            confidence=TEST_CONFIDENCE_MEDIUM,
            entities={
                "devices": [device_entity],
                "rooms": [room_entity],
            },
            alternative_intents=[
                (IntentType.DEVICE_SET, 0.65),
                (IntentType.SCENE_APPLY, 0.45),
            ],
            raw_text="turn off bedroom lights",
            timestamp=timestamp,
        )
        assert intent.intent_type == IntentType.DEVICE_OFF
        assert intent.confidence == TEST_CONFIDENCE_MEDIUM
        assert len(intent.entities) == TEST_ENTITY_COUNT
        assert intent.entities["devices"] == [device_entity]
        assert intent.entities["rooms"] == [room_entity]
        assert len(intent.alternative_intents) == TEST_ALTERNATIVE_COUNT
        assert intent.alternative_intents[0] == (IntentType.DEVICE_SET, 0.65)
        assert intent.alternative_intents[1] == (IntentType.SCENE_APPLY, 0.45)
        assert intent.raw_text == "turn off bedroom lights"
        assert intent.timestamp == timestamp

    def test_classified_intent_validation_error(self):
        """Test validation errors for invalid classified intent."""
        with pytest.raises(ValidationError) as exc_info:
            ClassifiedIntent(
                intent_type="invalid.intent",  # Not a valid IntentType
                confidence="high",  # Not a float
                entities={},
                raw_text="test",
            )
        errors = exc_info.value.errors()
        assert len(errors) >= TEST_ERROR_COUNT_MIN


class TestSkillContext:
    """Test SkillContext model."""

    def test_skill_context_creation_full(self):
        """Test creating a skill context with all fields."""
        context = SkillContext(
            skill_name="media_player",
            command_count_since_last=TEST_COMMAND_COUNT,
            recency_window_seconds=TEST_RECENCY_WINDOW_CUSTOM,
            max_follow_up_commands=TEST_MAX_FOLLOW_UP_CUSTOM,
        )
        assert context.skill_name == "media_player"
        assert context.command_count_since_last == TEST_COMMAND_COUNT
        assert context.recency_window_seconds == TEST_RECENCY_WINDOW_CUSTOM
        assert context.max_follow_up_commands == TEST_MAX_FOLLOW_UP_CUSTOM

    def test_has_recent_activity(self):
        """Test checking for recent activity."""
        context = SkillContext(skill_name="test_skill")

        # No activity initially
        assert context.has_recent_activity() is False

        # Add an action
        context.add_action("turn_on", {"device": "lights"})
        assert context.has_recent_activity() is True

    def test_find_recent_action(self):
        """Test finding specific actions in history."""
        context = SkillContext(
            skill_name="test_skill",
            recency_window_seconds=300,
        )

        # Add multiple actions
        context.add_action("turn_on", {"device": "lights"})
        context.add_action("turn_off", {"device": "fan"})
        context.add_action("turn_on", {"device": "tv"})

        # Find most recent turn_on
        action = context.find_recent_action("turn_on")
        assert action is not None
        assert action.action == "turn_on"
        assert action.entities == {"device": "tv"}

        # Find turn_off
        action = context.find_recent_action("turn_off")
        assert action is not None
        assert action.entities == {"device": "fan"}

        # Non-existent action
        action = context.find_recent_action("nonexistent")
        assert action is None

    def test_has_recent_intent(self):
        """Test checking for recent intent types."""
        context = SkillContext(skill_name="test_skill")

        # Add action matching an intent type value
        context.add_action("device.on", {"device": "lights"})

        # Check using IntentType enum
        assert context.has_recent_intent(IntentType.DEVICE_ON) is True
        assert context.has_recent_intent(IntentType.DEVICE_OFF) is False

        # Check using string
        assert context.has_recent_intent("device.on") is True
        assert context.has_recent_intent("device.off") is False

    def test_cleanup_expired_actions(self):
        """Test automatic cleanup of expired actions."""
        # Recent activity - should be kept after cleanup
        context = SkillContext(
            skill_name="test_skill",
            recency_window_seconds=300,
        )
        context.recent_actions.append(
            RecentAction(action="test", executed_at=datetime.now() - timedelta(seconds=100), entities={})
        )
        context._cleanup_expired_actions()
        assert len(context.recent_actions) == 1

        # Expired - old activity should be removed after cleanup
        context.recent_actions.append(
            RecentAction(action="old_test", executed_at=datetime.now() - timedelta(seconds=400), entities={})
        )
        context._cleanup_expired_actions()
        # Only the recent action (100 seconds old) should remain
        assert len(context.recent_actions) == 1
        assert context.recent_actions[0].action == "test"

    def test_find_recent_action_with_custom_window(self):
        """Test finding actions within a custom time window."""
        context = SkillContext(
            skill_name="test_skill",
            recency_window_seconds=300,
        )

        # Add an action from 150 seconds ago
        context.recent_actions.append(
            RecentAction(action="test", executed_at=datetime.now() - timedelta(seconds=150), entities={})
        )

        # Should find with default window (300s)
        assert context.find_recent_action("test") is not None

        # Should NOT find with 100s window
        assert context.find_recent_action("test", within_seconds=100) is None

        # Should find with 200s window
        assert context.find_recent_action("test", within_seconds=200) is not None


class TestIntentRequest:
    """Test IntentRequest model."""

    def test_intent_request_creation(self):
        """Test creating an intent request with classified intent and client request."""
        client_request = ClientRequest(
            id=uuid.uuid4(),
            text="turn on bedroom lights",
            room="living_room",
            output_topic="home/living_room/response",
        )

        classified_intent = ClassifiedIntent(
            intent_type=IntentType.DEVICE_ON,
            confidence=TEST_CONFIDENCE_HIGH,
            entities={
                "devices": [Entity(type=EntityType.DEVICE, raw_text="lights", normalized_value="lights")],
                "rooms": [Entity(type=EntityType.ROOM, raw_text="bedroom", normalized_value="bedroom")],
            },
            raw_text="turn on bedroom lights",
        )

        intent_request = IntentRequest(
            classified_intent=classified_intent,
            client_request=client_request,
        )

        assert intent_request.classified_intent == classified_intent
        assert intent_request.client_request == client_request
        assert isinstance(intent_request.id, uuid.UUID)

    def test_intent_request_validation_error(self):
        """Test validation errors for invalid intent request."""
        with pytest.raises(ValidationError) as exc_info:
            IntentRequest(
                classified_intent="not_an_intent",  # Should be ClassifiedIntent
                client_request="not_a_request",  # Should be ClientRequest
            )
        errors = exc_info.value.errors()
        assert len(errors) >= TEST_ERROR_COUNT_MIN


class TestConfidenceLevel:
    """Test ConfidenceLevel enum."""

    def test_confidence_level_ordering(self):
        """Test confidence levels can be compared."""
        assert ConfidenceLevel.MULTIWORD_WITH_CONTEXT >= ConfidenceLevel.KEYWORD_CONTEXT
        assert ConfidenceLevel.KEYWORD_ONLY > ConfidenceLevel.CONTEXT_ONLY


class TestConfidenceModifier:
    """Test ConfidenceModifier model."""

    def test_confidence_modifier_creation_full(self):
        """Test creating a confidence modifier with all fields."""
        modifier = ConfidenceModifier(
            trigger_intent=IntentType.MEDIA_PLAY,
            lowers_threshold_for=IntentType.MEDIA_STOP,
            reduced_threshold=ConfidenceLevel.KEYWORD_ONLY,
            time_window_seconds=600,
        )
        assert modifier.trigger_intent == IntentType.MEDIA_PLAY
        assert modifier.lowers_threshold_for == IntentType.MEDIA_STOP
        assert modifier.reduced_threshold == 0.5  # noqa: PLR2004
        assert modifier.time_window_seconds == 600  # noqa: PLR2004

    def test_confidence_modifier_validation_error(self):
        """Test validation errors for invalid confidence modifier."""
        with pytest.raises(ValidationError) as exc_info:
            ConfidenceModifier(
                trigger_intent="invalid_intent",  # Not a valid IntentType
                lowers_threshold_for=IntentType.DEVICE_OFF,
                reduced_threshold=0.5,
            )
        errors = exc_info.value.errors()
        assert len(errors) >= 1
