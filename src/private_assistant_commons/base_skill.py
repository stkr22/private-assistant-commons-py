import logging
import threading
import uuid
from collections.abc import Callable

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from private_assistant_commons import messages, skill_config

logger = logging.getLogger(__name__)


class BaseSkill:
    def __init__(
        self,
        config_obj: skill_config.SkillConfig,
        mqtt_client: mqtt.Client,
    ) -> None:
        self.config_obj: skill_config.SkillConfig = config_obj
        mqtt_client.on_connect, mqtt_client.on_message = self.get_mqtt_functions()
        self.mqtt_client: mqtt.Client = mqtt_client
        self.lock: threading.RLock = threading.RLock()
        self.intent_analysis_results: dict[uuid.UUID, messages.IntentAnalysisResult] = {}

    def get_mqtt_functions(self) -> tuple[Callable, Callable]:
        def on_connect(mqtt_client: mqtt.Client, user_data, flags, rc: int, properties):
            logger.info("Connected with result code %s", rc)
            mqtt_client.subscribe(
                [
                    (self.config_obj.feedback_topic, mqtt.SubscribeOptions(qos=1)),
                    (
                        self.config_obj.intent_analysis_result_topic,
                        mqtt.SubscribeOptions(qos=1),
                    ),
                ]
            )

        def on_message(mqtt_client: mqtt.Client, user_data, msg: mqtt.MQTTMessage):
            logger.debug("Received message %s", msg)
            if msg.topic == self.config_obj.feedback_topic:
                self.handle_feedback_message(msg.payload.decode("utf-8"))
            elif msg.topic == self.config_obj.intent_analysis_result_topic:
                self.handle_client_request_message(msg.payload.decode("utf-8"))

        return on_connect, on_message

    def calculate_certainty(self, intent_analysis_result: messages.IntentAnalysisResult) -> float:
        raise NotImplementedError

    def handle_client_request_message(self, payload: str) -> None:
        try:
            intent_analysis_result = messages.IntentAnalysisResult.model_validate_json(payload)
            self.intent_analysis_results[intent_analysis_result.id] = intent_analysis_result
            certainty = self.calculate_certainty(intent_analysis_result)
            certainty_message = messages.SkillCertainty(
                message_id=intent_analysis_result.id,
                certainty=certainty,
                skill_id=self.config_obj.client_id,
            )
            self.mqtt_client.publish(
                self.config_obj.certainty_topic,
                certainty_message.model_dump_json(),
                qos=1,
            )
        except ValidationError as e:
            logger.error("Error validating client request message: %s", e)

    def handle_feedback_message(self, payload: str) -> None:
        try:
            message_id = uuid.UUID(payload)
        except ValueError:
            logger.error("Feedback message_id is not a UUID.")
        intent_analysis_result = self.intent_analysis_results.get(message_id)
        if intent_analysis_result is not None:
            self.process_request(intent_analysis_result)
        else:
            logger.error("No intent analysis result for UUID %s was found.", message_id)

    def add_text_to_output_topic(self, response_text: str, client_request: messages.ClientRequest) -> None:
        self.mqtt_client.publish(client_request.output_topic, response_text, qos=2)

    def broadcast_text(self, response_text: str) -> None:
        self.mqtt_client.publish(self.config_obj.broadcast_topic, response_text, qos=1)

    def process_request(self, intent_analysis_result: messages.IntentAnalysisResult) -> None:
        raise NotImplementedError

    def register_skill(self):
        with self.lock:
            registration_message = messages.SkillRegistration(
                skill_id=self.config_obj.client_id,
                feedback_topic=self.config_obj.feedback_topic,
            )
            self.mqtt_client.publish(
                self.config_obj.register_topic,
                registration_message.model_dump_json(),
                qos=1,
            )
            self.registration_timer = threading.Timer(self.config_obj.registration_interval, self.register_skill)
            self.registration_timer.daemon = True
            self.registration_timer.start()

    def shutdown(self):
        self.mqtt_client.disconnect()

    def run(self):
        try:
            self.mqtt_client.connect(self.config_obj.mqtt_server_host, self.config_obj.mqtt_server_port, 60)
            self.register_skill()
            self.mqtt_client.loop_forever()
        finally:
            self.shutdown()
