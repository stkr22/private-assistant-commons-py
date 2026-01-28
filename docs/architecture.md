# Private Assistant Commons - Architecture Guide

## System Overview

Private Assistant Commons is a foundational library for building a distributed, local voice assistant system. The system processes voice commands for home automation through modular "skills" that communicate via MQTT messaging.

### Key Characteristics

- **Local & Private**: Runs entirely on local infrastructure (typically Kubernetes)
- **Distributed Processing**: No central coordinator - skills decide independently whether to handle requests
- **MQTT-Based**: All communication via structured MQTT messages using Pydantic models
- **Async & Concurrent**: Built on asyncio with TaskGroup for concurrent operations
- **Extensible**: Skills can be added/removed without system changes

## Architecture Components

```mermaid
graph TB
    LC[Local Client<br/>Audio I/O]
    VB[Voice Bridge<br/>WebSocket Server]
    STT[STT API<br/>Speech-to-Text]
    TTS[TTS API<br/>Text-to-Speech]
    MB[MQTT Broker<br/>Message Router]
    IAE[Intent Analysis Engine<br/>NLP Processing]
    S1[Skill 1<br/>Light Control]
    S2[Skill 2<br/>Timer/Alarm]
    S3[Skill N<br/>Weather/etc]

    LC -->|Audio Stream<br/>WebSocket| VB
    VB -->|Audio Chunks| STT
    STT -->|Transcribed Text| VB
    VB -->|ClientRequest<br/>MQTT| MB

    MB -->|ClientRequest| IAE
    IAE -->|IntentRequest<br/>assistant/intent_engine/result| MB

    MB -->|MQTT Subscribe| S1
    MB -->|MQTT Subscribe| S2
    MB -->|MQTT Subscribe| S3

    S1 -->|Response Messages<br/>client/broadcast topics| MB
    S2 -->|Response Messages<br/>client/broadcast topics| MB
    S3 -->|Response Messages<br/>client/broadcast topics| MB

    MB -->|Response Messages| VB
    VB -->|Response Text| TTS
    TTS -->|Audio Response| VB
    VB -->|Audio + Alerts<br/>WebSocket| LC

    classDef mqtt fill:#e1f5fe
    classDef skill fill:#f3e5f5
    classDef bridge fill:#e8f5e8
    classDef api fill:#fff3e0
    classDef client fill:#f1f8e9

    class MB mqtt
    class S1,S2,S3 skill
    class VB,IAE bridge
    class STT,TTS api
    class LC client
```

## Core Architectural Patterns

### 1. Distributed Skill Processing

**No Central Coordinator**: Originally the system had a coordinator that selected which skill should handle each request. This was removed to reduce latency.

**Current Flow**:
1. Intent Analysis Engine processes voice command → `IntentRequest` (containing `ClassifiedIntent` + `ClientRequest`)
2. All skills receive the message via MQTT
3. Each skill calculates its certainty score independently
4. Skills with certainty ≥ threshold process the request
5. Multiple skills can respond to the same request (rare but acceptable)

**Benefits**:
- Lower latency (no coordinator round-trip)
- Better fault tolerance (no single point of failure)
- Simpler architecture

### 2. Message-Driven Communication

All system components communicate via MQTT using structured Pydantic models:

- **ClientRequest**: Original voice command + metadata (id, text, room, output_topic)
- **ClassifiedIntent**: Classified intent type with confidence score and extracted entities
- **IntentRequest**: Combined wrapper containing both ClassifiedIntent and ClientRequest
- **Entity**: Extracted component with type, normalization, and linking capabilities
- **Response**: Skill output with optional audio alerts

### 3. Intent-Based Processing with Context-Aware Confidence

Skills configure their intent handling via simple instance attributes set in `__init__`:

#### Step 1: Intent Matching with Per-Intent Thresholds
Skills define supported intents as a dict mapping intent types to confidence thresholds:

