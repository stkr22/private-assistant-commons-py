# Private Assistant Commons

## Overview

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
