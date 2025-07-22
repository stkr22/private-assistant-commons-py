import asyncio
import logging
from abc import ABC, abstractmethod
from collections import OrderedDict

import aiomqtt
from pydantic import ValidationError

from private_assistant_commons import messages, skill_config, skill_logger


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
        self.intent_analysis_results: BoundedDict = BoundedDict(
            max_size=config_obj.intent_cache_size
        )
        self._results_lock = asyncio.Lock()  # Thread safety for concurrent access
        self.mqtt_client: aiomqtt.Client = mqtt_client
        self.task_group: asyncio.TaskGroup = task_group
        self.logger = logger or skill_logger.SkillLogger.get_logger(__name__)
        self.default_alert = messages.Alert(play_before=True)

    def decode_message_payload(self, payload) -> str | None:
        """Decode MQTT message payload to string.
        
        Args:
            payload: Raw MQTT payload (bytes, bytearray, or str)
            
        Returns:
            Decoded string or None if payload type is unsupported
        """
        """Decode the message payload if it is a suitable type."""
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
        """Set up MQTT topic subscriptions for the skill."""
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
        """Listen for incoming MQTT messages and handle them appropriately."""
        async for message in client.messages:
            self.logger.debug("Received message on topic %s", message.topic)

            if message.topic.matches(self.config_obj.intent_analysis_result_topic):
                payload_str = self.decode_message_payload(message.payload)
                if payload_str is not None:
                    # Process messages concurrently to improve throughput
                    self.add_task(self._handle_message_async(payload_str))

    @abstractmethod  
    async def calculate_certainty(self, intent_analysis_result: messages.IntentAnalysisResult) -> float:
        """Calculate confidence score for handling this request.
        
        Args:
            intent_analysis_result: Parsed voice command with extracted intents
            
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
        try:
            intent_analysis_result = messages.IntentAnalysisResult.model_validate_json(payload)
            
            # Thread-safe storage of intent analysis results
            async with self._results_lock:
                self.intent_analysis_results[intent_analysis_result.id] = intent_analysis_result

            # Calculate certainty
            certainty = await self.calculate_certainty(intent_analysis_result)
            self.logger.debug("Calculated certainty for intent: %.2f", certainty)

            # If certainty is above the threshold, process the request
            if certainty >= self.certainty_threshold:
                await self.process_request(intent_analysis_result)
            else:
                self.logger.info(
                    "Certainty (%.2f) below threshold (%.2f), skipping request.", certainty, self.certainty_threshold
                )
        except ValidationError as e:
            self.logger.error("Error validating client request message: %s", e)

    @abstractmethod
    async def process_request(self, intent_analysis_result: messages.IntentAnalysisResult) -> None:
        """Process a request that exceeded the certainty threshold.
        
        Args:
            intent_analysis_result: Validated request with extracted intents
            
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
        client_request: messages.ClientRequest,
        alert: messages.Alert | None = None,
    ) -> None:
        """Send a response to a specific client request.
        
        Args:
            response_text: Text response to send
            client_request: Original request containing output topic
            alert: Optional audio alert configuration
            
        Publishes response to the client-specific output topic for targeted delivery.
        """
        """Publish a response using the Response message model."""
        response = messages.Response(text=response_text, alert=alert)
        try:
            self.logger.debug("Publishing response as JSON to topic '%s'.", client_request.output_topic)
            await self.mqtt_client.publish(
                topic=client_request.output_topic,
                payload=response.model_dump_json(exclude_none=True),
                qos=1,
                retain=False,
            )
            self.logger.info("Published response to topic '%s'.", client_request.output_topic)
        except asyncio.CancelledError:
            self.logger.warning("Publishing to topic '%s' was cancelled.", client_request.output_topic)
            raise
        except Exception as e:
            self.logger.error(
                "Failed to publish response to topic '%s': %s", client_request.output_topic, e, exc_info=True
            )

    async def broadcast_response(
        self,
        response_text: str,
        alert: messages.Alert | None = None,
    ) -> None:
        """Broadcast a response to all connected clients.
        
        Args:
            response_text: Text response to broadcast
            alert: Optional audio alert configuration
            
        Publishes response to the global broadcast topic for system-wide announcements.
        """
        """Broadcast a response using the Response message model."""
        response = messages.Response(text=response_text, alert=alert)
        try:
            self.logger.debug("Broadcasting response as JSON to topic '%s'.", self.config_obj.broadcast_topic)
            await self.mqtt_client.publish(
                topic=self.config_obj.broadcast_topic,
                payload=response.model_dump_json(exclude_none=True),
                qos=1,
                retain=False,
            )
            self.logger.info("Broadcast response to topic '%s'.", self.config_obj.broadcast_topic)
        except asyncio.CancelledError:
            self.logger.warning("Broadcast to topic '%s' was cancelled.", self.config_obj.broadcast_topic)
            raise
        except Exception as e:
            self.logger.error(
                "Failed to broadcast response to topic '%s': %s", self.config_obj.broadcast_topic, e, exc_info=True
            )

    # AIDEV-NOTE: Convenience method that unifies send_response and broadcast_response
    async def publish_with_alert(
        self,
        response_text: str,
        client_request: messages.ClientRequest | None = None,
        broadcast: bool = False,
        alert: messages.Alert | None = None,
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
        """
        Publish a message to either the broadcast topic or a specific output topic with alert options.

        :param response_text: The text to be published.
        :param client_request: The client request object (required if not broadcasting).
        :param broadcast: Set to True to broadcast, False to publish to output topic.
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

    def add_task(self, coro) -> asyncio.Task:
        """Add a coroutine as a new task to the skill's task group.
        
        Args:
            coro: Coroutine to execute concurrently
            
        Returns:
            Created asyncio.Task
            
        Common use cases:
        - Spawn timer tasks for delayed responses
        - Background processing that shouldn't block message handling
        - Concurrent API calls or database operations
        """
        """Add a new task to the task group and return it."""
        self.logger.info("Adding new task to the task group.")
        return self.task_group.create_task(coro)