```python
def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)

    # Per-intent confidence thresholds
    self.supported_intents = {
        IntentType.DEVICE_ON: 0.8,    # Standard threshold
        IntentType.DEVICE_OFF: 0.8,   # Standard threshold
        IntentType.DEVICE_SET: 0.9,   # Higher threshold for critical actions
    }
```

The BaseSkill automatically filters out unsupported intent types for efficient processing.

#### Step 2: Confidence Evaluation
The intent engine assigns confidence scores based on pattern matching quality:
- **1.0** - Multi-word keyword + context hints (e.g., "turn on" + "lights")
- **0.9** - Multi-word keyword alone OR single keyword + multiple context hints
- **0.8** - Single keyword + single context hint OR all pattern keywords present
- **0.5** - Single keyword match without context
- **0.3** - Context hints without keywords

Skills can define **confidence modifiers** to lower thresholds for contextually related follow-up commands:

```python
    # Confidence modifiers for context-aware processing
    # Key is the intent being impacted, value is list of modifiers
    self.confidence_modifiers = {
        IntentType.DEVICE_OFF: [
            ConfidenceModifier(
                trigger_intent=IntentType.DEVICE_ON,  # If this was recently handled
                lowers_threshold_for=IntentType.DEVICE_OFF,  # Lower threshold for this
                reduced_threshold=0.5,  # Down to this level
                time_window_seconds=300  # Within this window
            )
        ]
    }
```

The dict structure allows efficient O(1) lookup by target intent, and supports multiple modifiers per intent. This improves conversation flow - if a user just said "turn on the lights", a follow-up "turn them off" with lower confidence will still be accepted.

#### Step 3: Entity Matching (Optional)
Skills can optionally define entity matchers for additional validation:

```python
    # Optional: Entity matchers for validation
    self.entity_matchers = {
        "devices": lambda devices: any("light" in d.raw_text.lower() for d in devices)
    }
```

If no entity matchers are defined, all intents that pass the confidence check are processed.

### 4. Location-Aware Processing

The system distinguishes between command origin and target:

- **ClientRequest.room**: Where the command was spoken ("kitchen")
- **Entity(type=ROOM)**: Target locations extracted as entities ("living room" for "turn off lights in living room")
- **Fallback behavior**: Skills use origin room when no target specified

### 5. Task Management & Concurrency

Skills use `asyncio.TaskGroup` for concurrent operations:

- **MQTT message handling**: Main loop processes incoming messages
- **Background tasks**: Timers, delayed responses, concurrent API calls
- **Lifecycle management**: Tasks are properly cleaned up on skill shutdown

**Common Patterns**:
```python
# Spawn a timer task
self.add_task(self._timer_task(duration, message))

# Background API call
self.add_task(self._fetch_weather_data())
```

## Data Flow

### Voice Command Processing

```mermaid
sequenceDiagram
    participant User
    participant LC as Local Client
    participant VB as Voice Bridge
    participant STT as STT API
    participant TTS as TTS API
    participant MB as MQTT Broker
    participant IAE as Intent Analysis Engine
    participant LS as Light Skill
    participant TS as Timer Skill

    User->>LC: Speaks: "Turn off lights in living room"
    LC->>VB: Audio stream (WebSocket)
    VB->>STT: Audio chunks
    STT->>VB: Transcribed text: "Turn off lights in living room"
    VB->>MB: ClientRequest (MQTT)

    MB->>IAE: ClientRequest message
    IAE->>MB: IntentRequest<br/>topic: assistant/intent_engine/result

    MB->>LS: MQTT message (subscribed)
    MB->>TS: MQTT message (subscribed)

    LS->>LS: calculate_certainty() = 0.95
    TS->>TS: calculate_certainty() = 0.1

    Note over LS: certainty ≥ threshold (0.8)
    LS->>LS: process_request()
    LS->>MB: Response: "Turning off living room lights"<br/>topic: client/output/xyz

    Note over TS: certainty < threshold - ignored

    MB->>VB: Response message (subscribed to output topics)
    VB->>TTS: Response text + alert config
    TTS->>VB: Generated audio
    VB->>LC: Audio response + alerts (WebSocket)
    LC->>User: Plays audio: "Turning off living room lights"
```

