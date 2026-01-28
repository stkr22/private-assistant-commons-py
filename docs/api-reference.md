# Private Assistant Commons - API Reference

## Core Classes

### BaseSkill

The abstract base class that all skills must inherit from.

```python
class BaseSkill(ABC):
    def __init__(
        self,
        config_obj: SkillConfig,
        mqtt_client: aiomqtt.Client,
        task_group: asyncio.TaskGroup,
        certainty_threshold: float = 0.8,
        logger: logging.Logger | None = None,
    ) -> None
```

#### Constructor Parameters
- **config_obj** (`SkillConfig`): Configuration for MQTT topics and connection settings
- **mqtt_client** (`aiomqtt.Client`): Connected MQTT client for message publishing/subscribing
- **task_group** (`asyncio.TaskGroup`): TaskGroup for managing concurrent operations
- **certainty_threshold** (`float`): Minimum confidence score to process requests (0.0-1.0)
- **logger** (`logging.Logger | None`): Optional custom logger

#### Abstract Methods

##### calculate_certainty
```python
@abstractmethod
async def calculate_certainty(self, intent_request: IntentRequest) -> float:
```
Calculate confidence score for handling this request. Must return a value between 0.0-1.0.

##### process_request
```python
@abstractmethod
async def process_request(self, intent_request: IntentRequest) -> None:
```
Process a request that exceeded the certainty threshold. Contains the main skill logic.

##### skill_preparations
```python
@abstractmethod
async def skill_preparations(self) -> None:
```
Perform skill-specific initialization after MQTT setup. Called once during startup.

#### Public Methods

##### setup_mqtt_subscriptions
```python
async def setup_mqtt_subscriptions(self) -> None:
```
Set up MQTT topic subscriptions. Subscribes to the intent analysis result topic.

##### send_response
```python
async def send_response(
    self,
    response_text: str,
    client_request: ClientRequest,
    alert: Alert | None = None,
) -> None:
```
Send a response to a specific client request using the client's output topic.

**Parameters:**
- **response_text** (`str`): Text response to send
- **client_request** (`ClientRequest`): Original request containing output topic
- **alert** (`Alert | None`): Optional audio alert configuration

##### broadcast_response
```python
async def broadcast_response(
    self,
    response_text: str,
    alert: Alert | None = None,
) -> None:
```
Broadcast a response to all connected clients using the broadcast topic.

##### publish_with_alert
```python
async def publish_with_alert(
    self,
    response_text: str,
    client_request: ClientRequest | None = None,
    broadcast: bool = False,
    alert: Alert | None = None,
) -> None:
```
Flexible publishing method that can send targeted or broadcast responses.

##### add_task
```python
def add_task(self, coro) -> asyncio.Task:
```
Add a coroutine as a new task to the skill's task group for concurrent execution.

#### Properties
- **config_obj** (`SkillConfig`): Skill configuration
- **mqtt_client** (`aiomqtt.Client`): MQTT client instance
- **task_group** (`asyncio.TaskGroup`): Task group for concurrent operations
- **logger** (`logging.Logger`): Logger instance
- **certainty_threshold** (`float`): Minimum certainty threshold
- **default_alert** (`Alert`): Default alert configuration
- **intent_analysis_results** (`BoundedDict`): LRU cache for intent analysis results with automatic eviction to prevent memory leaks

## Message Models

### ClientRequest

Represents the original voice command from a user.

```python
class ClientRequest(BaseModel):
    id: uuid.UUID
    text: str
    room: str
    output_topic: str
```

**Attributes:**
- **id**: Unique identifier for tracking the request
- **text**: Raw voice command text
- **room**: Location where command was spoken
- **output_topic**: MQTT topic for responses to this user/device

### IntentType

Enumeration of all supported intent types in the system.

```python
class IntentType(str, Enum):
    DEVICE_ON = "device.on"
    DEVICE_OFF = "device.off"
    DEVICE_SET = "device.set"
    DEVICE_OPEN = "device.open"
    DEVICE_CLOSE = "device.close"
    MEDIA_PLAY = "media.play"
    MEDIA_STOP = "media.stop"
    MEDIA_NEXT = "media.next"
    QUERY_STATUS = "query.status"
    QUERY_LIST = "query.list"
    QUERY_TIME = "query.time"
    SCENE_APPLY = "scene.apply"
    SCHEDULE_SET = "schedule.set"
    SCHEDULE_CANCEL = "schedule.cancel"
    SYSTEM_HELP = "system.help"
    SYSTEM_REFRESH = "system.refresh"
```

### EntityType

Types of entities that can be extracted from voice commands.

