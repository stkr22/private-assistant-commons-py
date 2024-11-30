import asyncio
import logging
import uuid
from abc import ABC, abstractmethod

import aiomqtt
from pydantic import ValidationError

from private_assistant_commons import messages, skill_config, skill_logger


class BaseSkill(ABC):
    def __init__(
        self,
        config_obj: skill_config.SkillConfig,
        mqtt_client: aiomqtt.Client,
        task_group: asyncio.TaskGroup,
        certainty_threshold: float = 0.8,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config_obj: skill_config.SkillConfig = config_obj
        self.certainty_threshold: float = certainty_threshold
        self.intent_analysis_results: dict[uuid.UUID, messages.IntentAnalysisResult] = {}
        self.mqtt_client: aiomqtt.Client = mqtt_client
        self.task_group: asyncio.TaskGroup = task_group
        self.logger = logger or skill_logger.SkillLogger.get_logger(__name__)
        self.default_alert = messages.Alert(play_before=True)

    def decode_message_payload(self, payload) -> str | None:
        """Decode the message payload if it is a suitable type."""
        if isinstance(payload, bytes) or isinstance(payload, bytearray):
            return payload.decode("utf-8")
        elif isinstance(payload, str):
            return payload
        else:
            self.logger.warning("Unexpected payload type: %s", type(payload))
            return None

    async def setup_mqtt_subscriptions(self) -> None:
        """Set up MQTT topic subscriptions for the skill."""
        await self.mqtt_client.subscribe(topic=self.config_obj.intent_analysis_result_topic, qos=1)
        self.logger.info("Subscribed to intent analysis result topic: %s", self.config_obj.intent_analysis_result_topic)

    async def skill_preparations(self) -> None:
        pass

    async def listen_to_messages(self, client: aiomqtt.Client) -> None:
        """Listen for incoming MQTT messages and handle them appropriately."""
        async for message in client.messages:
            self.logger.debug("Received message on topic %s", message.topic)

            if message.topic.matches(self.config_obj.intent_analysis_result_topic):
                payload_str = self.decode_message_payload(message.payload)
                if payload_str is not None:
                    await self.handle_client_request_message(payload_str)

    @abstractmethod
    async def calculate_certainty(self, intent_analysis_result: messages.IntentAnalysisResult) -> float:
        pass

    async def handle_client_request_message(self, payload: str) -> None:
        try:
            intent_analysis_result = messages.IntentAnalysisResult.model_validate_json(payload)
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
        pass

    async def send_response(
        self,
        response_text: str,
        client_request: messages.ClientRequest,
        alert: messages.Alert | None = None,
    ) -> None:
        """Publish a response using the new `Response` class."""
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
        """Broadcast a response using the new `Response` class."""
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

    async def publish_with_alert(
        self,
        response_text: str,
        client_request: messages.ClientRequest | None = None,
        broadcast: bool = False,
        alert: messages.Alert | None = None,
    ) -> None:
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
        """Add a new task to the task group and return it."""
        self.logger.info("Adding new task to the task group.")
        task = self.task_group.create_task(coro)
        return task