**Detailed Flow:**
1. **Voice Capture**: User speaks to Local Client, which streams audio to Voice Bridge via WebSocket
2. **Speech-to-Text**: Voice Bridge sends audio chunks to local STT API for transcription
3. **MQTT Publishing**: Voice Bridge publishes `ClientRequest` with transcribed text to MQTT broker
4. **Intent Analysis**: Intent Analysis Engine receives `ClientRequest`, classifies intent, and publishes `IntentRequest` to MQTT
5. **Distributed Processing**: All skills receive the `IntentRequest` via their MQTT subscriptions
6. **Certainty Evaluation**: Each skill calculates confidence score independently
7. **Selective Processing**: Only skills with certainty ≥ threshold process the request
8. **Response Publishing**: Processing skill publishes `Response` to appropriate MQTT topic
9. **Text-to-Speech**: Voice Bridge receives response, sends text to local TTS API for audio generation
10. **Audio Output**: Voice Bridge streams generated audio + alerts back to Local Client via WebSocket

### Message Routing

- **Targeted responses**: `skill.send_response(text, client_request)`
  - Uses `client_request.output_topic`
  - Sent to specific user/device
- **Broadcast responses**: `skill.broadcast_response(text)`
  - Uses `config.broadcast_topic`
  - Sent to all connected clients

## Skill Lifecycle

### Initialization
```python
async def mqtt_connection_handler(skill_class, config, **kwargs):
    # 1. Establish MQTT connection with retry logic
    # 2. Create TaskGroup for concurrent operations
    # 3. Initialize skill instance
    # 4. Setup MQTT subscriptions
    # 5. Call skill_preparations() for custom setup
    # 6. Start message listening loop
```

### Runtime
```python
# Main message loop
async def listen_to_messages():
    async for message in mqtt_client.messages:
        if message.topic.matches(intent_topic):
            await handle_client_request_message(payload)

# Request processing pipeline
async def handle_client_request_message(payload):
    intent_request = IntentRequest.parse(payload)

    # Step 1: Check if intent type is in self.supported_intents
    if intent_request.classified_intent.intent_type not in self.supported_intents:
        return  # Skip - not relevant to this skill

    # Step 2: Get per-intent threshold and apply confidence modifiers
    required_confidence = self.supported_intents[intent_request.classified_intent.intent_type]
    effective_threshold = required_confidence

    # Check modifiers via O(1) dict lookup
    modifiers_for_intent = self.confidence_modifiers.get(intent_request.classified_intent.intent_type, [])
    for modifier in modifiers_for_intent:
        if self.skill_context.has_recent_intent(modifier.trigger_intent):
            effective_threshold = min(effective_threshold, modifier.reduced_threshold)

    if intent_request.classified_intent.confidence < effective_threshold:
        return  # Skip - confidence too low

    # Step 3: Check entity matchers (if defined)
    if self.entity_matchers:
        matched = False
        for entity_type, matcher in self.entity_matchers.items():
            entities = intent_request.classified_intent.entities.get(entity_type, [])
            if entities and matcher(entities):
                matched = True
                break
        if not matched:
            return  # Skip - entities don't match

    # All checks passed - process the request
    await process_request(intent_request)

    # Track in context for future threshold adjustments
    self.skill_context.add_action(intent_request.classified_intent.intent_type.value)
```

## Integration Points

### MQTT Topics
- **Intent Results**: `assistant/intent_engine/result`
- **Broadcast**: `assistant/comms_bridge/broadcast`
- **Skill Feedback**: `assistant/{skill_id}/feedback`

