import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class SkillConfig(BaseModel):
    mqtt_server_host: str = "localhost"
    mqtt_server_port: int = 1883
    client_id: str = "default_skill"
    base_topic: str = "assistant"
    certainty_topic: str = "assistant/coordinator/certainty"
    register_topic: str = "assistant/coordinator/register"
    registration_interval: float = 500.0
    client_request_subscription: str = "assistant/+/+/input"
    spacy_model: str = "en_core_web_md"

    @property
    def feedback_topic(self) -> str:
        return f"{self.base_topic}/{self.client_id}/feedback"


def combine_yaml_files(file_paths: list[Path]) -> dict:
    combined_data = {}
    for file_path in file_paths:
        with file_path.open("r") as file:
            data = yaml.safe_load(file)
            combined_data.update(data)
    return combined_data


def load_config(config_path: str | Path) -> SkillConfig:
    config_path = Path(config_path)

    if config_path.is_dir():
        # Get all YAML files in the directory, sorted alphabetically
        yaml_files = sorted(config_path.glob("*.yaml"))
    else:
        # Single file path given
        yaml_files = [config_path]

    if not yaml_files:
        raise FileNotFoundError(f"No YAML files found in the directory: {config_path}")

    try:
        combined_data = combine_yaml_files(yaml_files)
        return SkillConfig.model_validate(combined_data)
    except FileNotFoundError as err:
        logger.error("Config file not found: %s", config_path)
        raise err
    except ValidationError as err_v:
        logger.error("Validation error: %s", err_v)
        raise err_v
