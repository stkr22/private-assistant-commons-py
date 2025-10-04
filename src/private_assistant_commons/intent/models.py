"""Intent classification data models for the Private Assistant ecosystem.

These models define the structured intent classification system
for voice command processing and skill context management.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# AIDEV-NOTE: Comprehensive intent types covering all command categories
class IntentType(str, Enum):
    """Enumeration of all supported intent types in the system."""

    # Device Control
    DEVICE_ON = "device.on"
    DEVICE_OFF = "device.off"
    DEVICE_SET = "device.set"
    DEVICE_OPEN = "device.open"
    DEVICE_CLOSE = "device.close"

    # Media Control
    MEDIA_PLAY = "media.play"
    MEDIA_STOP = "media.stop"
    MEDIA_NEXT = "media.next"
    MEDIA_VOLUME_UP = "media.volume_up"
    MEDIA_VOLUME_DOWN = "media.volume_down"
    MEDIA_VOLUME_SET = "media.volume_set"

    # Queries
    QUERY_STATUS = "query.status"
    QUERY_LIST = "query.list"
    QUERY_TIME = "query.time"

    # Scene/Automation
    SCENE_APPLY = "scene.apply"

    # Time/Scheduling
    SCHEDULE_SET = "schedule.set"
    SCHEDULE_CANCEL = "schedule.cancel"

    # System
    SYSTEM_HELP = "system.help"
    SYSTEM_REFRESH = "system.refresh"


class EntityType(str, Enum):
    """Types of entities that can be extracted from voice commands."""

    DEVICE = "device"
    ROOM = "room"
    NUMBER = "number"
    DURATION = "duration"
    TIME = "time"
    MEDIA_ID = "media_id"
    SCENE = "scene"
    MODIFIER = "modifier"


# AIDEV-NOTE: Entity with normalization and linking capabilities
class Entity(BaseModel):
    """Represents an entity extracted from a voice command.

    Entities are normalized components of a voice command with
    type information, confidence scoring, and relationship tracking.

    For DEVICE entities, the metadata should include:
    - device_type: The type/category of the device (e.g., "light", "media_service")
    - is_generic: Whether this is a generic reference (e.g., "lights") or specific (e.g., "bedroom lamp")
    - Additional context like "room" for location-specific devices
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    type: EntityType
    raw_text: str
    normalized_value: Any
    confidence: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    linked_to: list[uuid.UUID] = Field(default_factory=list)


class ClassifiedIntent(BaseModel):
    """Result of intent classification on a voice command.

    Contains the classified intent type with confidence scoring,
    extracted entities, and alternative interpretations.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    intent_type: IntentType
    confidence: float
    entities: dict[str, list[Entity]]
    alternative_intents: list[tuple[IntentType, float]] = Field(default_factory=list)
    raw_text: str
    timestamp: datetime = Field(default_factory=datetime.now)


# AIDEV-NOTE: Wrapper that combines classified intent with client request for skill processing
class IntentRequest(BaseModel):
    """Combined intent classification result and client request for skill processing.

    This model bridges the intent engine output with skill input requirements,
    providing both the classified intent and the original client request metadata.
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    classified_intent: ClassifiedIntent
    client_request: ClientRequest


# AIDEV-NOTE: Stateful context tracking for skill-side decision making
class RecentAction(BaseModel):
    """Represents a single recent action in the skill context history."""

    action: str
    executed_at: datetime
    entities: dict[str, Any] = Field(default_factory=dict)


