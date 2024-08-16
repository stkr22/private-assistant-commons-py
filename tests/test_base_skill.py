import unittest
import uuid
from unittest.mock import Mock, patch

from private_assistant_commons import BaseSkill, messages, skill_config


# Concrete subclass of BaseSkill for testing
class TestSkill(BaseSkill):
    def calculate_certainty(self, intent_analysis_result: messages.IntentAnalysisResult) -> float:
        return 1.0  # Simplified certainty calculation for testing

    def process_request(self, intent_analysis_result: messages.IntentAnalysisResult) -> None:
        pass  # Simplified processing logic for testing


class TestBaseSkill(unittest.TestCase):
    def setUp(self):
        self.mock_mqtt_client = Mock()
        self.mock_config = Mock(spec=skill_config.SkillConfig)
        self.mock_config.client_id = "test_skill"
        self.mock_config.feedback_topic = "test/feedback"
        self.mock_config.intent_analysis_result_topic = "test/intent_result"
        self.mock_config.certainty_topic = "test/certainty"
        self.mock_config.broadcast_topic = "test/broadcast"
        self.mock_config.register_topic = "test/register"
        self.mock_config.mqtt_server_host = "localhost"
        self.mock_config.mqtt_server_port = 1883
        self.mock_config.registration_interval = 500.0

        # Instantiate the concrete subclass instead of BaseSkill
        self.skill = TestSkill(config_obj=self.mock_config, mqtt_client=self.mock_mqtt_client)

    @patch("private_assistant_commons.messages.IntentAnalysisResult")
    @patch("private_assistant_commons.messages.SkillCertainty")
    def test_handle_client_request_message_valid(self, MockSkillCertainty, MockIntentAnalysisResult):
        mock_payload = '{"id": "12345678-1234-5678-1234-567812345678"}'
        mock_result = MockIntentAnalysisResult.model_validate_json.return_value
        mock_result.id = uuid.UUID("12345678-1234-5678-1234-567812345678")

        mock_certainty_message = MockSkillCertainty.return_value
        mock_certainty_message.model_dump_json.return_value = (
            '{"message_id":"12345678-1234-5678-1234-567812345678","certainty":1.0,"skill_id":"test_skill"}'
        )

        self.skill.handle_client_request_message(mock_payload)

        MockSkillCertainty.assert_called_once_with(
            message_id=mock_result.id,
            certainty=1.0,
            skill_id=self.mock_config.client_id,
        )
        self.mock_mqtt_client.publish.assert_called_once_with(
            self.mock_config.certainty_topic,
            mock_certainty_message.model_dump_json(),
            qos=1,
        )

    @patch("private_assistant_commons.base_skill.logger")
    def test_handle_client_request_message_invalid(self, mock_logger):
        invalid_payload = '{"invalid": "json"}'

        self.skill.handle_client_request_message(invalid_payload)

        mock_logger.error.assert_called_once_with("Error validating client request message: %s", unittest.mock.ANY)

    def test_handle_feedback_message_valid(self):
        message_id = str(uuid.uuid4())
        mock_result = Mock(spec=messages.IntentAnalysisResult)
        mock_result.id = uuid.UUID(message_id)
        self.skill.intent_analysis_results[mock_result.id] = mock_result

        with patch.object(self.skill, "process_request") as mock_process_request:
            self.skill.handle_feedback_message(message_id)
            mock_process_request.assert_called_once_with(mock_result)

    @patch("private_assistant_commons.base_skill.logger")
    def test_handle_feedback_message_invalid(self, mock_logger):
        invalid_message_id = "not-a-uuid"

        self.skill.handle_feedback_message(invalid_message_id)

        mock_logger.error.assert_called_once_with("Feedback message_id is not a UUID: %s", invalid_message_id)

    def test_add_text_to_output_topic(self):
        mock_request = Mock(spec=messages.ClientRequest)
        mock_request.output_topic = "test/output"
        response_text = "Test response"

        self.skill.add_text_to_output_topic(response_text, mock_request)
        self.mock_mqtt_client.publish.assert_called_once_with(
            mock_request.output_topic,
            response_text,
            qos=2,
        )

    def test_broadcast_text(self):
        response_text = "Broadcast message"
        self.skill.broadcast_text(response_text)
        self.mock_mqtt_client.publish.assert_called_once_with(
            self.mock_config.broadcast_topic,
            response_text,
            qos=1,
        )

    @patch("threading.Timer")
    @patch("private_assistant_commons.messages.SkillRegistration")
    def test_register_skill(self, MockSkillRegistration, MockTimer):
        self.skill.register_skill()

        MockSkillRegistration.assert_called_once_with(
            skill_id=self.mock_config.client_id,
            feedback_topic=self.mock_config.feedback_topic,
        )
        self.mock_mqtt_client.publish.assert_called_once_with(
            self.mock_config.register_topic,
            MockSkillRegistration.return_value.model_dump_json(),
            qos=1,
        )
        MockTimer.assert_called_once_with(self.mock_config.registration_interval, self.skill.register_skill)
        self.assertTrue(self.skill.registration_timer.daemon)

    def test_shutdown(self):
        self.skill.registration_timer = Mock()
        self.skill.shutdown()

        self.skill.registration_timer.cancel.assert_called_once()
        self.mock_mqtt_client.disconnect.assert_called_once()

    @patch.object(TestSkill, "register_skill")
    @patch.object(TestSkill, "shutdown")
    def test_run(self, mock_shutdown, mock_register_skill):
        with patch.object(self.mock_mqtt_client, "loop_forever", side_effect=Exception("Forced exit")):
            with self.assertRaises(Exception, msg="Forced exit"):
                self.skill.run()

        self.mock_mqtt_client.connect.assert_called_once_with(
            self.mock_config.mqtt_server_host,
            self.mock_config.mqtt_server_port,
            60,
        )
        mock_register_skill.assert_called_once()
        mock_shutdown.assert_called_once()
