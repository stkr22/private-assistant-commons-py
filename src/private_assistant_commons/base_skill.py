import logging
import re
import threading
import uuid
from collections.abc import Callable

import paho.mqtt.client as mqtt
import spacy
from pydantic import ValidationError

from private_assistant_commons import messages, skill_config

logger = logging.getLogger(__name__)


class BaseSkill:
    def __init__(
        self,
        config_obj: skill_config.SkillConfig,
        mqtt_client: mqtt.Client,
        nlp_model: spacy.language.Language,
    ) -> None:
        self.config_obj: skill_config.SkillConfig = config_obj
        self.client_request_pattern: re.Pattern = self.mqtt_pattern_to_regex(
            self.config_obj.client_request_subscription
        )
        mqtt_client.on_connect, mqtt_client.on_message = self.get_mqtt_functions()
        self.mqtt_client: mqtt.Client = mqtt_client
        self.nlp_model: spacy.language.Language = nlp_model
        self.lock: threading.RLock = threading.RLock()
        self.client_requests: dict[uuid.UUID, messages.ClientRequest] = {}

    @staticmethod
    def mqtt_pattern_to_regex(pattern: str) -> re.Pattern:
        """
        Converts MQTT topic pattern with wildcards to a regular expression.
        - '+' wildcard is replaced to match any string in a single topic level.
        - '#' wildcard is replaced to match any strings at multiple topic levels.
        """
        pattern = re.escape(pattern)
        pattern = pattern.replace(r"\+", r"[^/]+").replace(r"\#", r".*")
        return re.compile(f"^{pattern}$")

    def get_mqtt_functions(self) -> tuple[Callable, Callable]:
        def on_connect(mqtt_client: mqtt.Client, user_data, flags, rc: int, properties):
            logger.info("Connected with result code %s", rc)
            mqtt_client.subscribe(
                [
                    (self.config_obj.feedback_topic, mqtt.SubscribeOptions(qos=1)),
                    (
                        self.config_obj.client_request_subscription,
                        mqtt.SubscribeOptions(qos=1),
                    ),
                ]
            )

        def on_message(mqtt_client: mqtt.Client, user_data, msg: mqtt.MQTTMessage):
            logger.debug("Received message %s", msg)
            if msg.topic == self.config_obj.feedback_topic:
                self.handle_feedback_message(msg.payload.decode("utf-8"))
            elif self.client_request_pattern.match(msg.topic):
                self.handle_client_request_message(msg.payload.decode("utf-8"))

        return on_connect, on_message

    def calculate_certainty(self, doc: spacy.language.Doc) -> float:
        raise NotImplementedError

    def handle_client_request_message(self, payload: str) -> None:
        try:
            client_request = messages.ClientRequest.model_validate_json(payload)
            self.client_requests[client_request.id] = client_request
            certainty = self.calculate_certainty(
                self.nlp_model(text=client_request.text)
            )
            certainty_message = messages.SkillCertainty(
                message_id=client_request.id,
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
        client_request = self.client_requests.get(message_id)
        if client_request is not None:
            self.process_request(client_request)
        else:
            logger.error("No client request for UUID %s was found.", message_id)

    def add_text_to_output_topic(
        self, response_text: str, client_request: messages.ClientRequest
    ) -> None:
        self.mqtt_client.publish(client_request.output_topic, response_text, qos=2)

    def process_request(self, client_request: messages.ClientRequest) -> None:
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
            self.registration_timer = threading.Timer(
                self.config_obj.registration_interval, self.register_skill
            )
            self.registration_timer.daemon = True
            self.registration_timer.start()

    def shutdown(self):
        self.mqtt_client.disconnect()

    def run(self):
        try:
            self.mqtt_client.connect(
                self.config_obj.mqtt_server_host, self.config_obj.mqtt_server_port, 60
            )
            self.register_skill()
            self.mqtt_client.loop_forever()
        finally:
            self.shutdown()
