import pytest
import yaml
from pydantic import ValidationError

from private_assistant_commons import skill_config

TEST_MQTT_PORT = 1884


@pytest.fixture
def temp_yaml_files(tmp_path):
    # Create temporary YAML files for testing
    yaml_file1 = tmp_path / "file1.yaml"
    yaml_file2 = tmp_path / "file2.yaml"
    yaml_file1.write_text(yaml.dump({"client_id": "test_skill_1"}))
    yaml_file2.write_text(
        yaml.dump(
            {
                "client_id": "test_skill_2",
                "base_topic": "test/assistant",
            }
        )
    )
    return tmp_path


def test_load_single_yaml_file(temp_yaml_files):
    single_file = temp_yaml_files / "file1.yaml"
    config = skill_config.load_config(single_file, skill_config.SkillConfig)
    assert config.client_id == "test_skill_1"


def test_load_multiple_yaml_files(temp_yaml_files):
    config = skill_config.load_config(temp_yaml_files, skill_config.SkillConfig)
    assert config.client_id == "test_skill_2"
    assert config.base_topic == "test/assistant"


def test_load_nonexistent_file():
    with pytest.raises(FileNotFoundError):
        skill_config.load_config("nonexistent.yaml", skill_config.SkillConfig)


def test_validation_error(temp_yaml_files):
    invalid_yaml_file = temp_yaml_files / "invalid.yaml"
    invalid_yaml_file.write_text(yaml.dump({"intent_cache_size": "not_an_int"}))  # Invalid type
    with pytest.raises(ValidationError):
        skill_config.load_config(invalid_yaml_file, skill_config.SkillConfig)


def test_load_mqtt_config_from_yaml(tmp_path):
    """Test loading MqttConfig from YAML file."""
    yaml_file = tmp_path / "mqtt.yaml"
    yaml_file.write_text(
        yaml.dump(
            {
                "host": "mqtt.local",
                "port": TEST_MQTT_PORT,
                "username": "user",
                "password": "pass",
            }
        )
    )
    config = skill_config.load_config(yaml_file, skill_config.MqttConfig)
    assert config.host == "mqtt.local"
    assert config.port == TEST_MQTT_PORT
    assert config.username == "user"
    assert config.password == "pass"


def test_mqtt_config_required_fields(tmp_path):
    """Test that MqttConfig requires host and port."""
    yaml_file = tmp_path / "incomplete.yaml"
    yaml_file.write_text(yaml.dump({"host": "localhost"}))  # Missing port
    with pytest.raises(ValidationError):
        skill_config.load_config(yaml_file, skill_config.MqttConfig)
