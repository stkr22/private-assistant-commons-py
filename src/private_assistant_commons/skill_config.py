import logging
from pathlib import Path

import yaml
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class SkillConfig(BaseModel):
    mqtt_server_host: str = "localhost"
    mqtt_server_port: int = 1883
    client_id: str = "switch_skill"
    base_topic: str = "assistant"
    certainty_topic: str = "assistant/coordinator/certainty"
    register_topic: str = "assistant/coordinator/register"
    registration_interval: float = 500.0
    client_request_subscription: str = "assistant/+/+/input"
    spacy_model: str = "en_core_web_md"

    @property
    def feedback_topic(self) -> str:
        return f"{self.base_topic}/{self.client_id}/feedback"


def load_config(config_path: Path) -> SkillConfig:
    try:
        with config_path.open("r") as file:
            config_data = yaml.safe_load(file)
        return SkillConfig.model_validate(config_data)
    except FileNotFoundError as err:
        logger.error("Config file not found: %s", config_path)
        raise err
    except ValidationError as err_v:
        logger.error("Validation error: %s", err_v)
        raise err_v
