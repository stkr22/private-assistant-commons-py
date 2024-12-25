# Private Assistant Commons

[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-orange.json)](https://github.com/copier-org/copier)
[![python](https://img.shields.io/badge/Python-3.12-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/charliermarsh/ruff/main/assets/badge/v0.json)](https://github.com/charliermarsh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit&logoColor=white)](https://github.com/pre-commit/pre-commit)

Owner: stkr22

`private-assistant-commons` is a shared library designed to provide common utilities and foundational components essential for developing various skills within the Private Assistant ecosystem. This package includes base classes, utility functions, and common validation routines like messsages that standardize and streamline the development of new skills.

## Features

- **Base Skill Class**: Provides a templated parent class from which all specific skill implementations inherit.
- **MQTT Utilities**: Includes helper functions and classes for managing MQTT connections and message handling.
- **Validation Utilities**: Offers standardized validation functions to ensure message integrity across different skills.
- **Common Configurations**: Centralizes common configurations and settings that are used across multiple skills.

## Getting Started

### Prerequisites

Ensure you have Python 3.11+ installed, as this library uses features available in Python 3.11 and later.

### Installation

Install `private-assistant-commons` by running the following command:

Certainly! Let's craft both a concise description for your `pyproject.toml` and a more detailed description for your `README.md` for the new package named `private-assistant-commons`. This package is intended to serve as the foundation for shared utilities and components across all skills in your private assistant system.

### Description for `pyproject.toml`

This short description succinctly summarizes the purpose of the shared utilities package for inclusion in the `pyproject.toml` file:

```toml
description = "Common utilities and base functionalities for all skills in the Private Assistant ecosystem."
```

### Description for `README.md`

For the `README.md` file, you'll want a more detailed description that explains the purpose, contains setup instructions, and outlines how to use the utilities. Here’s a proposed structure:

```markdown
# Private Assistant Commons

## Overview

`private-assistant-commons` is a shared library designed to provide common utilities and foundational components essential for developing various skills within the Private Assistant ecosystem. This package includes base classes, utility functions, and common validation routines that standardize and streamline the development of new skills.

## Features

- **Base Skill Class**: Provides a templated parent class from which all specific skill implementations inherit.
- **MQTT Utilities**: Includes helper functions and classes for managing MQTT connections and message handling.
- **Validation Utilities**: Offers standardized validation functions to ensure message integrity across different skills.
- **Common Configurations**: Centralizes common configurations and settings that are used across multiple skills.

## Getting Started

### Prerequisites

Ensure you have Python 3.11+ installed, as this library uses features available in Python 3.11 and later.

### Usage

Import and use the utilities in your skill implementations:

```python
from private_assistant_commons import BaseSkill

class SwitchSkill(BaseSkill):
    def __init__(self, ...):
        super().__init__(...)

```

## Contributing

Contributions to `private-assistant-commons` are welcome! Please read our contributing guidelines on how to propose bug fixes, improvements, or new features.
