import asyncio
import uuid
from abc import ABC, abstractmethod

import aiomqtt
from pydantic import ValidationError

from private_assistant_commons import messages, skill_config
from private_assistant_commons.skill_logger import SkillLogger

logger = SkillLogger.get_logger(__name__)


class BaseSkill(ABC):
    def __init__(
        self,
        config_obj: skill_config.SkillConfig,
        mqtt_client: aiomqtt.Client,
        task_group: asyncio.TaskGroup,
        certainty_threshold: float = 0.8,
    ) -> None:
        self.config_obj: skill_config.SkillConfig = config_obj
        self.certainty_threshold: float = certainty_threshold
        self.intent_analysis_results: dict[uuid.UUID, messages.IntentAnalysisResult] = {}
        self.mqtt_client: aiomqtt.Client = mqtt_client
        self.task_group: asyncio.TaskGroup = task_group

    @staticmethod
    def decode_message_payload(payload) -> str | None:
        """Decode the message payload if it is a suitable type."""
        if isinstance(payload, bytes) or isinstance(payload, bytearray):
            return payload.decode("utf-8")
        elif isinstance(payload, str):
            return payload
        else:
            logger.warning("Unexpected payload type: %s", type(payload))
            return None

    async def setup_subscriptions(self) -> None:
        """Set up MQTT topic subscriptions for the skill."""
        await self.mqtt_client.subscribe(topic=self.config_obj.intent_analysis_result_topic, qos=1)
        logger.info("Subscribed to intent analysis result topic: %s", self.config_obj.intent_analysis_result_topic)

    async def listen_to_messages(self, client: aiomqtt.Client) -> None:
        """Listen for incoming MQTT messages and handle them appropriately."""
        async for message in client.messages:
            logger.debug("Received message on topic %s", message.topic)

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
            logger.debug("Calculated certainty for intent: %.2f", certainty)

            # If certainty is above the threshold, process the request
            if certainty >= self.certainty_threshold:
                await self.process_request(intent_analysis_result)
            else:
                logger.info(
                    "Certainty (%.2f) below threshold (%.2f), skipping request.", certainty, self.certainty_threshold
                )
        except ValidationError as e:
            logger.error("Error validating client request message: %s", e)

    @abstractmethod
    async def process_request(self, intent_analysis_result: messages.IntentAnalysisResult) -> None:
        pass

    async def add_text_to_output_topic(self, response_text: str, client_request: messages.ClientRequest) -> None:
        """Publish a message to a specific output topic."""
        await self.mqtt_client.publish(topic=client_request.output_topic, payload=response_text, qos=2, retain=False)
        logger.info("Published message to topic '%s'.", client_request.output_topic)

    async def broadcast_text(self, response_text: str) -> None:
        """Broadcast a message to the broadcast topic."""
        await self.mqtt_client.publish(
            topic=self.config_obj.broadcast_topic, payload=response_text, qos=1, retain=False
        )
        logger.info("Broadcast message published to topic '%s'.", self.config_obj.broadcast_topic)

    async def add_task(self, coro):
        """Add a new task to the task group."""
        logger.info("Adding new task to the task group.")
        self.task_group.create_task(coro)