### External Systems
- **Voice Bridge**: Audio input/output via FastAPI WebSocket
- **PostgreSQL Database**: Required for global device registry and skill registration
- **APIs**: Skills can integrate with external services (Home Assistant, Spotify, weather APIs, etc.)

## Device Registry

All skills participate in the global device registry for intent engine pattern matching. The registry enables the intent engine to:
- Match specific devices in voice commands ("turn on bedroom lamp")
- Resolve generic device types ("turn on lights" → all light devices)
- Provide context hints for intent classification

### Database Requirement

**PostgreSQL database is mandatory** for all skills. The database stores:
- Skills: Registered skill instances with unique names
- Device Types: Categories of devices (light, switch, timer, alarm, etc.)
- Devices: Specific devices with pattern strings for NL matching
- Rooms: Optional location associations for devices

### Automatic Registration

Skills are automatically registered during `skill_preparations()`:
1. Skill registration (idempotent by name)
2. Device type registration (from `supported_device_types` list)
3. Devices can then be registered by the skill

**Static Devices** (Timer/Alarm):
```python
class TimerSkill(BaseSkill):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.supported_device_types = ["timer", "alarm"]

    async def skill_preparations(self):
        await super().skill_preparations()  # Auto-registers skill + device types

        # Register static devices
        await self.register_device("timer", "timer", ["timer", "set timer"])
        await self.register_device("alarm", "alarm", ["alarm", "set alarm"])
```

**Dynamic Devices** (Lights from Home Assistant):
```python
class SwitchSkill(BaseSkill):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.supported_device_types = ["light", "switch"]

    async def skill_preparations(self):
        await super().skill_preparations()  # Auto-registers skill + device types

        # Sync devices from external system
        await self._sync_devices_from_home_assistant()

        # Schedule periodic refresh
        self.add_task(self._periodic_device_sync(interval=300))
```

### MQTT Notifications

When devices are registered, skills automatically publish to `assistant/global_device_update` topic, triggering the intent engine to refresh its device cache.

Skills also listen to this topic to reactively refresh their device cache when external systems (like a device management interface) modify devices in the database. This listener runs as a background task started during `skill_preparations()`.

## Configuration Management

Skills use `SkillConfig` for:
- MQTT connection settings
- Topic hierarchy configuration
- Skill-specific settings via YAML files

`PostgresConfig` (required) for database connection:
- Connection string generation for sync/async operations
- Environment variable loading (POSTGRES_USER, POSTGRES_PASSWORD, etc.)
- Used by all skills for device registry access

## Error Handling

### MQTT Resilience
- Automatic reconnection on connection loss
- Configurable retry intervals
- Graceful degradation when services unavailable

### Skill Robustness
- Pydantic validation for all messages
- Structured exception handling
- Comprehensive logging with configurable levels

### Task Management
- TaskGroup automatically handles task cleanup
- Proper cancellation handling
- Resource cleanup on skill shutdown

## Performance Considerations

### Message Processing
- Lightweight certainty calculations for fast filtering
- Async/await throughout for non-blocking operations
- Bounded LRU cache prevents memory leaks with automatic eviction
- Concurrent message processing for improved throughput (2-3x improvement)
- Thread-safe cache access with asyncio.Lock for data integrity

### Resource Management
- Skills only process relevant messages
- Background tasks managed by TaskGroup
- Optional database connections only when needed
- Configurable intent cache size (default: 1000 entries)
- Memory usage remains stable during long-running operations

### Scalability
- Horizontal: Add more skill instances
- Vertical: Skills process multiple messages concurrently
- Topic-based message filtering reduces processing overhead
- Individual message processing errors don't affect other messages

## Security & Privacy

### Local Processing
- No cloud dependencies
- All data stays on local network
- Voice processing entirely local

### Message Security
- MQTT over local network only
- Structured message validation
- No sensitive data in logs

This architecture provides a robust, scalable foundation for building sophisticated voice assistant capabilities while maintaining privacy and local control.