```python
class EntityType(str, Enum):
    DEVICE = "device"
    ROOM = "room"
    NUMBER = "number"
    DURATION = "duration"
    TIME = "time"
    MEDIA_ID = "media_id"
    SCENE = "scene"
    MODIFIER = "modifier"
```

### Entity

Represents an entity extracted from a voice command.

```python
class Entity(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    type: EntityType
    raw_text: str
    normalized_value: Any
    confidence: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)
    linked_to: list[uuid.UUID] = Field(default_factory=list)
```

**Attributes:**
- **id**: Unique identifier for this entity
- **type**: Type of entity (device, room, etc.)
- **raw_text**: Original text that was extracted
- **normalized_value**: Normalized/processed value (e.g., "five" → 5)
- **confidence**: Confidence score for this entity
- **metadata**: Additional entity metadata (e.g., units, device_type)
- **linked_to**: IDs of related entities

**Device Entity Metadata:**
For `DEVICE` entities, the metadata dictionary should include:
- **device_type**: The type/category of the device (e.g., "light", "media_service")
- **is_generic**: Whether this is a generic reference (e.g., "lights") or specific (e.g., "bedroom lamp")
- Additional context like "room" for location-specific devices

**Example:**
```python
# Generic device reference
Entity(
    type=EntityType.DEVICE,
    raw_text="lights",
    normalized_value="light",
    metadata={
        "device_type": "light",
        "is_generic": True
    }
)

# Specific device with room context
Entity(
    type=EntityType.DEVICE,
    raw_text="bedroom lamp",
    normalized_value="bedroom_lamp",
    metadata={
        "device_type": "light",
        "is_generic": False,
        "room": "bedroom"
    }
)

# Service/Platform as device
Entity(
    type=EntityType.DEVICE,
    raw_text="spotify",
    normalized_value="spotify",
    metadata={
        "device_type": "media_service",
        "is_generic": False
    }
)
```

### ClassifiedIntent

Result of intent classification on a voice command.

```python
class ClassifiedIntent(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    intent_type: IntentType
    confidence: float
    entities: dict[str, list[Entity]]
    alternative_intents: list[tuple[IntentType, float]] = Field(default_factory=list)
    raw_text: str
    timestamp: datetime = Field(default_factory=datetime.now)
```

**Attributes:**
- **id**: Unique identifier for this classification
- **intent_type**: Classified intent type
- **confidence**: Confidence score for the classification
- **entities**: Extracted entities grouped by type
- **alternative_intents**: Alternative intent types with confidence scores
- **raw_text**: Original voice command text
- **timestamp**: When the classification was performed

### IntentRequest

Combined intent classification result and client request for skill processing.

```python
class IntentRequest(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    classified_intent: ClassifiedIntent
    client_request: ClientRequest
```

**Attributes:**
- **id**: Unique identifier for this request
- **classified_intent**: The classified intent with entities
- **client_request**: Original client request with routing information

### SkillContext

Context tracking for skill-side decision making.

```python
class SkillContext(BaseModel):
    skill_name: str
    last_action: str | None = None
    last_executed_at: datetime | None = None
    last_entities: dict[str, Any] = Field(default_factory=dict)
    command_count_since_last: int = 0
    confidence_threshold_default: float = 0.7
    confidence_threshold_recent: float = 0.4
    recency_window_seconds: int = 300
    max_follow_up_commands: int = 5
```

**Methods:**
- **should_handle(intent: ClassifiedIntent) -> bool**: Determine if skill should handle based on confidence and context
- **should_expire() -> bool**: Check if context should expire

### Alert

Configuration for audio feedback in skill responses.

```python
class Alert(BaseModel):
    play_before: bool = False
    play_after: bool = False
    sound: str = "default"
```

**Attributes:**
- **play_before**: Play sound before speaking the response text
- **play_after**: Play sound after speaking the response text
- **sound**: Sound file name (configured in voice bridge)

### Response

Standard response message sent by skills to users.

```python
class Response(BaseModel):
    text: str
    alert: Alert | None = None
```

**Attributes:**
- **text**: Response text to be spoken/displayed
- **alert**: Optional audio alert configuration

## Configuration Classes

### MqttConfig

MQTT broker connection configuration. Loads from environment variables with `MQTT_` prefix.

```python
class MqttConfig(BaseSettings):
    host: str  # Required - MQTT broker hostname
    port: int  # Required - MQTT broker port
    username: str | None = None  # Optional - Authentication username
    password: str | None = None  # Optional - Authentication password
```

**Environment Variables:**
- **MQTT_HOST** (required): MQTT broker hostname
- **MQTT_PORT** (required): MQTT broker port
- **MQTT_USERNAME** (optional): Authentication username
- **MQTT_PASSWORD** (optional): Authentication password

