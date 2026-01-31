import logging
import unittest
import uuid
from unittest.mock import AsyncMock, Mock, patch

from sqlalchemy.ext.asyncio import create_async_engine

from private_assistant_commons import intent, skill_config
from private_assistant_commons.base_skill import BaseSkill
from private_assistant_commons.database import Skill
from private_assistant_commons.messages import Alert, ClientRequest, Response


# Concrete subclass of BaseSkill for testing
class ConcreteTestSkill(BaseSkill):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Configure supported intents with per-intent confidence thresholds
        self.supported_intents = {
            intent.IntentType.DEVICE_ON: 0.8,
            intent.IntentType.DEVICE_OFF: 0.8,
        }

    async def process_request(self, intent_request: intent.IntentRequest) -> None:
        pass  # Simplified processing logic for testing

    async def skill_preparations(self) -> None:
        """Skip database initialization in tests."""
        # Override to prevent database operations during tests
        # Database operations should be tested separately in database-specific tests


# Concrete subclass with help text for testing help text functionality
class SkillWithHelpText(BaseSkill):
    help_text = "Test skill with help text for unit testing"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.supported_intents = {
            intent.IntentType.DEVICE_ON: 0.8,
        }

    async def process_request(self, intent_request: intent.IntentRequest) -> None:
        pass

    async def skill_preparations(self) -> None:
        """Skip database initialization in tests."""


