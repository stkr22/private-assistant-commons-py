# Private Assistant Commons - Usage Guide

## Quick Start

### Installing the Library

```bash
pip install private-assistant-commons
```

### Basic Skill Implementation

```python
from private_assistant_commons import BaseSkill, IntentAnalysisResult

class LightControlSkill(BaseSkill):
    async def skill_preparations(self) -> None:
        """Initialize any resources needed by the skill."""
        self.logger.info("Light control skill initialized")
        
    async def calculate_certainty(self, intent_analysis_result: IntentAnalysisResult) -> float:
        """Calculate confidence score for handling this request."""
        verbs = intent_analysis_result.verbs
        nouns = intent_analysis_result.nouns
        
        # Check for light-related keywords
        light_nouns = {"light", "lights", "lamp", "bulb"}
        light_verbs = {"turn", "switch", "dim", "brighten"}
        
        noun_match = bool(set(nouns) & light_nouns)
        verb_match = bool(set(verbs) & light_verbs)
        
        if noun_match and verb_match:
            return 0.9
        elif noun_match:
            return 0.5
        else:
            return 0.0
            
    async def process_request(self, intent_analysis_result: IntentAnalysisResult) -> None:
        """Process a request that exceeded the certainty threshold."""
        client_request = intent_analysis_result.client_request
        
        # Determine target room(s)
        rooms = intent_analysis_result.rooms or [client_request.room]
        
        # Process the command
        action = "turned off" if "off" in intent_analysis_result.verbs else "turned on"
        room_text = " and ".join(rooms)
        
        response_text = f"I've {action} the lights in the {room_text}"
        
        # Send response back to the user
        await self.send_response(response_text, client_request)
```

### Running a Skill

```python
import asyncio
from private_assistant_commons import SkillConfig, mqtt_connection_handler

async def main():
    # Load configuration
    config = SkillConfig(
        mqtt_server_host="localhost",
        mqtt_server_port=1883,
        client_id="light_control_skill"
    )
    
    # Start the skill
    await mqtt_connection_handler(
        skill_class=LightControlSkill,
        skill_config=config,
        certainty_threshold=0.7  # Custom threshold
    )

if __name__ == "__main__":
    asyncio.run(main())
```

## Common Patterns

### 1. Keyword-Based Certainty Calculation

Most skills use simple keyword matching:

```python
async def calculate_certainty(self, intent_analysis_result: IntentAnalysisResult) -> float:
    verbs = set(intent_analysis_result.verbs)
    nouns = set(intent_analysis_result.nouns)
    
    # Required keywords for this skill
    required_verbs = {"play", "start", "stop", "pause"}
    required_nouns = {"music", "song", "playlist", "spotify"}
    
    verb_score = 0.4 if verbs & required_verbs else 0.0
    noun_score = 0.6 if nouns & required_nouns else 0.0
    
    return verb_score + noun_score
```

### 2. Number Processing

Extract and use numbers from voice commands:

```python
async def process_request(self, intent_analysis_result: IntentAnalysisResult) -> None:
    numbers = intent_analysis_result.numbers
    
    # Look for timer duration
    duration_minutes = None
    for num_result in numbers:
        if num_result.next_token in ["minute", "minutes", "min"]:
            duration_minutes = num_result.number_token
            break
    
    if duration_minutes:
        # Set timer for specified duration
        await self._start_timer(duration_minutes)
```

### 3. Background Tasks

Use task spawning for delayed or concurrent operations:

```python
async def process_request(self, intent_analysis_result: IntentAnalysisResult) -> None:
    client_request = intent_analysis_result.client_request
    
    # Acknowledge immediately
    await self.send_response("Setting timer", client_request)
    
    # Spawn background timer task
    self.add_task(self._timer_task(duration, client_request))

async def _timer_task(self, duration_minutes: int, client_request):
    """Background task that waits then alerts."""
    await asyncio.sleep(duration_minutes * 60)
    
    # Send alert after timer completes
    alert = messages.Alert(play_before=True, sound="timer")
    await self.send_response(
        f"Timer for {duration_minutes} minutes is complete!",
        client_request,
        alert=alert
    )
```

### 4. Room-Based Processing

Handle location context in commands:

```python
async def process_request(self, intent_analysis_result: IntentAnalysisResult) -> None:
    client_request = intent_analysis_result.client_request
    
    # Get target rooms from command or fallback to origin
    target_rooms = intent_analysis_result.rooms
    if not target_rooms:
        target_rooms = [client_request.room]
    
    # Process for each target room
    for room in target_rooms:
        await self._control_device_in_room(room, action="toggle")
    
    room_list = " and ".join(target_rooms)
    await self.send_response(f"Controlled devices in {room_list}", client_request)
```

### 5. Database Integration

For skills requiring persistence:

```python
from private_assistant_commons import PostgresConfig
import asyncpg

class SpotifySkill(BaseSkill):
    def __init__(self, *args, db_config: PostgresConfig, **kwargs):
        super().__init__(*args, **kwargs)
        self.db_config = db_config
        self.db_pool = None
        
    async def skill_preparations(self) -> None:
        # Initialize database connection pool
        self.db_pool = await asyncpg.create_pool(
            self.db_config.connection_string_async
        )
        
    async def _store_token(self, user_id: str, access_token: str):
        """Store Spotify token for user."""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO user_tokens (user_id, token) VALUES ($1, $2) "
                "ON CONFLICT (user_id) DO UPDATE SET token = $2",
                user_id, access_token
            )
```

## Configuration

### YAML Configuration

Skills can load configuration from YAML files:

