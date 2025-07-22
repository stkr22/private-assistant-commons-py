import logging
import unittest
import uuid
from unittest.mock import AsyncMock, Mock, patch

from private_assistant_commons import messages, skill_config
from private_assistant_commons.base_skill import BaseSkill


# Concrete subclass of BaseSkill for testing
class TestSkill(BaseSkill):
    async def calculate_certainty(self, intent_analysis_result: messages.IntentAnalysisResult) -> float:  # noqa: ARG002
        return 1.0  # Simplified certainty calculation for testing

    async def process_request(self, intent_analysis_result: messages.IntentAnalysisResult) -> None:
        pass  # Simplified processing logic for testing

    async def skill_preparations(self) -> None:
        pass


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
        self.mock_config.intent_cache_size = 1000
        self.mock_logger = Mock(logging.Logger)
        self.default_alert = messages.Alert(play_before=True)

        # Instantiate the concrete subclass instead of BaseSkill
        self.skill = TestSkill(
            config_obj=self.mock_config,
            mqtt_client=self.mock_mqtt_client,
            task_group=self.task_group,
            logger=self.mock_logger,
        )

    @patch("private_assistant_commons.messages.IntentAnalysisResult")
    async def test_handle_client_request_message_valid(self, mock_intent_analysis_result):
        mock_payload = '{"id": "12345678-1234-5678-1234-567812345678"}'
        mock_result = mock_intent_analysis_result.model_validate_json.return_value
        mock_result.id = uuid.UUID("12345678-1234-5678-1234-567812345678")

        await self.skill.handle_client_request_message(mock_payload)

        mock_intent_analysis_result.model_validate_json.assert_called_once_with(mock_payload)
        self.assertIn(mock_result.id, self.skill.intent_analysis_results)

    async def test_handle_client_request_message_invalid(self):
        invalid_payload = '{"invalid": "json"}'

        await self.skill.handle_client_request_message(invalid_payload)

        self.mock_logger.error.assert_called_once_with("Error validating client request message: %s", unittest.mock.ANY)

    async def test_listen_to_messages_valid(self):
        mock_message = Mock()
        mock_message.topic.matches.return_value = True
        mock_message.payload = b'{"id": "12345678-1234-5678-1234-567812345678"}'

        # Create an async iterable mock for client.messages
        async def async_generator():
            yield mock_message

        mock_mqtt_client = Mock()
        mock_mqtt_client.messages = async_generator()

        # Mock the add_task method to capture the spawned task
        with patch.object(self.skill, "add_task") as mock_add_task:
            await self.skill.listen_to_messages(mock_mqtt_client)
            
            # Verify that add_task was called once
            mock_add_task.assert_called_once()
            
            # Get the coroutine that was passed to add_task and execute it
            called_coro = mock_add_task.call_args[0][0]
            
            # Execute the coroutine to test the message handling
            with patch.object(self.skill, "handle_client_request_message") as mock_handle_client_request:
                await called_coro
                mock_handle_client_request.assert_called_once_with('{"id": "12345678-1234-5678-1234-567812345678"}')

    async def test_add_text_to_output_topic_with_alert(self):
        mock_request = Mock(spec=messages.ClientRequest)
        mock_request.output_topic = "test/output"
        response_text = "Test response"

        # Call the new method with default alert options
        await self.skill.publish_with_alert(response_text, client_request=mock_request)

        # Build the expected payload
        expected_alert = self.skill.default_alert
        expected_payload = messages.Response(text=response_text, alert=expected_alert).model_dump_json()

        self.mock_mqtt_client.publish.assert_called_once_with(
            topic=mock_request.output_topic,
            payload=expected_payload,
            qos=1,
            retain=False,
        )

    async def test_broadcast_text_with_alert(self):
        response_text = "Broadcast message"

        # Call the new method with broadcast set to True
        await self.skill.publish_with_alert(response_text, broadcast=True)

        # Build the expected payload
        expected_alert = self.skill.default_alert
        expected_payload = messages.Response(text=response_text, alert=expected_alert).model_dump_json()

        self.mock_mqtt_client.publish.assert_called_once_with(
            topic=self.mock_config.broadcast_topic,
            payload=expected_payload,
            qos=1,
            retain=False,
        )

    async def test_add_text_to_output_topic_with_custom_alert(self):
        mock_request = Mock(spec=messages.ClientRequest)
        mock_request.output_topic = "test/output"
        response_text = "Test response"

        # Custom alert options
        custom_alert = messages.Alert(play_before=False, play_after=True, sound="custom_sound")

        # Call the new method with custom alert
        await self.skill.publish_with_alert(response_text, client_request=mock_request, alert=custom_alert)

        # Build the expected payload
        expected_payload = messages.Response(text=response_text, alert=custom_alert).model_dump_json()

        self.mock_mqtt_client.publish.assert_called_once_with(
            topic=mock_request.output_topic,
            payload=expected_payload,
            qos=1,
            retain=False,
        )

    async def test_broadcast_text_with_custom_alert(self):
        response_text = "Broadcast message"

        # Custom alert options
        custom_alert = messages.Alert(play_before=True, play_after=False, sound="custom_broadcast_sound")

        # Call the new method with broadcast set to True and custom alert
        await self.skill.publish_with_alert(
            response_text,
            broadcast=True,
            alert=custom_alert,
        )

        # Build the expected payload
        expected_payload = messages.Response(text=response_text, alert=custom_alert).model_dump_json()

        self.mock_mqtt_client.publish.assert_called_once_with(
            topic=self.mock_config.broadcast_topic,
            payload=expected_payload,
            qos=1,
            retain=False,
        )
