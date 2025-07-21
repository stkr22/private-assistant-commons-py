# Private Assistant Commons

[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-orange.json)](https://github.com/copier-org/copier)
[![python](https://img.shields.io/badge/Python-3.12-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v0.json)](https://github.com/charliermarsh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

**Owner:** stkr22

Common utilities and base classes for building distributed voice assistant skills in a Private Assistant ecosystem. This library provides the foundation for creating modular, MQTT-based skills that process voice commands for home automation.

## Key Features

- **BaseSkill Framework**: Abstract base class with distributed processing, certainty-based filtering, and task management
- **MQTT Communication**: Structured message handling using Pydantic models with automatic reconnection
- **Location Awareness**: Support for room-based command routing and targeting
- **Audio Integration**: Configurable alerts and responses through voice bridge system
- **Optional Persistence**: PostgreSQL integration for skills requiring state storage

## Quick Start

### Installation

```bash
pip install private-assistant-commons
```

### Basic Skill Example

```python
from private_assistant_commons import BaseSkill, IntentAnalysisResult

class LightControlSkill(BaseSkill):
    async def calculate_certainty(self, intent: IntentAnalysisResult) -> float:
        if "light" in intent.nouns and "turn" in intent.verbs:
            return 0.9
        return 0.0

    async def process_request(self, intent: IntentAnalysisResult) -> None:
        await self.send_response("Lights controlled!", intent.client_request)

    async def skill_preparations(self) -> None:
        self.logger.info("Light skill ready")
```

## Documentation

📖 **[Full Documentation](docs/)**

- **[Architecture Guide](docs/architecture.md)** - System design, components, and data flow
- **[Usage Guide](docs/usage.md)** - Examples, patterns, and best practices
- **[API Reference](docs/api-reference.md)** - Complete API documentation

## System Overview

Private Assistant Commons enables building a distributed voice assistant system where:

- **Skills run independently** and decide whether to handle requests based on confidence scores
- **Communication via MQTT** using structured Pydantic messages
- **No central coordinator** - skills compete based on certainty thresholds
- **Room-based targeting** distinguishes command origin from target locations
- **Local deployment** typically on Kubernetes with STT/TTS APIs

## Architecture

```
User Voice → Local Client → Voice Bridge → STT API → MQTT Broker
                                                         ↓
Intent Analysis Engine ← MQTT Broker ← Skills (distributed processing)
                                                         ↓
Voice Bridge ← TTS API ← MQTT Broker ← Skill Responses
       ↓
Local Client → Audio Output
```

Skills inherit from `BaseSkill` and implement:
- `calculate_certainty()` - Confidence scoring for requests
- `process_request()` - Main skill logic
- `skill_preparations()` - Initialization setup

## Development

### Prerequisites

- Python 3.12+
- UV package manager

### Setup

```bash
# Clone and setup environment
git clone <repository-url>
cd private-assistant-commons-py
uv sync --group dev

# Run tests
uv run pytest

# Format and lint
uv run ruff format .
uv run ruff check .

# Type checking
uv run mypy src/
```

### Essential Commands

- `uv sync --group dev` - Install/update dependencies
- `uv run pytest` - Run tests with coverage
- `uv run ruff check .` - Lint code
- `uv run mypy src/` - Type check
- `pre-commit run --all-files` - Run all pre-commit hooks

## License

GNU General Public License v3.0 - see [LICENSE](LICENSE) for details.
