import logging
import os
from pathlib import Path
from typing import Self, TypeVar

import yaml
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class PostgresConfig(BaseModel):
    user: str = Field(default="postgres", description="Database user")
    password: str = Field(default="postgres", description="Database password")
    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port")
    database: str = Field(default="postgres", description="Database name")

    @property
    def connection_string(self) -> str:
        return f"postgresql+psycopg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @property
    def connection_string_async(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    @classmethod
    def from_env(cls) -> Self:
        return cls.model_validate(
            {
                "user": os.getenv("POSTGRES_USER", "postgres"),
                "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
                "host": os.getenv("POSTGRES_HOST", "localhost"),
                "port": int(os.getenv("POSTGRES_PORT", "5432")),
                "database": os.getenv("POSTGRES_DB", "postgres"),
            }
        )


class SkillConfig(BaseModel):
    mqtt_server_host: str = "localhost"
    mqtt_server_port: int = 1883
    client_id: str = "default_skill"
    base_topic: str = "assistant"
    intent_analysis_result_topic: str = "assistant/intent_engine/result"
    broadcast_topic: str = "assistant/comms_bridge/broadcast"
    intent_cache_size: int = Field(default=1000, description="Maximum number of intent analysis results to cache")

    @property
    def feedback_topic(self) -> str:
        return f"{self.base_topic}/{self.client_id}/feedback"


def combine_yaml_files(file_paths: list[Path]) -> dict:
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