```yaml
# config/skill.yaml
mqtt_server_host: "mqtt.local"
mqtt_server_port: 1883
client_id: "weather_skill"
base_topic: "assistant"

# Performance tuning
intent_cache_size: 2000  # Increase for high-volume skills

# Skill-specific settings
api_key: "your-api-key-here"
default_location: "San Francisco"
```

```python
from private_assistant_commons import load_config, SkillConfig

# Custom config class
class WeatherConfig(SkillConfig):
    api_key: str
    default_location: str = "Unknown"

# Load from YAML
config = load_config("config/", WeatherConfig)
```

### Environment Variables

Use environment-based configuration:

```python
# For database config
db_config = PostgresConfig.from_env()

# For logging
import os
os.environ["LOG_LEVEL"] = "DEBUG"
```

## Response Handling

### Simple Response

```python
await self.send_response("Task completed", client_request)
```

### Response with Audio Alert

```python
from private_assistant_commons import Alert

alert = Alert(play_before=True, sound="success")
await self.send_response("Task completed successfully", client_request, alert)
```

### Broadcast to All Users

```python
# System-wide announcement
await self.broadcast_response("System maintenance in 5 minutes")
```

### Flexible Response Helper

```python
# Send to specific user
await self.publish_with_alert(
    "Personal reminder set", 
    client_request=client_request,
    broadcast=False
)

# Broadcast to everyone
await self.publish_with_alert(
    "Weather alert: Storm approaching",
    broadcast=True,
    alert=Alert(play_before=True, sound="warning")
)
```

## Advanced Patterns

### Complex Certainty Calculation

```python
async def calculate_certainty(self, intent_analysis_result: IntentAnalysisResult) -> float:
    verbs = intent_analysis_result.verbs
    nouns = intent_analysis_result.nouns
    text = intent_analysis_result.client_request.text.lower()
    
    # Base score from keywords
    score = 0.0
    
    # Verb matching
    if any(v in verbs for v in ["weather", "forecast", "temperature"]):
        score += 0.4
        
    # Noun matching  
    weather_nouns = {"weather", "temperature", "rain", "snow", "sun"}
    if any(n in nouns for n in weather_nouns):
        score += 0.3
        
    # Context phrases
    weather_phrases = ["what's the weather", "how hot", "will it rain"]
    if any(phrase in text for phrase in weather_phrases):
        score += 0.4
        
    return min(score, 1.0)  # Cap at 1.0
```

### State Management

```python
class TimerSkill(BaseSkill):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.active_timers: dict[uuid.UUID, dict] = {}
        
    async def process_request(self, intent_analysis_result: IntentAnalysisResult) -> None:
        if "cancel" in intent_analysis_result.verbs:
            await self._cancel_timers(intent_analysis_result.client_request)
        else:
            await self._start_new_timer(intent_analysis_result)
            
    async def _cancel_timers(self, client_request):
        # Cancel all timers for this user
        user_timers = [t for t in self.active_timers.values() 
                      if t["client_request"].id == client_request.id]
        
        for timer in user_timers:
            timer["task"].cancel()
            
        await self.send_response(f"Cancelled {len(user_timers)} timers", client_request)
```

### Error Handling

```python
async def process_request(self, intent_analysis_result: IntentAnalysisResult) -> None:
    client_request = intent_analysis_result.client_request
    
    try:
        result = await self._call_external_api()
        await self.send_response(f"Result: {result}", client_request)
        
    except asyncio.TimeoutError:
        self.logger.warning("API call timed out")
        await self.send_response("Service temporarily unavailable", client_request)
        
    except Exception as e:
        self.logger.error("Unexpected error: %s", e, exc_info=True)
        await self.send_response("Sorry, something went wrong", client_request)
```

## Performance Tuning

### Cache Configuration

The `intent_cache_size` parameter controls memory usage and performance:

```yaml
# For low-traffic skills (default)
intent_cache_size: 1000

# For high-traffic skills
intent_cache_size: 5000

# For memory-constrained environments
intent_cache_size: 500
```

**Guidelines:**
- **Default (1000)**: Suitable for most skills processing <100 messages/hour
- **High-traffic (5000+)**: Skills processing >500 messages/hour or requiring delayed processing
- **Low-memory (500)**: Resource-constrained deployments or IoT devices

The cache uses LRU eviction - older entries are automatically removed when the limit is reached, preventing memory leaks while maintaining fast O(1) lookup performance.

## Testing Skills

### Unit Testing

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
async def skill():
    config = SkillConfig()
    mqtt_client = AsyncMock()
    task_group = AsyncMock()
    
    skill = LightControlSkill(config, mqtt_client, task_group)
    return skill

@pytest.mark.asyncio
async def test_certainty_calculation(skill):
    intent = IntentAnalysisResult(
        client_request=ClientRequest(...),
        verbs=["turn", "on"],
        nouns=["lights"],
        numbers=[],
        rooms=[]
    )
    
    certainty = await skill.calculate_certainty(intent)
    assert certainty == 0.9
```

## Deployment

### Docker Container

```dockerfile
FROM python:3.12-slim

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY skill.py .
CMD ["python", "skill.py"]
```

### Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: light-control-skill
spec:
  replicas: 1
  selector:
    matchLabels:
      app: light-control-skill
  template:
    metadata:
      labels:
        app: light-control-skill
    spec:
      containers:
      - name: skill
        image: light-control-skill:latest
        env:
        - name: LOG_LEVEL
          value: "INFO"
        - name: MQTT_HOST
          value: "mqtt-service"
```

This guide covers the most common patterns for building Private Assistant skills. For more advanced use cases, refer to the API reference and architecture documentation.