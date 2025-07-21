"""Pydantic models for structured MQTT communication in Private Assistant ecosystem.

These models define the message formats used for voice command processing,
from initial client requests through intent analysis to skill responses.
"""
import uuid

from pydantic import BaseModel, Field


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


class NumberAnalysisResult(BaseModel):
    """Represents a number extracted from voice command with context.
    
    Used for commands like "set timer for 5 minutes" or "turn on light 3".
    
    Attributes:
        number_token: The extracted numeric value
        previous_token: Word before the number for context (e.g., "for" in "for 5 minutes")
        next_token: Word after the number for context (e.g., "minutes" in "5 minutes")
    """
    number_token: int
    previous_token: str | None = None
    next_token: str | None = None


# AIDEV-NOTE: Core message that all skills receive - contains parsed intent data
class IntentAnalysisResult(BaseModel):
    """Result of intent analysis processing on a voice command.
    
    This is the primary message that skills receive and evaluate for processing.
    Contains the original client request plus extracted linguistic features.
    
    Attributes:
        id: Unique identifier for this analysis result
        client_request: Original voice command and metadata
        numbers: Extracted numbers with context
        nouns: Extracted noun words (e.g., ["lights", "bedroom"])
        verbs: Extracted action words (e.g., ["turn", "set"])
        rooms: Target room names extracted from command (e.g., ["living room"])
        
    Note:
        client_request.room is WHERE the command was spoken
        rooms list is WHAT rooms are targeted by the command
    """
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    client_request: ClientRequest
    numbers: list[NumberAnalysisResult]
    nouns: list[str]
    verbs: list[str]
    rooms: list[str] = []


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