### SkillConfig

Core configuration for Private Assistant skills.

```python
class SkillConfig(BaseSettings):
    client_id: str = "default_skill"
    base_topic: str = "assistant"
    intent_analysis_result_topic: str = "assistant/intent_engine/result"
    broadcast_topic: str = "assistant/broadcast"
    intent_cache_size: int = 1000
```

**Attributes:**
- **client_id**: Unique identifier for this skill
- **base_topic**: Base MQTT topic prefix
- **intent_analysis_result_topic**: Topic for receiving intent analysis results
- **broadcast_topic**: Topic for broadcasting responses to all clients
- **intent_cache_size**: Maximum number of intent analysis results to cache (default: 1000)

**Properties:**
- **feedback_topic** (`str`): Generated topic for skill feedback: `{base_topic}/{client_id}/feedback`

### PostgresConfig

PostgreSQL database configuration for skills that need persistence.

```python
class PostgresConfig(BaseModel):
    user: str = "postgres"
    password: str = "postgres"
    host: str = "localhost"
    port: int = 5432
    database: str = "postgres"
```

**Properties:**
- **connection_string** (`str`): Synchronous connection string for psycopg
- **connection_string_async** (`str`): Asynchronous connection string for asyncpg

**Class Methods:**
```python
@classmethod
def from_env(cls) -> Self:
```
Create PostgresConfig from environment variables (`POSTGRES_USER`, `POSTGRES_PASSWORD`, etc.).

## Utility Functions

### mqtt_connection_handler

Main entry point for skill lifecycle management.

```python
async def mqtt_connection_handler(
    skill_class,
    skill_config: SkillConfig,
    mqtt_config: MqttConfig,
    retry_interval: int = 5,
    logger: logging.Logger | None = None,
    **kwargs,
) -> None:
```

**Parameters:**
- **skill_class**: Class that inherits from BaseSkill
- **skill_config**: Topic and skill configuration
- **mqtt_config**: MQTT broker connection settings (host, port, credentials)
- **retry_interval**: Seconds between reconnection attempts
- **logger**: Optional custom logger
- **kwargs**: Additional arguments passed to skill constructor

Handles:
1. MQTT connection establishment with retry logic
2. Skill instantiation and setup
3. Task group management
4. Automatic reconnection on connection loss

### load_config

Load and validate configuration from YAML files.

```python
def load_config[T: BaseModel](config_path: str | Path, config_class: type[T]) -> T:
```

**Parameters:**
- **config_path**: Path to YAML file or directory containing YAML files
- **config_class**: Pydantic model class to validate against

**Returns:** Validated instance of the provided Pydantic model

**Raises:**
- `FileNotFoundError`: If no YAML files found
- `ValidationError`: If configuration doesn't match schema

### combine_yaml_files

Combine multiple YAML files into a single configuration dictionary.

```python
def combine_yaml_files(file_paths: list[Path]) -> dict:
```

**Parameters:**
- **file_paths**: List of paths to YAML files to merge

**Returns:** Combined dictionary with later files overriding earlier ones for conflicting keys.

## Logging

### SkillLogger

Utility class for creating standardized loggers.

```python
class SkillLogger:
    @staticmethod
    def get_logger(name: str, level: int | None = None) -> logging.Logger:
```

**Parameters:**
- **name**: Logger name (typically `__name__`)
- **level**: Optional log level override

**Returns:** Configured logger with console handler and standard formatting

**Environment Variables:**
- **LOG_LEVEL**: Sets default log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)

## Error Handling

The library uses standard Python exceptions with additional context:

### ValidationError
- Raised by Pydantic models for invalid data
- Occurs during message parsing or configuration loading

### MqttError (from aiomqtt)
- Raised for MQTT connection issues
- Handled automatically by mqtt_connection_handler with retry logic

### asyncio.CancelledError
- Raised when tasks are cancelled during shutdown
- Properly handled by BaseSkill methods

## Type Hints

The library makes extensive use of Python type hints:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    import uuid
```

All public APIs are fully type-hinted for better IDE support and static analysis.

## Constants and Defaults

### Default Values
- **certainty_threshold**: 0.8
- **retry_interval**: 5 seconds
- **base_topic**: "assistant"
- **log_level**: "INFO" (from LOG_LEVEL env var)

### Topic Patterns
- **Intent results**: `{base_topic}/intent_engine/result`
- **Broadcast**: `{base_topic}/broadcast`
- **Skill feedback**: `{base_topic}/{client_id}/feedback`

This API reference covers all public interfaces provided by the Private Assistant Commons library.