class TestBaseSkill(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Set up test fixtures with real async engine."""
        # Create real async engine for proper session management
        # SQLite doesn't support ARRAY types used in models, so we skip schema creation
        self.engine_async = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

        self.mock_mqtt_client = AsyncMock()
        self.task_group = AsyncMock()
        self.mock_config = Mock(spec=skill_config.SkillConfig)
        self.mock_config.client_id = "test_skill"
        self.mock_config.skill_id = "test_skill"
        self.mock_config.intent_analysis_result_topic = "test/intent_result"
        self.mock_config.broadcast_topic = "test/broadcast"
        self.mock_config.intent_cache_size = 1000
        self.mock_logger = Mock(logging.Logger)
        self.default_alert = Alert(play_before=True)

        # Instantiate the concrete subclass with real engine
        # Tests can use real async sessions when needed
        self.skill = ConcreteTestSkill(
            config_obj=self.mock_config,
            mqtt_client=self.mock_mqtt_client,
            task_group=self.task_group,
            engine=self.engine_async,
            logger=self.mock_logger,
        )

    async def asyncTearDown(self):
        """Clean up engine after each test."""
        await self.engine_async.dispose()

    @patch("private_assistant_commons.intent.IntentRequest")
    async def test_handle_client_request_message_valid(self, mock_intent_request):
        mock_payload = '{"id": "12345678-1234-5678-1234-567812345678"}'
        mock_result = mock_intent_request.model_validate_json.return_value
        mock_result.id = uuid.UUID("12345678-1234-5678-1234-567812345678")

        await self.skill.handle_client_request_message(mock_payload)

        mock_intent_request.model_validate_json.assert_called_once_with(mock_payload)

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

    async def test_listen_to_messages_device_update(self):
        """Test that device update messages are routed to _handle_device_update."""
        # Set up device_update_topic on mock config
        self.mock_config.device_update_topic = "test/device_update"

        # Create a mock message that matches the device update topic
        mock_message = Mock()
        mock_message.topic.matches.side_effect = lambda topic: topic == "test/device_update"
        mock_message.payload = b""

        # Create an async iterable mock for client.messages
        async def async_generator():
            yield mock_message

        mock_mqtt_client = Mock()
        mock_mqtt_client.messages = async_generator()

        # Mock the add_task method to capture the spawned task
        with patch.object(self.skill, "add_task") as mock_add_task:
            await self.skill.listen_to_messages(mock_mqtt_client)

            # Verify that add_task was called once for device update
            mock_add_task.assert_called_once()

            # Get the coroutine that was passed to add_task
            called_coro = mock_add_task.call_args[0][0]

            # Execute the coroutine and verify it calls get_skill_devices
            with patch.object(self.skill, "get_skill_devices", new_callable=AsyncMock) as mock_get_devices:
                mock_get_devices.return_value = []
                await called_coro
                # Verify that get_skill_devices was called to refresh the cache
                mock_get_devices.assert_called_once()

    async def test_handle_device_update(self):
        """Test that _handle_device_update refreshes the device cache."""
        # Mock get_skill_devices to return a list of devices
        mock_devices = [Mock(), Mock(), Mock()]

        with patch.object(self.skill, "get_skill_devices", new_callable=AsyncMock) as mock_get_devices:
            mock_get_devices.return_value = mock_devices

            # Call the handler
            await self.skill._handle_device_update()

            # Verify that get_skill_devices was called
            mock_get_devices.assert_called_once()

            # Verify that global_devices was updated
            self.assertEqual(self.skill.global_devices, mock_devices)

    async def test_add_text_to_output_topic_with_alert(self):
        mock_request = Mock(spec=ClientRequest)
        mock_request.output_topic = "test/output"
        response_text = "Test response"

        # Call the new method with default alert options
        await self.skill.publish_with_alert(response_text, client_request=mock_request)

        # Build the expected payload
        expected_alert = self.skill.default_alert
        expected_payload = Response(text=response_text, alert=expected_alert).model_dump_json()

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
        expected_payload = Response(text=response_text, alert=expected_alert).model_dump_json()

        self.mock_mqtt_client.publish.assert_called_once_with(
            topic=self.mock_config.broadcast_topic,
            payload=expected_payload,
            qos=1,
            retain=False,
        )

    async def test_add_text_to_output_topic_with_custom_alert(self):
        mock_request = Mock(spec=ClientRequest)
        mock_request.output_topic = "test/output"
        response_text = "Test response"

        # Custom alert options
        custom_alert = Alert(play_before=False, play_after=True, sound="custom_sound")

        # Call the new method with custom alert
        await self.skill.publish_with_alert(response_text, client_request=mock_request, alert=custom_alert)

        # Build the expected payload
        expected_payload = Response(text=response_text, alert=custom_alert).model_dump_json()

        self.mock_mqtt_client.publish.assert_called_once_with(
            topic=mock_request.output_topic,
            payload=expected_payload,
            qos=1,
            retain=False,
        )

    async def test_help_text_class_attribute(self):
        """Test that help_text class attribute is accessible."""
        # Skill without help text should have None
        self.assertIsNone(ConcreteTestSkill.help_text)
        self.assertIsNone(self.skill.help_text)

        # Skill with help text should have the defined value
        self.assertEqual(SkillWithHelpText.help_text, "Test skill with help text for unit testing")

        # Create an instance and verify the help text is accessible
        skill_with_help = SkillWithHelpText(
            config_obj=self.mock_config,
            mqtt_client=self.mock_mqtt_client,
            task_group=self.task_group,
            engine=self.engine_async,
            logger=self.mock_logger,
        )
        self.assertEqual(skill_with_help.help_text, "Test skill with help text for unit testing")

    async def test_ensure_skill_registered_uses_class_help_text(self):
        """Test that ensure_skill_registered uses class-level help_text when no explicit help_text is provided."""
        skill_with_help = SkillWithHelpText(
            config_obj=self.mock_config,
            mqtt_client=self.mock_mqtt_client,
            task_group=self.task_group,
            engine=self.engine_async,
            logger=self.mock_logger,
        )

        # Mock Skill.ensure_exists to capture the arguments
        with patch.object(Skill, "ensure_exists", new_callable=AsyncMock) as mock_ensure_exists:
            mock_skill = Mock()
            mock_skill.id = uuid.uuid4()
            mock_ensure_exists.return_value = mock_skill

            # Call ensure_skill_registered without explicit help_text
            await skill_with_help.ensure_skill_registered()

            # Verify that Skill.ensure_exists was called with the class-level help_text
            mock_ensure_exists.assert_called_once()
            call_args = mock_ensure_exists.call_args
            # The third argument should be help_text
            self.assertEqual(call_args.kwargs.get("help_text"), "Test skill with help text for unit testing")

    async def test_ensure_skill_registered_explicit_help_text_overrides(self):
        """Test that explicit help_text parameter overrides class-level help_text."""
        skill_with_help = SkillWithHelpText(
            config_obj=self.mock_config,
            mqtt_client=self.mock_mqtt_client,
            task_group=self.task_group,
            engine=self.engine_async,
            logger=self.mock_logger,
        )

        # Mock Skill.ensure_exists to capture the arguments
        with patch.object(Skill, "ensure_exists", new_callable=AsyncMock) as mock_ensure_exists:
            mock_skill = Mock()
            mock_skill.id = uuid.uuid4()
            mock_ensure_exists.return_value = mock_skill

            # Call ensure_skill_registered with explicit help_text
            explicit_help = "Override help text"
            await skill_with_help.ensure_skill_registered(help_text=explicit_help)

            # Verify that Skill.ensure_exists was called with the explicit help_text
            mock_ensure_exists.assert_called_once()
            call_args = mock_ensure_exists.call_args
            self.assertEqual(call_args.kwargs.get("help_text"), explicit_help)

    async def test_ensure_skill_registered_no_help_text(self):
        """Test that ensure_skill_registered works with skills that have no help_text (backwards compatibility)."""
        # Mock Skill.ensure_exists to capture the arguments
        with patch.object(Skill, "ensure_exists", new_callable=AsyncMock) as mock_ensure_exists:
            mock_skill = Mock()
            mock_skill.id = uuid.uuid4()
            mock_ensure_exists.return_value = mock_skill

            # Call ensure_skill_registered without explicit help_text on a skill without class-level help_text
            await self.skill.ensure_skill_registered()

            # Verify that Skill.ensure_exists was called with None for help_text
            mock_ensure_exists.assert_called_once()
            call_args = mock_ensure_exists.call_args
            self.assertEqual(call_args.kwargs.get("help_text"), None)