class SkillContext(BaseModel):
    """Context tracking for skill-side decision making.

    Provides utilities for tracking recent actions and querying context state.
    Skills should implement their own logic for determining whether to handle
    intents based on this context.
    """

    skill_name: str
    recent_actions: list[RecentAction] = Field(default_factory=list)
    command_count_since_last: int = 0
    max_recent_actions: int = 10

    # Expiry settings
    recency_window_seconds: int = 300  # 5 minutes
    max_follow_up_commands: int = 5

    def has_recent_activity(self) -> bool:
        """Check if there are any valid recent actions.

        Returns:
            True if there are recent actions within the recency window
        """
        self._cleanup_expired_actions()
        return len(self.recent_actions) > 0

    def find_recent_action(self, action: str, within_seconds: int | None = None) -> RecentAction | None:
        """Find a specific action in recent history.

        Args:
            action: The action name to search for
            within_seconds: Optional time window to search within (defaults to recency_window_seconds)

        Returns:
            The most recent matching action, or None if not found
        """
        self._cleanup_expired_actions()

        if not self.recent_actions:
            return None

        time_window = within_seconds if within_seconds is not None else self.recency_window_seconds
        cutoff_time = datetime.now().timestamp() - time_window

        # Search backwards through recent actions
        for recent_action in reversed(self.recent_actions):
            if recent_action.action == action and recent_action.executed_at.timestamp() > cutoff_time:
                return recent_action

        return None

    def has_recent_intent(self, intent_type: IntentType | str) -> bool:
        """Check if a specific intent type was recently handled.

        Args:
            intent_type: The intent type to search for

        Returns:
            True if this intent type was recently handled
        """
        intent_str = intent_type.value if isinstance(intent_type, IntentType) else intent_type
        return self.find_recent_action(intent_str) is not None

    def _cleanup_expired_actions(self) -> None:
        """Remove expired actions from the history based on recency window."""
        if not self.recent_actions:
            return

        now = datetime.now()
        cutoff_time = now.timestamp() - self.recency_window_seconds

        # Keep only actions within the recency window
        self.recent_actions = [action for action in self.recent_actions if action.executed_at.timestamp() > cutoff_time]

    def add_action(self, action: str, entities: dict[str, Any] | None = None) -> None:
        """Add a new action to the recent actions history.

        Args:
            action: Name of the action executed
            entities: Optional entities associated with the action
        """
        recent_action = RecentAction(
            action=action,
            executed_at=datetime.now(),
            entities=entities or {},
        )
        self.recent_actions.append(recent_action)

        # Trim to max size
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions = self.recent_actions[-self.max_recent_actions :]

    def get_last_action(self) -> RecentAction | None:
        """Get the most recent action.

        Returns:
            The most recent action, or None if no actions exist
        """
        return self.recent_actions[-1] if self.recent_actions else None

    def get_recent_entities(self, entity_type: str | None = None) -> dict[str, Any]:
        """Get entities from recent actions.

        Args:
            entity_type: Optional filter for specific entity type

        Returns:
            Dictionary of entities from the most recent action, or all recent entities
        """
        if not self.recent_actions:
            return {}

        if entity_type:
            # Search backwards through recent actions for this entity type
            for action in reversed(self.recent_actions):
                if entity_type in action.entities:
                    return {entity_type: action.entities[entity_type]}
            return {}

        # Return all entities from the most recent action
        return self.recent_actions[-1].entities


# AIDEV-NOTE: Original voice command from user with routing information
class ClientRequest(BaseModel):
    """Represents the original voice command from a user.

    Attributes:
        id: Unique identifier for tracking the request through the pipeline
        text: Raw voice command text (e.g., "turn off the lights in the living room")
        room: Location where command was spoken (e.g., "kitchen")
        output_topic: MQTT topic where responses should be sent for this specific user/device
    """

    id: uuid.UUID
    text: str
    room: str
    output_topic: str


class Alert(BaseModel):
    """Configuration for audio feedback in skill responses.

    Used to control when and what sounds are played to provide
    audio cues to users through the voice bridge system.

    Attributes:
        play_before: Play sound before speaking the response text
        play_after: Play sound after speaking the response text
        sound: Sound file name to play (configured in voice bridge)
    """

    play_before: bool = False
    play_after: bool = False
    sound: str = "default"


# AIDEV-NOTE: Standard response format sent by all skills
class Response(BaseModel):
    """Standard response message sent by skills to users.

    Published to either specific client output topics or broadcast topic
    depending on whether response is targeted or system-wide.

    Attributes:
        text: Response text to be spoken/displayed to user
        alert: Optional audio alert configuration for enhanced feedback
    """

    text: str
    alert: Alert | None = None
