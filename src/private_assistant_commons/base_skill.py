from __future__ import annotations

import asyncio
import weakref
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import partial
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import logging

import aiomqtt
from pydantic import ValidationError

from private_assistant_commons import intent, skill_config, skill_logger
from private_assistant_commons.metrics import MetricsCollector


class BoundedDict(OrderedDict):
    """Thread-safe bounded dictionary with LRU eviction.

    Maintains a maximum number of entries by automatically removing
    the least recently used items when capacity is exceeded.
    """

    def __init__(self, max_size: int = 1000):
        """Initialize bounded dictionary.

        Args:
            max_size: Maximum number of entries to store
        """
        self.max_size = max_size
        super().__init__()

    def __setitem__(self, key, value):
        """Add or update an entry, maintaining size limit."""
        if key in self:
            # Move existing key to end (most recently used)
            self.move_to_end(key)
        elif len(self) >= self.max_size:
            # Remove least recently used item
            self.popitem(last=False)
        super().__setitem__(key, value)


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

    def __init__(
        self,
        config_obj: skill_config.SkillConfig,
        mqtt_client: aiomqtt.Client,
        task_group: asyncio.TaskGroup,
        certainty_threshold: float = 0.8,
        logger: logging.Logger | None = None,
    ) -> None:
        """Initialize the base skill.

        Args:
            config_obj: Configuration for MQTT topics and connection settings
            mqtt_client: Connected MQTT client for message publishing/subscribing
            task_group: TaskGroup for managing concurrent operations
            certainty_threshold: Minimum confidence score to process requests (0.0-1.0)
            logger: Optional custom logger, defaults to skill-specific logger
        """
        self.config_obj: skill_config.SkillConfig = config_obj
        self.certainty_threshold: float = certainty_threshold
        # AIDEV-NOTE: Bounded LRU cache prevents memory leaks from unbounded growth
        self.intent_requests: BoundedDict = BoundedDict(max_size=config_obj.intent_cache_size)
        self._results_lock = asyncio.Lock()  # Thread safety for concurrent access
        self.mqtt_client: aiomqtt.Client = mqtt_client
        self.task_group: asyncio.TaskGroup = task_group
        self.logger = logger or skill_logger.SkillLogger.get_logger(__name__)
        self.default_alert = intent.Alert(play_before=True)

        # AIDEV-NOTE: Task lifecycle management for monitoring and debugging
        self._active_tasks: dict[int, BaseSkill.TaskInfo] = {}
        self._task_counter = 0

        # AIDEV-NOTE: Performance metrics and observability
        self.metrics = MetricsCollector(skill_name=config_obj.client_id)

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
        voice commands for evaluation and potential handling.
        """
        await self.mqtt_client.subscribe(topic=self.config_obj.intent_analysis_result_topic, qos=1)
        self.logger.info("Subscribed to intent analysis result topic: %s", self.config_obj.intent_analysis_result_topic)

    @abstractmethod
    async def skill_preparations(self) -> None:
        """Perform skill-specific initialization after MQTT setup.

        Called after MQTT subscriptions are established. Skills should
        implement any custom setup logic here (e.g., database connections,
        external API initialization, etc.).
        """
        pass

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

    @abstractmethod
    async def calculate_certainty(self, intent_request: intent.IntentRequest) -> float:
        """Calculate confidence score for handling this request.

        Args:
            intent_request: Parsed voice command with classified intent and client request

        Returns:
            Confidence score between 0.0-1.0. Values >= certainty_threshold
            will trigger request processing.

        Implementation varies by skill:
        - Simple keyword matching (most common)
        - Complex NLP analysis
        - Pattern matching on verbs/nouns
        """
        pass

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

    # AIDEV-NOTE: Core request processing pipeline - certainty evaluation and routing
    async def handle_client_request_message(self, payload: str) -> None:
        """Process incoming intent analysis result and decide whether to handle it.

        Args:
            payload: JSON string containing IntentAnalysisResult

        Flow:
        1. Parse and validate the intent analysis result
        2. Store for potential delayed processing
        3. Calculate skill-specific certainty score
        4. Process request if certainty >= threshold
        """
        # Start timing for performance metrics
        timer_id = self.metrics.start_timer("message_processing")

        try:
            # Parse and validate the incoming JSON message
            intent_request = intent.IntentRequest.model_validate_json(payload)

            # Store result in bounded cache with thread-safe access
            # This cache is legacy from coordinator-based architecture but still used for debugging
            async with self._results_lock:
                cache_had_key = intent_request.id in self.intent_requests
                self.intent_requests[intent_request.id] = intent_request

                # Record cache metrics
                self.metrics.record_cache_event(
                    "hit" if cache_had_key else "miss", cache_size=len(self.intent_requests)
                )

            # Calculate skill-specific confidence score (implemented by each skill)
            certainty = await self.calculate_certainty(intent_request)
            self.logger.debug("Calculated certainty for intent: %.2f", certainty)

            # Distributed decision: each skill independently decides whether to handle the request
            if certainty >= self.certainty_threshold:
                await self.process_request(intent_request)
                self.metrics.record_message_processed(success=True, certainty=certainty)
            else:
                self.logger.info(
                    "Certainty (%.2f) below threshold (%.2f), skipping request.", certainty, self.certainty_threshold
                )
                self.metrics.record_message_processed(success=True, certainty=certainty)

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
        client_request: intent.ClientRequest,
        alert: intent.Alert | None = None,
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
        alert: intent.Alert | None = None,
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
        client_request: intent.ClientRequest | None = None,
        broadcast: bool = False,
        alert: intent.Alert | None = None,
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

        # AIDEV-NOTE: Enhanced error handling with retry logic and error categorization

    async def _send_response_with_retry(
        self,
        response_text: str,
        topic: str,
        alert: intent.Alert | None = None,
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
        response = intent.Response(text=response_text, alert=alert)
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
        await self._handle_publish_failure(last_error_type, operation, topic, response_text)
        return False

    async def _handle_publish_failure(
        self,
        error_type: BaseSkill.MqttErrorType | None,
        operation: str,
        topic: str,
        response_text: str,
    ) -> None:
        """Handle persistent publish failures with appropriate recovery strategies.

        Args:
            error_type: Type of error that caused the failure
            operation: Operation that failed for logging context
            topic: MQTT topic that failed
            response_text: Response text that failed to send
        """
        self.logger.error(
            "%s: All retry attempts failed for topic '%s'. Error type: %s. Response: '%.100s'",
            operation,
            topic,
            error_type.value if error_type else "unknown",
            response_text,
        )

        # Future enhancement: Could implement fallback strategies here
        # - Store failed messages for later retry
        # - Send to alternative topic
        # - Trigger reconnection logic
        # - Update skill health status

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
