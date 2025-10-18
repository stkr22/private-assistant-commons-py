"""Database models for the global device registry.

This module provides SQLModel table definitions for managing the global device registry
that enables pattern-based device matching across all skills in the Private Assistant ecosystem.

The registry consists of four main entities:
- Room: Physical locations where devices are placed
- Skill: Skills that own and manage devices
- DeviceType: Types of devices (e.g., light, switch, media_player)
- GlobalDevice: Devices registered in the global registry with pattern matching support

Skills can register their devices in the global registry and publish updates via MQTT
to the 'assistant/global_device_update' topic, triggering the intent engine to refresh
its device cache.

Example:
    from private_assistant_commons.database import Room, Skill, DeviceType, GlobalDevice

    # Create a room
    bedroom = Room(name="bedroom")

    # Create a skill
    switch_skill = Skill(name="switch-skill")

    # Create a device type
    light_type = DeviceType(name="light")

    # Register a device
    device = GlobalDevice(
        device_type_id=light_type.id,
        name="bedroom lamp",
        pattern=["bedroom lamp", "lamp in bedroom", "bedroom light"],
        room_id=bedroom.id,
        skill_id=switch_skill.id
    )
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import ARRAY, JSON, Column, String
from sqlmodel import Field, Relationship, SQLModel, select


class Room(SQLModel, table=True):
    """Room model for organizing devices by physical location.

    Rooms represent physical spaces where devices are located, enabling location-based
    device queries like "turn on bedroom lamp" or "lights in living room".

    Attributes:
        id: Unique identifier for the room
        name: Human-readable room name (unique across all rooms)
        created_at: Timestamp when the room was created
        updated_at: Timestamp when the room was last modified
    """

    __tablename__ = "rooms"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    devices: list["GlobalDevice"] = Relationship(back_populates="room")

    @classmethod
    async def get_by_name(cls, session, name: str) -> "Room | None":
        """Find room by name.

        Args:
            session: AsyncSession for database operations
            name: Room name to search for

        Returns:
            Room instance if found, None otherwise
        """
        result = await session.exec(select(cls).where(cls.name == name))
        return result.first()  # type: ignore[no-any-return]


class Skill(SQLModel, table=True):
    """Skill model for tracking which skill owns each device.

    Skills are components that manage specific types of devices (e.g., switch-skill,
    media-skill). Each device must be associated with exactly one skill that handles
    its operations.

    Attributes:
        id: Unique identifier for the skill
        name: Unique skill name (e.g., "switch-skill", "media-skill")
        created_at: Timestamp when the skill was registered
        updated_at: Timestamp when the skill was last modified
    """

    __tablename__ = "skills"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    devices: list["GlobalDevice"] = Relationship(back_populates="skill")

    @classmethod
    async def get_by_name(cls, session, name: str) -> "Skill | None":
        """Find skill by name.

        Args:
            session: AsyncSession for database operations
            name: Skill name to search for

        Returns:
            Skill instance if found, None otherwise
        """
        result = await session.exec(select(cls).where(cls.name == name))
        return result.first()  # type: ignore[no-any-return]

    @classmethod
    async def ensure_exists(cls, session, name: str) -> "Skill":
        """Ensure skill exists in database, creating if necessary (idempotent).

        Args:
            session: AsyncSession for database operations
            name: Skill name to ensure exists

        Returns:
            Skill instance (existing or newly created)
        """
        skill = await cls.get_by_name(session, name)
        if skill is None:
            skill = cls(name=name)
            session.add(skill)
            await session.commit()
            await session.refresh(skill)
        return skill


class DeviceType(SQLModel, table=True):
    """Device type model for categorizing devices.

    Device types represent categories of devices (e.g., light, switch, media_player).
    This allows for consistent device categorization across all skills.

    Attributes:
        id: Unique identifier for the device type
        name: Unique device type name (e.g., "light", "switch", "media_player")
        created_at: Timestamp when the device type was created
        updated_at: Timestamp when the device type was last modified
    """

    __tablename__ = "device_types"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    devices: list["GlobalDevice"] = Relationship(back_populates="device_type")

    @classmethod
    async def get_by_name(cls, session, name: str) -> "DeviceType | None":
        """Find device type by name.

        Args:
            session: AsyncSession for database operations
            name: Device type name to search for

        Returns:
            DeviceType instance if found, None otherwise
        """
        result = await session.exec(select(cls).where(cls.name == name))
        return result.first()  # type: ignore[no-any-return]

    @classmethod
    async def ensure_exists(cls, session, name: str) -> "DeviceType":
        """Ensure device type exists in database, creating if necessary (idempotent).

        Args:
            session: AsyncSession for database operations
            name: Device type name to ensure exists

        Returns:
            DeviceType instance (existing or newly created)
        """
        device_type = await cls.get_by_name(session, name)
        if device_type is None:
            device_type = cls(name=name)
            session.add(device_type)
            await session.commit()
            await session.refresh(device_type)
        return device_type


class GlobalDevice(SQLModel, table=True):
    """Device registry model for pattern-based device matching.

    The global device registry enables the intent engine to match user commands to
    specific devices instead of just generic device types. Each device has multiple
    pattern strings that can be used to identify it in natural language commands.

    Example:
        A device with name="bedroom lamp" might have patterns:
        ["bedroom lamp", "lamp in bedroom", "bedroom light", "lamp bedroom"]

        This allows matching commands like:
        - "Turn on bedroom lamp"
        - "Turn on the lamp in bedroom"
        - "Switch bedroom light on"

    Attributes:
        id: Unique identifier for the device
        device_type_id: Foreign key to the device type
        name: Human-readable device name
        pattern: List of pattern strings for matching natural language commands
        device_attributes: Skill-specific metadata (MQTT paths, templates, state mappings, etc.)
        room_id: Optional foreign key to the room where device is located
        skill_id: Foreign key to the skill that manages this device
        created_at: Timestamp when the device was registered
        updated_at: Timestamp when the device was last modified

    Note:
        Skills should publish to 'assistant/global_device_update' MQTT topic when
        devices are added, updated, or removed to trigger cache refresh in the
        intent engine.
    """

    __tablename__ = "global_devices"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    device_type_id: UUID = Field(foreign_key="device_types.id", index=True)
    name: str = Field(index=True)
    pattern: list[str] = Field(sa_column=Column(ARRAY(String)))
    device_attributes: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSON), description="Skill-specific device metadata (MQTT paths, templates, etc.)"
    )

    # Foreign key relationships
    room_id: UUID | None = Field(default=None, foreign_key="rooms.id", index=True)
    skill_id: UUID = Field(foreign_key="skills.id", index=True)

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Relationships
    device_type: DeviceType = Relationship(back_populates="devices")
    room: Room = Relationship(back_populates="devices")
    skill: Skill = Relationship(back_populates="devices")
