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
    DEVICE_TYPE = "device_type"
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


# TODO - consider using dataclass for SkillContext if no validation needed
# AIDEV-NOTE: Stateful context tracking for skill-side decision making
class SkillContext(BaseModel):
    """Context tracking for skill-side decision making.

    Manages recency-based confidence thresholds and context expiry
    to enable intelligent follow-up command handling.
    """

    skill_name: str
    # TODO - consider tracking multiple recent actions for more complex context
    last_action: str | None = None
    last_executed_at: datetime | None = None
    last_entities: dict[str, Any] = Field(default_factory=dict)
    command_count_since_last: int = 0

    # Confidence thresholds
    confidence_threshold_default: float = 0.7
    confidence_threshold_recent: float = 0.4

    # Expiry settings
    recency_window_seconds: int = 300  # 5 minutes
    max_follow_up_commands: int = 5

    def should_handle(self, intent: ClassifiedIntent) -> bool:
        """Determine if skill should handle based on confidence and context.

        Args:
            intent: The classified intent to evaluate

        Returns:
            True if the skill should handle this intent, False otherwise
        """
        # If no recent activity or context has expired, use default threshold
        if self.last_executed_at is None or self.should_expire():
            return intent.confidence >= self.confidence_threshold_default

        # Recently active - accept lower confidence
        return intent.confidence >= self.confidence_threshold_recent

    def should_expire(self) -> bool:
        """Check if context should expire.

        Returns:
            True if the context has expired and should be reset
        """
        if self.last_executed_at:
            time_since = datetime.now() - self.last_executed_at
            if time_since.total_seconds() > self.recency_window_seconds:
                return True

        return self.command_count_since_last >= self.max_follow_up_commands


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
