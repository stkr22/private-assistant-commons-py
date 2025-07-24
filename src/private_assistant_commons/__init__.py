"""Common utilities and base functionalities for all skills in the Private Assistant ecosystem."""

# Version handling for dynamic versioning
try:
    from ._version import __version__
except ImportError:
    # Fallback for development installs
    __version__ = "dev"

# Main imports
from .base_skill import BaseSkill
from .messages import ClientRequest, IntentAnalysisResult, NumberAnalysisResult
from .skill_config import SkillConfig
from .skill_logger import LoggerConfig, SkillLogger

# Single __all__ declaration with all public exports
__all__ = [
    "BaseSkill",
    "ClientRequest",
    "IntentAnalysisResult",
    "LoggerConfig",
    "NumberAnalysisResult",
    "SkillConfig",
    "SkillLogger",
    "__version__",
]
