from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class MqttConfig(BaseSettings):
    """Configuration for MQTT broker connection.

    Loads from environment variables with MQTT_ prefix:
    - MQTT_HOST (required): MQTT broker hostname
    - MQTT_PORT (required): MQTT broker port
    - MQTT_USERNAME (optional): Username for authentication
    - MQTT_PASSWORD (optional): Password for authentication
    """

    model_config = SettingsConfigDict(env_prefix="MQTT_")

    host: str = Field(description="MQTT broker host")
    port: int = Field(description="MQTT broker port")
    username: str | None = Field(default=None, description="MQTT username for authentication")
    password: str | None = Field(default=None, description="MQTT password for authentication")


class SkillConfig(BaseSettings):
    client_id: str = "default_skill"
    base_topic: str = "assistant"
    intent_analysis_result_topic: str = "assistant/intent_engine/result"
    broadcast_topic: str = "assistant/broadcast"
    intent_cache_size: int = Field(default=1000, description="Maximum number of intent analysis results to cache")
    device_update_topic: str = Field(
        default="assistant/global_device_update",
        description="MQTT topic for device registry update notifications",
    )

    @property
    def feedback_topic(self) -> str:
        return f"{self.base_topic}/{self.client_id}/feedback"

    @property
    def skill_id(self) -> str:
        """Get skill identifier (alias for client_id for device registry compatibility)."""
        return self.client_id


def combine_yaml_files(file_paths: list[Path]) -> dict[str, Any]:
    """
    Combine multiple YAML files into a single dictionary.

    Args:
        file_paths (list[Path]): List of paths to YAML files.

    Returns:
        dict: Combined dictionary from all YAML files.
    """
    combined_data = {}
    for file_path in file_paths:
        with file_path.open("r") as file:
            data = yaml.safe_load(file)
            combined_data.update(data)
    return combined_data


def load_config[T: BaseModel](config_path: str | Path, config_class: type[T]) -> T:
    """
    Load and validate configuration from YAML files.

    Args:
        config_path (Union[str, Path]): Path to a YAML file or a directory containing YAML files.
        config_class (Type[T]): The Pydantic model class to validate the combined data against.

    Returns:
        T: An instance of the provided Pydantic model class.

    Raises:
        FileNotFoundError: If no YAML files are found.
        ValidationError: If the combined data does not conform to the Pydantic model.
    """
    config_path = Path(config_path)

    yaml_files = sorted(config_path.glob("*.yaml")) if config_path.is_dir() else [config_path]

    if not yaml_files:
        raise FileNotFoundError(f"No YAML files found in the directory: {config_path}")

    try:
        combined_data = combine_yaml_files(yaml_files)
        return config_class.model_validate(combined_data)
    except FileNotFoundError as err:
        logger.error("Config file not found: %s", config_path)
        raise err
    except ValidationError as err_v:
        logger.error("Validation error: %s", err_v)
        raise err_v
