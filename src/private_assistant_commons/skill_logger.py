"""Centralized logging configuration for Private Assistant skills."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme


@dataclass
class LoggerConfig:
    """Configuration for rich logger options."""

    show_time: bool = True
    show_path: bool = False
    enable_link_path: bool = True
    rich_tracebacks: bool = True
    console: Console | None = None


class SkillLogger:
    """Utility class for creating standardized loggers for skills with rich visual enhancements."""

    # AIDEV-NOTE: Custom theme for consistent Private Assistant branding
    _SKILL_THEME = Theme(
        {
            "logging.level.debug": "cyan",
            "logging.level.info": "green",
            "logging.level.warning": "yellow",
            "logging.level.error": "red bold",
            "logging.level.critical": "red on white bold",
            "logging.keyword": "bold blue",
            "logging.string": "magenta",
            "logging.number": "bright_blue",
            "repr.path": "magenta",
            "repr.filename": "bright_magenta bold",
        }
    )

    @staticmethod
    def get_logger(
        name: str,
        level: int | None = None,
        config: LoggerConfig | None = None,
    ) -> logging.Logger:
        """Create a configured logger with rich visual enhancements.

        Args:
            name: Logger name (typically __name__ from calling module)
            level: Optional log level override, defaults to LOG_LEVEL env var or INFO
            config: Optional LoggerConfig instance for rich formatting options

        Returns:
            Configured logger with RichHandler and enhanced visual formatting

        Environment Variables:
            LOG_LEVEL: Sets default log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            RICH_NO_COLOR: Set to disable colored output (useful for CI/CD)
        """
        if level is None:
            # AIDEV-NOTE: Respects LOG_LEVEL environment variable for runtime log control
            env_level = os.getenv("LOG_LEVEL", "INFO").upper()
            level = getattr(logging, env_level, logging.INFO)

        if config is None:
            config = LoggerConfig()

        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Avoid adding multiple handlers to the same logger
        if not logger.handlers:
            # Create console with custom theme if not provided
            console = config.console
            if console is None:
                console = Console(
                    theme=SkillLogger._SKILL_THEME,
                    force_terminal=None,  # Auto-detect terminal capabilities
                    no_color=os.getenv("RICH_NO_COLOR") is not None,
                )

            # AIDEV-NOTE: RichHandler provides colored output, structured formatting, and enhanced tracebacks
            rich_handler = RichHandler(
                console=console,
                show_time=config.show_time,
                show_path=config.show_path,
                enable_link_path=config.enable_link_path,
                rich_tracebacks=config.rich_tracebacks,
                tracebacks_show_locals=level <= logging.DEBUG,  # Show local vars only in debug mode
                markup=True,  # Enable rich markup in log messages
            )

            # Custom format for skill logging with skill name highlighting
            rich_handler.setFormatter(
                logging.Formatter(
                    fmt="[bold blue]%(name)s[/bold blue] - %(message)s",
                    datefmt="[%X]",
                )
            )

            logger.addHandler(rich_handler)

        return logger

    @staticmethod
    def get_console_logger(
        name: str,
        console: Console,
        level: int | None = None,
        config: LoggerConfig | None = None,
    ) -> logging.Logger:
        """Create a logger that uses a specific Console instance.

        Args:
            name: Logger name
            console: Console instance to use for output
            level: Optional log level override
            config: Optional LoggerConfig instance, console will be overridden

        Returns:
            Logger configured with the provided Console instance
        """
        if config is None:
            config = LoggerConfig()

        # Override console in config
        config.console = console

        return SkillLogger.get_logger(
            name=name,
            level=level,
            config=config,
        )

    @staticmethod
    def create_skill_console(
        width: int | None = None,
        force_terminal: bool | None = None,
        **console_kwargs: Any,
    ) -> Console:
        """Create a Console instance optimized for skill logging.

        Args:
            width: Console width, defaults to auto-detection
            force_terminal: Force terminal mode, defaults to auto-detection
            **console_kwargs: Additional arguments passed to Console

        Returns:
            Configured Console instance with skill-specific theme
        """
        return Console(
            theme=SkillLogger._SKILL_THEME,
            width=width,
            force_terminal=force_terminal,
            no_color=os.getenv("RICH_NO_COLOR") is not None,
            **console_kwargs,
        )
