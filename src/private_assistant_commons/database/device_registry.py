"""Device registry mixin for standardized device CRUD operations.

This module provides the DeviceRegistryMixin for skills to manage their devices
with consistent patterns and automatic MQTT cache invalidation notifications.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from private_assistant_commons.database.models import GlobalDevice

if TYPE_CHECKING:
    import logging

    import aiomqtt
    from sqlalchemy.ext.asyncio import AsyncEngine

    from private_assistant_commons.skill_config import SkillConfig


class DeviceRegistryMixin:
    """Mixin for skills to manage devices with standardized patterns.

    Provides consistent device CRUD operations with automatic MQTT notifications
    for cache invalidation in the intent engine.

    Required attributes in class using this mixin:
    - engine: AsyncEngine (from BaseSkill.engine property)
    - mqtt_client: aiomqtt.Client (from BaseSkill)
    - config_obj: SkillConfig with skill_id property
    - logger: logging.Logger (from BaseSkill)

    Example:
        ```python
        from sqlalchemy.ext.asyncio import create_async_engine
        from private_assistant_commons import BaseSkill, DeviceRegistryMixin

        class SwitchSkill(BaseSkill, DeviceRegistryMixin):
            def __init__(self, ...):
                engine = create_async_engine("postgresql+asyncpg://...")
                super().__init__(..., engine=engine)

            async def refresh_devices(self):
                # Register a device with skill-specific metadata
                await self.register_device(
                    name="bedroom lamp",
                    device_type_id=light_type_id,
                    pattern=["bedroom lamp", "lamp in bedroom", "bedroom light"],
                    device_attributes={
                        "mqtt_path": "zigbee2mqtt/bedroom_lamp",
                        "on_payload": {"state": "ON"},
                        "off_payload": {"state": "OFF"},
                    },
                    room_id=bedroom_id,
                )
        ```
    """

    # Required attributes (provided by BaseSkill):
    # These are declared here for type checking but will be overridden by BaseSkill
    if TYPE_CHECKING:
        @property
        def engine(self) -> "AsyncEngine": ...
        mqtt_client: "aiomqtt.Client"
        logger: "logging.Logger"
        config_obj: "SkillConfig"

    async def register_device(
        self,
        name: str,
        device_type_id: UUID,
        pattern: list[str],
        device_attributes: dict[str, Any] | None = None,
        room_id: UUID | None = None,
    ) -> GlobalDevice | None:
        """Register a new device and publish MQTT notification.

        Args:
            name: Human-readable device name
            device_type_id: Foreign key to DeviceType
            pattern: List of pattern strings for NLU matching
            device_attributes: Skill-specific metadata (MQTT paths, templates, etc.)
            room_id: Optional foreign key to Room

        Returns:
            Created GlobalDevice instance, or None if registration failed
        """
        try:
            # Convert skill_id to UUID (skill_id from config is a string)
            skill_uuid = (
                UUID(self.config_obj.skill_id)
                if isinstance(self.config_obj.skill_id, str)
                else self.config_obj.skill_id
            )

            async with AsyncSession(self.engine) as session:
                device = GlobalDevice(
                    name=name,
                    device_type_id=device_type_id,
                    pattern=pattern,
                    device_attributes=device_attributes,
                    room_id=room_id,
                    skill_id=skill_uuid,
                )
                session.add(device)
                await session.commit()
                await session.refresh(device)

            # Guaranteed MQTT notification for cache invalidation
            await self._publish_device_update()
            self.logger.info("Registered device '%s' (id=%s)", name, device.id)
            return device

        except Exception as e:
            self.logger.error("Failed to register device '%s': %s", name, e, exc_info=True)
            return None

    async def update_device(
        self,
        device_id: UUID,
        **updates: Any,
    ) -> GlobalDevice | None:
        """Update device fields and publish MQTT notification.

        Args:
            device_id: Device UUID to update
            **updates: Fields to update (name, pattern, device_attributes, room_id)

        Returns:
            Updated GlobalDevice instance, or None if update failed or device not found
        """
        try:
            # Convert skill_id to UUID (skill_id from config is a string)
            skill_uuid = (
                UUID(self.config_obj.skill_id)
                if isinstance(self.config_obj.skill_id, str)
                else self.config_obj.skill_id
            )

            async with AsyncSession(self.engine) as session:
                result = await session.execute(
                    select(GlobalDevice).where(
                        GlobalDevice.id == device_id,  # type: ignore[arg-type]
                        GlobalDevice.skill_id == skill_uuid,  # type: ignore[arg-type]
                    )
                )
                device = result.scalar_one_or_none()

                if not device:
                    self.logger.warning("Device %s not found or doesn't belong to this skill", device_id)
                    return None

                # Update allowed fields
                for key, value in updates.items():
                    if hasattr(device, key):
                        setattr(device, key, value)

                device.updated_at = datetime.now()
                await session.commit()
                await session.refresh(device)

            await self._publish_device_update()
            self.logger.info("Updated device '%s' (id=%s)", device.name, device.id)
            return device

        except Exception as e:
            self.logger.error("Failed to update device %s: %s", device_id, e, exc_info=True)
            return None

    async def delete_device(self, device_id: UUID) -> bool:
        """Delete device and publish MQTT notification.

        Args:
            device_id: Device UUID to delete

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            # Convert skill_id to UUID (skill_id from config is a string)
            skill_uuid = (
                UUID(self.config_obj.skill_id)
                if isinstance(self.config_obj.skill_id, str)
                else self.config_obj.skill_id
            )

            async with AsyncSession(self.engine) as session:
                result = await session.execute(
                    select(GlobalDevice).where(
                        GlobalDevice.id == device_id,  # type: ignore[arg-type]
                        GlobalDevice.skill_id == skill_uuid,  # type: ignore[arg-type]
                    )
                )
                device = result.scalar_one_or_none()

                if not device:
                    self.logger.warning("Device %s not found or doesn't belong to this skill", device_id)
                    return False

                device_name = device.name
                await session.delete(device)
                await session.commit()

            await self._publish_device_update()
            self.logger.info("Deleted device '%s' (id=%s)", device_name, device_id)
            return True

        except Exception as e:
            self.logger.error("Failed to delete device %s: %s", device_id, e, exc_info=True)
            return False

    async def get_skill_devices(self) -> list[GlobalDevice]:
        """Get all devices belonging to this skill.

        Returns:
            List of GlobalDevice instances for this skill, or empty list on error
        """
        try:
            # Convert skill_id to UUID (skill_id from config is a string)
            skill_uuid = (
                UUID(self.config_obj.skill_id)
                if isinstance(self.config_obj.skill_id, str)
                else self.config_obj.skill_id
            )

            async with AsyncSession(self.engine) as session:
                result = await session.execute(
                    select(GlobalDevice).where(GlobalDevice.skill_id == skill_uuid)  # type: ignore[arg-type]
                )
                return list(result.scalars().all())

        except Exception as e:
            self.logger.error("Failed to get skill devices: %s", e, exc_info=True)
            return []

    async def _publish_device_update(self) -> None:
        """Publish MQTT notification for device cache invalidation.

        Sends an empty message to assistant/global_device_update topic to trigger
        the intent engine to refresh its device cache.
        """
        try:
            await self.mqtt_client.publish(self.config_obj.device_update_topic, payload="", qos=1)
            self.logger.debug("Published device update notification to %s", self.config_obj.device_update_topic)

        except Exception as e:
            self.logger.error("Failed to publish device update notification: %s", e, exc_info=True)
