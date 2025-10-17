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

from private_assistant_commons.messages import ClientRequest  # noqa: TC001


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


class ConfidenceLevel(float, Enum):
    """Confidence levels used by the intent engine for classification.

    These values represent the confidence score assigned by the intent engine
    based on the matching pattern characteristics (keywords, context hints, etc.).
    Skills use these thresholds when evaluating whether to handle an intent.
    """

    MULTIWORD_WITH_CONTEXT = 1.0  # Multi-word keyword + context hints (e.g., "turn on" + "lights")
    MULTIWORD_ONLY = 0.9  # Multi-word keyword without context (e.g., "switch off" alone)
    KEYWORD_MULTI_CONTEXT = 0.9  # Single keyword + multiple context hints (e.g., "set" + "temperature" + "degrees")
    KEYWORD_CONTEXT = 0.8  # Single keyword + single context hint (e.g., "stop" + "music")
    ALL_KEYWORDS = 0.8  # All pattern keywords present
    KEYWORD_ONLY = 0.5  # Single keyword match without context
    CONTEXT_ONLY = 0.3  # Context hints without keywords


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
