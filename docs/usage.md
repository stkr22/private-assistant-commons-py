# Private Assistant Commons - Usage Guide

## Quick Start

### Installing the Library

```bash
pip install private-assistant-commons
```

### Basic Skill Implementation

```python
from private_assistant_commons import BaseSkill, IntentRequest, IntentType, EntityType

class LightControlSkill(BaseSkill):
    async def skill_preparations(self) -> None:
        """Initialize any resources needed by the skill."""
        self.logger.info("Light control skill initialized")
        
    async def calculate_certainty(self, intent_request: IntentRequest) -> float:
        """Calculate confidence score for handling this request."""
        intent = intent_request.classified_intent

        # Check for light-related intent types
        light_intents = {IntentType.DEVICE_ON, IntentType.DEVICE_OFF, IntentType.DEVICE_SET}

        if intent.intent_type in light_intents:
            # Check if it's about lights based on entities
            for entity in intent.entities.get("devices", []):
                if entity.raw_text.lower() in {"light", "lights", "lamp", "bulb"}:
                    return intent.confidence
            return 0.3  # Low confidence if intent type matches but no light entity
        else:
            return 0.0
            
    async def process_request(self, intent_request: IntentRequest) -> None:
        """Process a request that exceeded the certainty threshold."""
        client_request = intent_request.client_request
        intent = intent_request.classified_intent

        # Determine target room(s) from entities
        room_entities = intent.entities.get("rooms", [])
        rooms = [e.normalized_value for e in room_entities] or [client_request.room]

        # Process the command based on intent type
        action = "turned off" if intent.intent_type == IntentType.DEVICE_OFF else "turned on"
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
async def calculate_certainty(self, intent_request: IntentRequest) -> float:
    intent = intent_request.classified_intent

    # Check for media control intents
    media_intents = {IntentType.MEDIA_PLAY, IntentType.MEDIA_STOP, IntentType.MEDIA_NEXT}

    if intent.intent_type in media_intents:
        return intent.confidence

    # Fallback to checking entities for media-related content
    for entity in intent.entities.get("media_id", []):
        if "music" in entity.raw_text.lower() or "song" in entity.raw_text.lower():
            return 0.7

    return 0.0
```

### 2. Number Processing

Extract and use numbers from voice commands:

```python
async def process_request(self, intent_request: IntentRequest) -> None:
    intent = intent_request.classified_intent
    
    # Look for duration entities
    duration_minutes = None
    for entity in intent.entities.get("durations", []):
        if entity.type == EntityType.DURATION:
            duration_minutes = entity.normalized_value
            break
    
    if duration_minutes:
        # Set timer for specified duration
        await self._start_timer(duration_minutes)
```

### 3. Background Tasks

Use task spawning for delayed or concurrent operations:

```python
async def process_request(self, intent_request: IntentRequest) -> None:
    client_request = intent_request.client_request
    
    # Acknowledge immediately
    await self.send_response("Setting timer", client_request)
    
    # Spawn background timer task
    self.add_task(self._timer_task(duration, client_request))

async def _timer_task(self, duration_minutes: int, client_request):
    """Background task that waits then alerts."""
    await asyncio.sleep(duration_minutes * 60)
    
    # Send alert after timer completes
    alert = Alert(play_before=True, sound="timer")
    await self.send_response(
        f"Timer for {duration_minutes} minutes is complete!",
        client_request,
        alert=alert
    )
```

### 4. Room-Based Processing

Handle location context in commands:

```python
async def process_request(self, intent_request: IntentRequest) -> None:
    client_request = intent_request.client_request
    
    # Get target rooms from entities or fallback to origin
    room_entities = intent_request.classified_intent.entities.get("rooms", [])
    target_rooms = [e.normalized_value for e in room_entities] or [client_request.room]
    
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
async def calculate_certainty(self, intent_request: IntentRequest) -> float:
    intent = intent_request.classified_intent
    text = intent_request.client_request.text.lower()
    
    # Base score from intent type and entities
    score = 0.0

    # Check for weather-related queries
    if intent.intent_type == IntentType.QUERY_STATUS:
        # Check entities for weather-related content
        for entity_list in intent.entities.values():
            for e in entity_list:
                if any(word in e.raw_text.lower() for word in ["weather", "temperature", "rain"]):
                    score += 0.7
                    break
        
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
        
    async def process_request(self, intent_request: IntentRequest) -> None:
        if intent_request.classified_intent.intent_type == IntentType.SCHEDULE_CANCEL:
            await self._cancel_timers(intent_request.client_request)
        else:
            await self._start_new_timer(intent_request)
            
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
async def process_request(self, intent_request: IntentRequest) -> None:
    client_request = intent_request.client_request
    
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

## Monitoring and Metrics

Private Assistant Commons includes comprehensive metrics collection for production monitoring and observability.

### Built-in Metrics Collection

Every BaseSkill automatically collects performance metrics:

```python
# Metrics are automatically collected for:
# - Message processing (throughput, latency, success rates)
# - MQTT operations (publish success/failure, response times)
# - Task management (creation, completion, failures)
# - Cache performance (hit rates, evictions)
# - System health (error rates, uptime)

