"""Tests for DeviceRegistryMixin."""

import unittest
import uuid
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

from private_assistant_commons import skill_config
from private_assistant_commons.base_skill import BaseSkill
from private_assistant_commons.database import DeviceRegistryMixin, GlobalDevice


# Concrete test skill with mixin
class TestSkillWithRegistry(BaseSkill, DeviceRegistryMixin):
    """Test skill implementing DeviceRegistryMixin."""

    async def calculate_certainty(self, intent_request: Any) -> float:  # noqa: ARG002
        return 1.0

    async def process_request(self, intent_request: Any) -> None:
        pass

    async def skill_preparations(self) -> None:
        pass


class TestDeviceRegistryMixin(unittest.IsolatedAsyncioTestCase):
    """Test suite for DeviceRegistryMixin."""

    async def asyncSetUp(self):
        """Set up test fixtures."""
        # Mock dependencies
        self.mock_mqtt_client = AsyncMock()
        self.mock_task_group = AsyncMock()
        self.mock_engine = Mock()

        # Mock config
        self.mock_config = Mock(spec=skill_config.SkillConfig)
        self.mock_config.client_id = "test_skill"
        self.skill_uuid = uuid.uuid4()
        self.mock_config.skill_id = str(self.skill_uuid)  # skill_id is string UUID
        self.mock_config.intent_cache_size = 1000
        self.mock_config.device_update_topic = "assistant/global_device_update"

        # Create skill instance with mocked engine
        self.skill = TestSkillWithRegistry(
            config_obj=self.mock_config,
            mqtt_client=self.mock_mqtt_client,
            task_group=self.mock_task_group,
            engine=self.mock_engine,
        )

        # Test UUIDs
        self.device_id = uuid.uuid4()
        self.device_type_id = uuid.uuid4()
        self.room_id = uuid.uuid4()

    @patch("private_assistant_commons.database.device_registry.AsyncSession")
    async def test_register_device_success(self, mock_session_class):
        """Test successful device registration."""
        # Mock session and database operations
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        # Call register_device
        _device = await self.skill.register_device(
            name="test lamp",
            device_type_id=self.device_type_id,
            pattern=["test lamp", "lamp"],
            device_attributes={"mqtt_path": "test/lamp"},
            room_id=self.room_id,
        )

        # Verify session operations
        mock_session.add.assert_called_once()
        mock_session.commit.assert_awaited_once()
        mock_session.refresh.assert_awaited_once()

        # Verify MQTT notification
        self.mock_mqtt_client.publish.assert_awaited_once_with(
            "assistant/global_device_update", payload="", qos=1
        )

    @patch("private_assistant_commons.database.device_registry.AsyncSession")
    @patch("private_assistant_commons.database.device_registry.select")
    async def test_update_device_success(self, _mock_select, mock_session_class):
        """Test successful device update."""
        # Mock session and result
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        # Mock device from database
        mock_device = Mock(spec=GlobalDevice)
        mock_device.id = self.device_id
        mock_device.name = "old name"
        mock_device.pattern = ["old"]

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_device
        mock_session.execute.return_value = mock_result

        # Call update_device
        _device = await self.skill.update_device(self.device_id, name="new name", pattern=["new pattern"])

        # Verify update
        assert mock_device.name == "new name"
        assert mock_device.pattern == ["new pattern"]
        mock_session.commit.assert_awaited_once()

        # Verify MQTT notification
        self.mock_mqtt_client.publish.assert_awaited_once()

    @patch("private_assistant_commons.database.device_registry.AsyncSession")
    @patch("private_assistant_commons.database.device_registry.select")
    async def test_update_device_not_found(self, _mock_select, mock_session_class):
        """Test update when device not found."""
        # Mock session with no device found
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Call update_device
        device = await self.skill.update_device(self.device_id, name="new name")

        # Verify returns None and no commit
        assert device is None
        mock_session.commit.assert_not_awaited()

    @patch("private_assistant_commons.database.device_registry.AsyncSession")
    @patch("private_assistant_commons.database.device_registry.select")
    async def test_delete_device_success(self, _mock_select, mock_session_class):
        """Test successful device deletion."""
        # Mock session and device
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        mock_device = Mock(spec=GlobalDevice)
        mock_device.id = self.device_id
        mock_device.name = "test lamp"

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_device
        mock_session.execute.return_value = mock_result

        # Call delete_device
        success = await self.skill.delete_device(self.device_id)

        # Verify deletion
        assert success is True
        mock_session.delete.assert_awaited_once_with(mock_device)
        mock_session.commit.assert_awaited_once()

        # Verify MQTT notification
        self.mock_mqtt_client.publish.assert_awaited_once()

    @patch("private_assistant_commons.database.device_registry.AsyncSession")
    @patch("private_assistant_commons.database.device_registry.select")
    async def test_delete_device_not_found(self, _mock_select, mock_session_class):
        """Test delete when device not found."""
        # Mock session with no device
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Call delete_device
        success = await self.skill.delete_device(self.device_id)

        # Verify returns False and no delete
        assert success is False
        mock_session.delete.assert_not_awaited()

    @patch("private_assistant_commons.database.device_registry.AsyncSession")
    @patch("private_assistant_commons.database.device_registry.select")
    async def test_get_skill_devices(self, _mock_select, mock_session_class):
        """Test getting all skill devices."""
        # Mock session and devices
        mock_session = AsyncMock()
        mock_session_class.return_value.__aenter__.return_value = mock_session

        mock_device1 = Mock(spec=GlobalDevice, name="device1")
        mock_device2 = Mock(spec=GlobalDevice, name="device2")

        expected_device_count = 2
        mock_result = Mock()
        mock_scalars = Mock()
        mock_scalars.all.return_value = [mock_device1, mock_device2]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        # Call get_skill_devices
        devices = await self.skill.get_skill_devices()

        # Verify results
        assert len(devices) == expected_device_count
        assert devices == [mock_device1, mock_device2]

    @patch("private_assistant_commons.database.device_registry.AsyncSession")
    async def test_register_device_error_handling(self, mock_session_class):
        """Test error handling in register_device."""
        # Mock session that raises exception
        mock_session = AsyncMock()
        mock_session.commit.side_effect = Exception("Database error")
        mock_session_class.return_value.__aenter__.return_value = mock_session

        # Call register_device
        device = await self.skill.register_device(
            name="test lamp", device_type_id=self.device_type_id, pattern=["test"]
        )

        # Verify returns None on error
        assert device is None

    async def test_mqtt_notification_error_handling(self):
        """Test MQTT notification error handling."""
        # Mock MQTT client to raise exception
        self.mock_mqtt_client.publish.side_effect = Exception("MQTT error")

        # Call _publish_device_update directly
        await self.skill._publish_device_update()

        # Should not raise exception, just log error
        self.mock_mqtt_client.publish.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
