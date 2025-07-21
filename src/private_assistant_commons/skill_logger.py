"""Centralized logging configuration for Private Assistant skills."""
import logging
import os


class SkillLogger:
    """Utility class for creating standardized loggers for skills."""
    
    @staticmethod
    def get_logger(name: str, level: int | None = None) -> logging.Logger:
        """Create a configured logger for a skill.
        
        Args:
            name: Logger name (typically __name__ from calling module)
            level: Optional log level override, defaults to LOG_LEVEL env var or INFO
            
        Returns:
            Configured logger with console handler and standard formatting
            
        Environment Variables:
            LOG_LEVEL: Sets default log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        if level is None:
            # AIDEV-NOTE: Respects LOG_LEVEL environment variable for runtime log control
            env_level = os.getenv("LOG_LEVEL", "INFO").upper()

            # Convert string level to logging constant
            level = getattr(logging, env_level, logging.INFO)

        logger = logging.getLogger(name)
        logger.setLevel(level)

        if not logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        return logger