# Access metrics in your skill:
class MySkill(BaseSkill):
    async def skill_preparations(self) -> None:
        # Metrics are available via self.metrics
        self.logger.info("Metrics collector: %s", self.metrics.skill_name)
```

### Prometheus Integration

Export metrics for Prometheus monitoring:

```python
from private_assistant_commons.metrics import MetricsCollector

# Get Prometheus format metrics
metrics_text = skill.metrics.get_prometheus_metrics()

# Typical metrics exported:
# - skill_messages_processed_total
# - skill_messages_failed_total  
# - skill_message_processing_duration_seconds
# - skill_throughput_messages_per_second
# - skill_mqtt_publishes_total
# - skill_mqtt_publish_failures_total
# - skill_tasks_created_total
# - skill_cache_hits_total
# - skill_uptime_seconds
```

### HTTP Metrics Endpoint 

Add a metrics endpoint to your skill:

```python
from aiohttp import web, web_runner
import asyncio

class MonitoredSkill(BaseSkill):
    async def skill_preparations(self) -> None:
        # Start HTTP server for metrics
        await self._start_metrics_server()
    
    async def _start_metrics_server(self):
        """Start HTTP server for Prometheus metrics scraping."""
        app = web.Application()
        app.router.add_get('/metrics', self._metrics_handler)
        app.router.add_get('/health', self._health_handler)
        
        runner = web_runner.AppRunner(app)
        await runner.setup()
        
        site = web_runner.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        
        self.logger.info("Metrics server started on :8080")
    
    async def _metrics_handler(self, request):
        """Serve Prometheus metrics."""
        metrics_text = self.metrics.get_prometheus_metrics()
        return web.Response(text=metrics_text, content_type='text/plain')
    
    async def _health_handler(self, request):
        """Serve health check information."""
        from private_assistant_commons.metrics import HealthChecker
        
        health_checker = HealthChecker(self.metrics)
        health_status = health_checker.check_health()
        
        status_code = 200 if health_status["overall_status"] == "healthy" else 503
        return web.json_response(health_status, status=status_code)
```

### Kubernetes Service Monitor

Configure Prometheus to scrape your skills:

```yaml
# service-monitor.yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor  
metadata:
  name: private-assistant-skills
spec:
  selector:
    matchLabels:
      app: private-assistant-skill
  endpoints:
  - port: metrics
    path: /metrics
    interval: 30s
---
# service.yaml  
apiVersion: v1
kind: Service
metadata:
  name: light-skill-metrics
  labels:
    app: private-assistant-skill
spec:
  ports:
  - name: metrics
    port: 8080
    targetPort: 8080
  selector:
    app: light-control-skill
```

### Health Monitoring

Automated health checks with configurable thresholds:

```python
from private_assistant_commons.metrics import HealthChecker

health_checker = HealthChecker(skill.metrics)
health_status = health_checker.check_health()

# Health status includes:
# - overall_status: "healthy", "degraded", or "critical"
# - checks: Individual component health
# - alerts: Current issues requiring attention
# - recommendations: Performance optimization suggestions

print(f"System status: {health_status['overall_status']}")
for alert in health_status['alerts']:
    print(f"⚠️  {alert}")
```

### Grafana Dashboard

Example Grafana queries for skill monitoring:

```promql
# Message processing rate
rate(skill_messages_processed_total[5m])

# Error rate percentage  
rate(skill_messages_failed_total[5m]) / rate(skill_messages_processed_total[5m]) * 100

# 95th percentile latency
histogram_quantile(0.95, skill_message_processing_duration_seconds)

# MQTT success rate
rate(skill_mqtt_publishes_total[5m]) / (rate(skill_mqtt_publishes_total[5m]) + rate(skill_mqtt_publish_failures_total[5m])) * 100

# Cache hit rate
rate(skill_cache_hits_total[5m]) / (rate(skill_cache_hits_total[5m]) + rate(skill_cache_misses_total[5m])) * 100
```

### Custom Metrics

Add skill-specific metrics:

```python
class WeatherSkill(BaseSkill):
    async def process_request(self, intent_request: IntentRequest) -> None:
        # Start timing custom operation
        timer_id = self.metrics.start_timer("weather_api_call")
        
        try:
            weather_data = await self._get_weather()
            
            # Record successful API call
            duration = self.metrics.end_timer(timer_id)
            self.logger.info("Weather API call completed in %.3fs", duration)
            
        except Exception as e:
            # Record failed operation
            self.metrics.end_timer(timer_id)
            self.metrics.record_log_event("ERROR")
            raise
```

These metrics provide comprehensive visibility into skill performance, helping identify bottlenecks, monitor system health, and ensure reliable operation in production environments.

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
    from private_assistant_commons import ClientRequest, ClassifiedIntent, Entity
    import uuid

    client_request = ClientRequest(
        id=uuid.uuid4(),
        text="turn on lights",
        room="living_room",
        output_topic="test/output"
    )
    classified_intent = ClassifiedIntent(
        intent_type=IntentType.DEVICE_ON,
        confidence=0.9,
        entities={"devices": [Entity(type=EntityType.DEVICE, raw_text="lights", normalized_value="lights")]},
        raw_text="turn on lights"
    )
    intent_request = IntentRequest(
        classified_intent=classified_intent,
        client_request=client_request
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