import unittest
import uuid
from unittest.mock import AsyncMock, Mock, patch

from private_assistant_commons import messages, skill_config
from private_assistant_commons.base_skill import BaseSkill


# Concrete subclass of BaseSkill for testing
class TestSkill(BaseSkill):
    async def calculate_certainty(self, intent_analysis_result: messages.IntentAnalysisResult) -> float:
        return 1.0  # Simplified certainty calculation for testing

    async def process_request(self, intent_analysis_result: messages.IntentAnalysisResult) -> None:
        pass  # Simplified processing logic for testing


class TestBaseSkill(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_mqtt_client = AsyncMock()
        self.task_group = AsyncMock()
        self.mock_config = Mock(spec=skill_config.SkillConfig)
        self.mock_config.client_id = "test_skill"
        self.mock_config.intent_analysis_result_topic = "test/intent_result"
        self.mock_config.broadcast_topic = "test/broadcast"
        self.mock_config.mqtt_server_host = "localhost"
        self.mock_config.mqtt_server_port = 1883

        # Instantiate the concrete subclass instead of BaseSkill
        self.skill = TestSkill(
            config_obj=self.mock_config, mqtt_client=self.mock_mqtt_client, task_group=self.task_group
        )

    @patch("private_assistant_commons.messages.IntentAnalysisResult")
    async def test_handle_client_request_message_valid(self, MockIntentAnalysisResult):
        mock_payload = '{"id": "12345678-1234-5678-1234-567812345678"}'
        mock_result = MockIntentAnalysisResult.model_validate_json.return_value
        mock_result.id = uuid.UUID("12345678-1234-5678-1234-567812345678")

        await self.skill.handle_client_request_message(mock_payload)

        MockIntentAnalysisResult.model_validate_json.assert_called_once_with(mock_payload)
        self.assertIn(mock_result.id, self.skill.intent_analysis_results)

    @patch("private_assistant_commons.base_skill.logger")
    async def test_handle_client_request_message_invalid(self, mock_logger):
        invalid_payload = '{"invalid": "json"}'

        await self.skill.handle_client_request_message(invalid_payload)

        mock_logger.error.assert_called_once_with("Error validating client request message: %s", unittest.mock.ANY)

    @patch("private_assistant_commons.base_skill.logger")
    async def test_listen_to_messages_valid(self, mock_logger):
        mock_message = Mock()
        mock_message.topic.matches.return_value = True
        mock_message.payload = b'{"id": "12345678-1234-5678-1234-567812345678"}'

        # Create an async iterable mock for client.messages
        async def async_generator():
            yield mock_message

        mock_mqtt_client = Mock()
        mock_mqtt_client.messages = async_generator()

        with patch.object(self.skill, "handle_client_request_message") as mock_handle_client_request:
            await self.skill.listen_to_messages(mock_mqtt_client)
            mock_handle_client_request.assert_called_once_with('{"id": "12345678-1234-5678-1234-567812345678"}')

    async def test_add_text_to_output_topic(self):
        mock_request = Mock(spec=messages.ClientRequest)
        mock_request.output_topic = "test/output"
        response_text = "Test response"

        await self.skill.add_text_to_output_topic(response_text, mock_request)
        self.mock_mqtt_client.publish.assert_called_once_with(
            topic=mock_request.output_topic,
            payload=response_text,
            qos=2,
            retain=False,
        )

    async def test_broadcast_text(self):
        response_text = "Broadcast message"
        await self.skill.broadcast_text(response_text)
        self.mock_mqtt_client.publish.assert_called_once_with(
            topic=self.mock_config.broadcast_topic,
            payload=response_text,
            qos=1,
            retain=False,
        )
