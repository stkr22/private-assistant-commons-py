from __future__ import annotations

import asyncio
import weakref
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import partial
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import logging
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncEngine

import aiomqtt
from pydantic import ValidationError
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from private_assistant_commons import intent, skill_config, skill_logger
from private_assistant_commons.database.models import DeviceType, GlobalDevice, Room, Skill
from private_assistant_commons.messages import Alert, ClientRequest, Response
from private_assistant_commons.metrics import MetricsCollector
from private_assistant_commons.skill_context import ConfidenceModifier, SkillContext


# AIDEV-NOTE: Core abstract base class for all skills in Private Assistant ecosystem
class BaseSkill(ABC):
    """Abstract base class for Private Assistant skills.

    Provides common functionality for MQTT-based skills that process voice commands
    in a distributed manner. Skills inherit from this class and implement abstract
    methods for certainty calculation and request processing.

    Architecture:
    - Distributed processing: Each skill decides independently whether to handle requests
    - MQTT messaging: Async communication via structured Pydantic models
    - Task management: Uses asyncio.TaskGroup for concurrent operations
    - Location awareness: Supports room-based command routing
    """

    class MqttErrorType(Enum):
        """Categorize MQTT errors for better handling and recovery."""

        CONNECTION_LOST = "connection_lost"
        PUBLISH_FAILED = "publish_failed"
        TIMEOUT = "timeout"
        VALIDATION_ERROR = "validation_error"

    @dataclass
    class TaskInfo:
        """Track information about active tasks for monitoring and debugging."""

        name: str
        created_at: datetime
        task_ref: weakref.ReferenceType
        metadata: dict[str, Any]

    def __init__(  # noqa: PLR0913
        self,
        config_obj: skill_config.SkillConfig,
        mqtt_client: aiomqtt.Client,
        task_group: asyncio.TaskGroup,
        engine: AsyncEngine,
        certainty_threshold: float = 0.8,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize the base skill.

        Args:
            config_obj: Configuration for MQTT topics and connection settings
            mqtt_client: Connected MQTT client for message publishing/subscribing
            task_group: TaskGroup for managing concurrent operations
            engine: Async database engine for device registry operations (required)
            certainty_threshold: Minimum confidence score to process requests (0.0-1.0)
            logger: Optional custom logger, defaults to skill-specific logger
        """
        self.config_obj: skill_config.SkillConfig = config_obj
        self.certainty_threshold: float = certainty_threshold
        self.mqtt_client: aiomqtt.Client = mqtt_client
        self.task_group: asyncio.TaskGroup = task_group
        self.logger = logger or skill_logger.SkillLogger.get_logger(__name__)
        self.default_alert = Alert(play_before=True)
        self.engine: AsyncEngine = engine

        # AIDEV-NOTE: Task lifecycle management for monitoring and debugging
        self._active_tasks: dict[int, BaseSkill.TaskInfo] = {}
        self._task_counter = 0

        # AIDEV-NOTE: Performance metrics and observability
        self.metrics = MetricsCollector(skill_name=config_obj.client_id)

        # AIDEV-NOTE: Context tracking for intent decision flow
        self.skill_context = SkillContext(skill_name=config_obj.client_id)

        # AIDEV-NOTE: Intent handling configuration - skills set these in their __init__
        # Skills should populate these attributes to configure intent handling behavior:
        # - supported_intents: Map each intent type to its minimum confidence threshold
        # - confidence_modifiers: Map target intent to list of modifiers that lower its threshold
        self.supported_intents: dict[intent.IntentType, float] = {}  # intent -> min confidence threshold
        self.confidence_modifiers: dict[intent.IntentType, list[ConfidenceModifier]] = {}

        # AIDEV-NOTE: Device registry configuration - skills set supported_device_types in their __init__
        # Skills should populate this list with device type names they support (e.g., ["light", "switch"])
        self.supported_device_types: list[str] = []
        self._global_skill_id: UUID | None = None  # Cached skill UUID from database
        self.global_devices: list = []  # Cache of devices from database, refreshed on updates

    def decode_message_payload(self, payload: bytes | bytearray | str | Any) -> str | None:
        """Decode MQTT message payload to string.

        Args:
            payload: Raw MQTT payload (bytes, bytearray, or str)

        Returns:
            Decoded string or None if payload type is unsupported
        """
        # AIDEV-NOTE: Enhanced type hint coverage - supports all MQTT payload types
        if isinstance(payload, bytes | bytearray):
            return payload.decode("utf-8")
        if isinstance(payload, str):
            return payload
        self.logger.warning("Unexpected payload type: %s", type(payload))
        return None

    async def setup_mqtt_subscriptions(self) -> None:
        """Set up MQTT topic subscriptions for the skill.

        Subscribes to the intent analysis result topic to receive processed
        voice commands for evaluation and potential handling. Also subscribes
        to the device update topic to receive notifications when devices are
        added, modified, or removed.
        """
        await self.mqtt_client.subscribe(topic=self.config_obj.intent_analysis_result_topic, qos=1)
        self.logger.info("Subscribed to intent analysis result topic: %s", self.config_obj.intent_analysis_result_topic)

        await self.mqtt_client.subscribe(topic=self.config_obj.device_update_topic, qos=1)
        self.logger.info("Subscribed to device update topic: %s", self.config_obj.device_update_topic)

    async def skill_preparations(self) -> None:
        """Perform skill-specific initialization after MQTT setup.

        Called after MQTT subscriptions are established. Automatically registers
        the skill and its device types in the database, then loads the initial
        device cache. Skills should override this method to add custom setup
        logic (e.g., device registration, external API initialization, etc.),
        but must call super().skill_preparations() first to ensure database
        registration completes.

        Example:
            ```python
            async def skill_preparations(self):
                await super().skill_preparations()  # Register skill + device types

                # Custom initialization
                await self.register_device("timer", "timer", ["timer", "set timer"])
            ```
        """
        # Auto-register skill and device types
        await self.ensure_skill_registered()
        await self.ensure_device_types_registered()

        # Load initial device cache on startup
        self.global_devices = await self.get_skill_devices()
        self.logger.info("Initial device cache loaded: %d devices", len(self.global_devices))

    # AIDEV-NOTE: Main message processing loop - handles all incoming MQTT messages
    async def listen_to_messages(self, client: aiomqtt.Client) -> None:
        """Listen for incoming MQTT messages and route them appropriately.

        Args:
            client: Connected MQTT client to listen on

        This is the main message processing loop that runs continuously,
        filtering messages by topic and delegating to appropriate handlers.
        """
        async for message in client.messages:
            self.logger.debug("Received message on topic %s", message.topic)

            # Filter for intent analysis results - this is the main message type skills process
            if message.topic.matches(self.config_obj.intent_analysis_result_topic):
                payload_str = self.decode_message_payload(message.payload)
                if payload_str is not None:
                    # Process messages concurrently to improve throughput and prevent blocking
                    # Each message gets its own task to allow parallel certainty calculation
                    self.add_task(self._handle_message_async(payload_str))

            # Handle device update notifications
            elif message.topic.matches(self.config_obj.device_update_topic):
                # Process device updates concurrently to avoid blocking the main loop
                self.add_task(self._handle_device_update())

    # AIDEV-NOTE: Intent decision flow - centralized logic for determining whether to handle intent
    def _should_handle_intent(self, intent_request: intent.IntentRequest) -> tuple[bool, float]:
        """Determine if this skill should handle the intent request.

        This method implements the 2-step intent decision flow:
        1. Intent Matching: Check if intent type is supported
        2. Confidence Evaluation: Check if confidence meets threshold (with modifiers)

        Args:
            intent_request: Parsed voice command with classified intent and client request

        Returns:
            Tuple of (should_handle, effective_threshold):
                - should_handle: True if the skill should handle this request, False otherwise
                - effective_threshold: The confidence threshold used (after applying modifiers)
        """
        classified_intent = intent_request.classified_intent

        # Step 1: Intent Matching - Check if this skill supports the intent type
        if classified_intent.intent_type not in self.supported_intents:
            self.logger.debug(
                "Intent type %s not supported by this skill, skipping", classified_intent.intent_type.value
            )
            return False, 0.0

        # Step 2: Confidence Evaluation - Get per-intent threshold and apply modifiers
        required_confidence = self.supported_intents[classified_intent.intent_type]
        effective_threshold = required_confidence

        # Check if any recent intents allow for a lower threshold via O(1) dict lookup
        modifiers_for_intent = self.confidence_modifiers.get(classified_intent.intent_type, [])
        for modifier in modifiers_for_intent:
            # Check if the trigger intent was recent
            recent_action = self.skill_context.find_recent_action(
                modifier.trigger_intent.value, within_seconds=modifier.time_window_seconds
            )
            if recent_action:
                effective_threshold = min(effective_threshold, modifier.reduced_threshold)
                self.logger.debug(
                    "Lowered threshold to %.2f due to recent %s intent",
                    effective_threshold,
                    modifier.trigger_intent.value,
                )

        # Check if confidence meets the effective threshold
        if classified_intent.confidence < effective_threshold:
            self.logger.info(
                "Confidence (%.2f) below effective threshold (%.2f), skipping request.",
                classified_intent.confidence,
                effective_threshold,
            )
            return False, effective_threshold

        return True, effective_threshold

    async def _handle_message_async(self, payload_str: str) -> None:
        """Handle message processing in separate task for concurrency.

        Args:
            payload_str: JSON string containing IntentAnalysisResult

        This method enables concurrent message processing while maintaining
        proper error handling for individual message failures.
        """
        try:
            await self.handle_client_request_message(payload_str)
        except Exception as e:
            self.logger.error("Error processing message: %s", e, exc_info=True)

    # AIDEV-NOTE: Core request processing pipeline - delegates decision to _should_handle_intent
    async def handle_client_request_message(self, payload: str) -> None:
        """Process incoming intent analysis result and decide whether to handle it.

        Args:
            payload: JSON string containing IntentRequest

        Flow:
        1. Parse and validate the intent analysis result
        2. Store for potential delayed processing
        3. Call _should_handle_intent() for 2-step decision process (intent + confidence)
        4. Process request if checks pass (entity validation happens in process_request)
        5. Track processed intent in context for future threshold adjustments
        """
        # Start timing for performance metrics
        timer_id = self.metrics.start_timer("message_processing")

        try:
            # Parse and validate the incoming JSON message
            intent_request = intent.IntentRequest.model_validate_json(payload)
            classified_intent = intent_request.classified_intent

            # Execute the 3-step intent decision flow
            should_handle, effective_threshold = self._should_handle_intent(intent_request)

            if not should_handle:
                # Decision logged within _should_handle_intent
                self.metrics.record_message_processed(success=True, certainty=classified_intent.confidence)
                return

            # All checks passed - process the request
            self.logger.info(
                "Processing intent %s with confidence %.2f (threshold: %.2f)",
                classified_intent.intent_type.value,
                classified_intent.confidence,
                effective_threshold,
            )

            await self.process_request(intent_request)
            self.metrics.record_message_processed(success=True, certainty=classified_intent.confidence)

            # Track this intent in context for future threshold adjustments
            self.skill_context.add_action(
                classified_intent.intent_type.value,
                entities={k: [e.normalized_value for e in v] for k, v in classified_intent.entities.items()},
            )

        except ValidationError as e:
            self.logger.error("Error validating client request message: %s", e)
            self.metrics.record_message_processed(success=False)
            self.metrics.record_log_event("ERROR")
        except Exception as e:
            self.logger.error("Unexpected error processing message: %s", e, exc_info=True)
            self.metrics.record_message_processed(success=False)
            self.metrics.record_log_event("ERROR")
        finally:
            # End timing
            self.metrics.end_timer(timer_id)

    @abstractmethod
    async def process_request(self, intent_request: intent.IntentRequest) -> None:
        """Process a request that exceeded the certainty threshold.

        Args:
            intent_request: Validated request with classified intent and client info

        This is where skills implement their core business logic.
        Common patterns:
        - Send immediate response via send_response()
        - Spawn background tasks for delayed actions (e.g., timers)
        - Interact with external APIs or databases
        """
        pass

    async def send_response(
        self,
        response_text: str,
        client_request: ClientRequest,
        alert: Alert | None = None,
    ) -> bool:
        """Send a response to a specific client request with retry logic.

        Args:
            response_text: Text response to send
            client_request: Original request containing output topic
            alert: Optional audio alert configuration

        Returns:
            bool: True if response was successfully published, False otherwise

        Publishes response to the client-specific output topic for targeted delivery.
        Uses exponential backoff retry logic for improved reliability.
        """
        return await self._send_response_with_retry(
            response_text=response_text, topic=client_request.output_topic, alert=alert, operation="send_response"
        )

    async def broadcast_response(
        self,
        response_text: str,
        alert: Alert | None = None,
    ) -> bool:
        """Broadcast a response to all connected clients with retry logic.

        Args:
            response_text: Text response to broadcast
            alert: Optional audio alert configuration

        Returns:
            bool: True if broadcast was successfully published, False otherwise

        Publishes response to the global broadcast topic for system-wide announcements.
        Uses exponential backoff retry logic for improved reliability.
        """
        return await self._send_response_with_retry(
            response_text=response_text,
            topic=self.config_obj.broadcast_topic,
            alert=alert,
            operation="broadcast_response",
        )

    # AIDEV-NOTE: Convenience method that unifies send_response and broadcast_response
    async def publish_with_alert(
        self,
        response_text: str,
        client_request: ClientRequest | None = None,
        broadcast: bool = False,
        alert: Alert | None = None,
    ) -> None:
        """Publish a message with flexible routing and alert options.

        Args:
            response_text: Text response to publish
            client_request: Required for targeted responses (when broadcast=False)
            broadcast: If True, broadcast to all clients; if False, send to specific client
            alert: Optional audio alert, defaults to skill's default_alert

        Raises:
            ValueError: If broadcast=False but client_request is None
        """
        if alert is None:
            alert = self.default_alert

        # Call the appropriate existing method
        if broadcast:
            await self.broadcast_response(response_text, alert=alert)
        elif client_request is not None:
            await self.send_response(response_text, client_request, alert=alert)
        else:
            raise ValueError("client_request must be provided if broadcast is False.")

        # AIDEV-NOTE: Custom retry logic required - aiomqtt provides connection-level
        # reconnection but NOT publish-level retries. This implements exponential backoff
        # for reliable message delivery even during transient network issues.

    async def _send_response_with_retry(
        self,
        response_text: str,
        topic: str,
        alert: Alert | None = None,
        operation: str = "mqtt_publish",
        max_retries: int = 3,
    ) -> bool:
        """Send MQTT response with exponential backoff retry logic.

        Args:
            response_text: Text response to send
            topic: MQTT topic to publish to
            alert: Optional audio alert configuration
            operation: Operation name for logging context
            max_retries: Maximum number of retry attempts

        Returns:
            bool: True if response was successfully published, False otherwise
        """
        response = Response(text=response_text, alert=alert)
        last_error_type = None

        # Start timing for MQTT operation metrics
        timer_id = self.metrics.start_timer("mqtt_publish")

        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(
                    "%s: Publishing to topic '%s' (attempt %d/%d)", operation, topic, attempt + 1, max_retries + 1
                )

                # Add timeout to prevent hanging
                await asyncio.wait_for(
                    self.mqtt_client.publish(
                        topic=topic,
                        payload=response.model_dump_json(exclude_none=True),
                        qos=1,
                        retain=False,
                    ),
                    timeout=5.0,
                )

                self.logger.info("%s: Successfully published to topic '%s' (attempt %d)", operation, topic, attempt + 1)

                # Record successful publish
                duration = self.metrics.end_timer(timer_id)
                self.metrics.record_mqtt_event("publish", success=True, duration=duration)
                return True

            except asyncio.CancelledError:
                self.logger.warning("%s: Publishing to topic '%s' was cancelled", operation, topic)
                raise

            except TimeoutError:
                last_error_type = self.MqttErrorType.TIMEOUT
                self.logger.warning(
                    "%s: Publish timeout to topic '%s' (attempt %d/%d)", operation, topic, attempt + 1, max_retries + 1
                )

            except aiomqtt.MqttError as e:
                last_error_type = self.MqttErrorType.CONNECTION_LOST
                self.logger.error(
                    "%s: MQTT error to topic '%s' (attempt %d/%d): %s",
                    operation,
                    topic,
                    attempt + 1,
                    max_retries + 1,
                    e,
                )

            except Exception as e:
                last_error_type = self.MqttErrorType.PUBLISH_FAILED
                self.logger.error(
                    "%s: Unexpected error to topic '%s' (attempt %d/%d): %s",
                    operation,
                    topic,
                    attempt + 1,
                    max_retries + 1,
                    e,
                    exc_info=True,
                )

            # Exponential backoff before retry (skip on last attempt)
            if attempt < max_retries:
                # Exponential backoff: 1s, 2s, 4s, but capped at 10s to prevent excessive delays
                delay = min(2**attempt, 10)
                self.logger.debug("%s: Retrying in %.1f seconds", operation, delay)
                await asyncio.sleep(delay)

        # All retries failed - handle gracefully
        duration = self.metrics.end_timer(timer_id)
        self.metrics.record_mqtt_event("publish", success=False, duration=duration)
        self.logger.error(
            "%s: All retry attempts failed for topic '%s'. Error type: %s. Response: '%.100s'",
            operation,
            topic,
            last_error_type.value if last_error_type else "unknown",
            response_text,
        )
        return False

    # AIDEV-NOTE: Enhanced task management with lifecycle monitoring and cleanup
    def add_task(self, coro: Any, name: str | None = None, **metadata: Any) -> asyncio.Task[Any]:
        """Add a task with monitoring and lifecycle management.

        Args:
            coro: Coroutine to execute as a background task
            name: Optional name for the task (defaults to coroutine name)
            **metadata: Additional metadata for monitoring and debugging

        Returns:
            asyncio.Task: Created task with lifecycle tracking

        Common use cases:
        - Spawn timer tasks for delayed responses
        - Background processing that shouldn't block message handling
        - Concurrent API calls or database operations

        The task is automatically tracked and cleaned up on completion.
        """
        if name is None:
            name = getattr(coro, "__name__", f"anonymous_coro_{id(coro)}")

        task = self.task_group.create_task(coro, name=f"{name}_{self._task_counter}")

        # Store task info for monitoring
        task_info = self.TaskInfo(name=name, created_at=datetime.now(), task_ref=weakref.ref(task), metadata=metadata)
        self._active_tasks[self._task_counter] = task_info

        # Add completion callback for cleanup
        task.add_done_callback(partial(self._task_completed, self._task_counter))

        # Record task creation in metrics
        self.metrics.record_task_event("created")

        self.logger.info("Added task '%s' (#%d)", name, self._task_counter)
        self._task_counter += 1
        return task

    def _task_completed(self, task_id: int, task: asyncio.Task) -> None:
        """Handle task completion and cleanup.

        Args:
            task_id: Internal task identifier
            task: Completed task
        """
        task_info = self._active_tasks.pop(task_id, None)
        if not task_info:
            return

        duration = datetime.now() - task_info.created_at
        duration_seconds = duration.total_seconds()

        if task.exception():
            # Record task failure in metrics
            self.metrics.record_task_event("failed", duration=duration_seconds)

            self.logger.error(
                "Task '%s' (#%d) failed after %s: %s",
                task_info.name,
                task_id,
                duration,
                task.exception(),
                exc_info=task.exception(),
            )
        else:
            # Record task completion in metrics
            self.metrics.record_task_event("completed", duration=duration_seconds)

            self.logger.debug("Task '%s' (#%d) completed successfully after %s", task_info.name, task_id, duration)

    def get_active_task_count(self) -> int:
        """Get number of currently active tasks."""
        return len(self._active_tasks)

    def get_task_stats(self) -> dict[str, Any]:
        """Get comprehensive task statistics for monitoring.

        Returns:
            Dict containing task statistics and active task details
        """
        return {
            "active_count": len(self._active_tasks),
            "total_created": self._task_counter,
            "active_tasks": [
                {
                    "id": task_id,
                    "name": info.name,
                    "age_seconds": (datetime.now() - info.created_at).total_seconds(),
                    "metadata": info.metadata,
                }
                for task_id, info in self._active_tasks.items()
            ],
        }

    @property
    async def global_skill_id(self) -> UUID:
        """Get the skill's UUID from the database (cached).

        Lazily loads the skill UUID on first access and caches it for subsequent calls.
        This property ensures the skill is registered in the database.

        Returns:
            UUID of the skill in the database

        Raises:
            RuntimeError: If skill registration fails
        """
        if self._global_skill_id is None:
            await self.ensure_skill_registered()
        return self._global_skill_id  # type: ignore[return-value]

    # AIDEV-NOTE: Device Registry Methods - All skills participate in global device registry
    async def ensure_skill_registered(self) -> None:
        """Ensure this skill is registered in the database (idempotent).

        Registers the skill if it doesn't exist and caches its UUID for subsequent operations.
        This method is called automatically during skill_preparations().

        Raises:
            RuntimeError: If database operation fails
        """
        try:
            async with AsyncSession(self.engine) as session:
                skill = await Skill.ensure_exists(session, self.config_obj.skill_id)
                self._global_skill_id = skill.id
                self.logger.info("Skill registered in database: %s (UUID: %s)", skill.name, skill.id)
        except Exception as e:
            self.logger.error("Failed to register skill: %s", e, exc_info=True)
            raise RuntimeError(f"Skill registration failed: {e}") from e

    async def ensure_device_types_registered(self) -> None:
        """Ensure all device types in supported_device_types are registered (idempotent).

        Registers any missing device types in the database. This method is called
        automatically during skill_preparations().

        Raises:
            RuntimeError: If database operation fails
        """
        if not self.supported_device_types:
            self.logger.debug("No device types to register")
            return

        try:
            async with AsyncSession(self.engine) as session:
                for device_type_name in self.supported_device_types:
                    device_type = await DeviceType.ensure_exists(session, device_type_name)
                    self.logger.info("Device type registered: %s (UUID: %s)", device_type.name, device_type.id)
        except Exception as e:
            self.logger.error("Failed to register device types: %s", e, exc_info=True)
            raise RuntimeError(f"Device type registration failed: {e}") from e

    async def register_device(
        self,
        device_type: str,
        name: str,
        pattern: list[str],
        room: str | None = None,
        device_attributes: dict[str, Any] | None = None,
    ) -> UUID:
        """Register a new device in the global device registry.

        If a device with the same name and pattern already exists for this skill,
        logs a warning and returns the existing device ID instead of creating a duplicate.

        Args:
            device_type: Device type name (must be in supported_device_types)
            name: Human-readable device name
            pattern: List of pattern strings for natural language matching
            room: Optional room name where device is located
            device_attributes: Optional skill-specific metadata (MQTT paths, templates, etc.)

        Returns:
            UUID of the created or existing device

        Raises:
            ValueError: If device_type not in supported_device_types
            RuntimeError: If database operation fails
        """
        if device_type not in self.supported_device_types:
            raise ValueError(
                f"Device type '{device_type}' not in supported_device_types: {self.supported_device_types}"
            )

        try:
            async with AsyncSession(self.engine) as session:
                # Get device type UUID
                device_type_obj = await DeviceType.get_by_name(session, device_type)
                if device_type_obj is None:
                    raise RuntimeError(f"Device type '{device_type}' not found in database")

                # Check for duplicate device
                existing_device = await self._find_duplicate_device(session, name, pattern)
                if existing_device:
                    self.logger.warning(
                        "Device '%s' with pattern %s already exists (UUID: %s). Returning existing device.",
                        name,
                        pattern,
                        existing_device.id,
                    )
                    return existing_device.id

                # Get room UUID if specified
                room_id = None
                if room:
                    room_obj = await Room.get_by_name(session, room)
                    if room_obj:
                        room_id = room_obj.id
                    else:
                        self.logger.warning("Room '%s' not found, device will have no room", room)

                # Create device
                device = GlobalDevice(
                    device_type_id=device_type_obj.id,
                    name=name,
                    pattern=pattern,
                    room_id=room_id,
                    skill_id=await self.global_skill_id,
                    device_attributes=device_attributes,
                )
                session.add(device)
                await session.commit()
                await session.refresh(device)

                self.logger.info("Device registered: %s (UUID: %s)", name, device.id)

                # Notify intent engine
                await self.publish_device_update()

                # Refresh local device cache
                self.global_devices = await self.get_skill_devices()

                return device.id

        except Exception as e:
            self.logger.error("Failed to register device '%s': %s", name, e, exc_info=True)
            raise RuntimeError(f"Device registration failed: {e}") from e

    async def _handle_device_update(self) -> None:
        """Handle device update notification by refreshing device cache.

        This method is called when a device update message is received on the
        device_update_topic. It refreshes the device cache by calling get_skill_devices().

        This allows external systems to notify skills when devices have been modified,
        enabling skills to react to changes without actively polling the database.
        """
        try:
            self.logger.debug("Received device update notification, refreshing device cache")
            # Trigger cache refresh and update stored devices
            self.global_devices = await self.get_skill_devices()
            self.logger.info("Device cache refreshed: %d devices loaded", len(self.global_devices))
        except Exception as e:
            self.logger.error("Error handling device update: %s", e, exc_info=True)

    async def get_skill_devices(self) -> list:
        """Get all devices belonging to this skill with relationships eagerly loaded.

        By default, eagerly loads room, device_type, and skill relationships to prevent
        detached instance errors when accessing them after the session closes.

        Skills can override this method to customize loading behavior if needed.

        Returns:
            List of GlobalDevice instances with relationships loaded, or empty list on error
        """
        try:
            async with AsyncSession(self.engine) as session:
                statement = (
                    select(GlobalDevice)
                    .where(GlobalDevice.skill_id == await self.global_skill_id)
                    .options(
                        selectinload(GlobalDevice.room),  # type: ignore[arg-type]
                        selectinload(GlobalDevice.device_type),  # type: ignore[arg-type]
                        selectinload(GlobalDevice.skill),  # type: ignore[arg-type]
                    )
                )
                result = await session.exec(statement)
                return list(result.all())

        except Exception as e:
            self.logger.error("Failed to get skill devices: %s", e, exc_info=True)
            return []

    async def _find_duplicate_device(
        self,
        session: AsyncSession,
        name: str,
        pattern: list[str],
    ) -> GlobalDevice | None:
        """Find existing device with same name and pattern for this skill.

        Args:
            session: Database session
            name: Device name to check
            pattern: Pattern list to check (exact match)

        Returns:
            Matching GlobalDevice or None if no duplicate found
        """
        statement = select(GlobalDevice).where(
            GlobalDevice.skill_id == await self.global_skill_id,
            GlobalDevice.name == name,
            GlobalDevice.pattern == pattern,  # SQLModel/PostgreSQL array equality
        )
        result = await session.exec(statement)
        return result.first()

    async def publish_device_update(self) -> None:
        """Publish device update notification to MQTT.

        Notifies the intent engine to refresh its device cache when devices
        are added, updated, or removed. Publishes to the device_update_topic
        configured in SkillConfig.
        """
        try:
            await self.mqtt_client.publish(
                self.config_obj.device_update_topic,
                payload=b"",  # Empty payload, intent engine just needs the signal
            )
            self.logger.debug("Published device update notification")
        except Exception as e:
            self.logger.error("Failed to publish device update notification: %s", e, exc_info=True)
