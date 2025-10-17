"""Message models for client requests and skill responses.

This module defines the standard message formats used for communication
between voice clients, the intent engine, and skills.
"""

import uuid

from pydantic import BaseModel


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
