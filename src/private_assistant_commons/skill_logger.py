"""Centralized logging configuration for Private Assistant skills."""

from __future__ import annotations

import logging
import os
import threading
from dataclasses import dataclass
from typing import Any, ClassVar

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
    """Optimized logger factory with handler and formatter caching.

    Provides thread-safe caching of handlers and formatters to reduce
    object creation overhead during logger initialization.
    """

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

    # AIDEV-NOTE: Performance optimization - cached handlers and formatters with thread safety
    _handler_cache: ClassVar[dict[str, RichHandler]] = {}
    _formatter_cache: ClassVar[dict[str, logging.Formatter]] = {}
    _console_cache: ClassVar[dict[str, Console]] = {}
    _cache_lock: ClassVar[threading.Lock] = threading.Lock()

    @classmethod
    def get_logger(
        cls,
        name: str,
        level: int | None = None,
        config: LoggerConfig | None = None,
        format_string: str | None = None,
    ) -> logging.Logger:
        """Create a configured logger with cached handlers for optimal performance.

        Args:
            name: Logger name (typically __name__ from calling module)
            level: Optional log level override, defaults to LOG_LEVEL env var or INFO
            config: Optional LoggerConfig instance for rich formatting options
            format_string: Optional custom format string for the logger

        Returns:
            Configured logger with cached RichHandler and enhanced visual formatting

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

        if format_string is None:
            format_string = "[bold blue]%(name)s[/bold blue] - %(message)s"

        logger = logging.getLogger(name)
        logger.setLevel(level)

        # Only configure if not already configured
        if not logger.handlers:
            handler = cls._get_cached_handler(config, level, format_string)
            logger.addHandler(handler)

        return logger

    @classmethod
    def _get_cached_handler(cls, config: LoggerConfig, level: int, format_string: str) -> RichHandler:
        """Get cached RichHandler with thread-safe access.

        Args:
            config: LoggerConfig instance with rich formatting options
            level: Log level for handler configuration
            format_string: Format string for the handler

        Returns:
            Cached or newly created RichHandler instance
        """
        # Create cache key based on configuration
        console_key = cls._get_console_cache_key(config)
        handler_key = (
            f"{console_key}_{level}_{hash(format_string)}_"
            f"{config.show_time}_{config.show_path}_{config.enable_link_path}_{config.rich_tracebacks}"
        )

        with cls._cache_lock:
            if handler_key not in cls._handler_cache:
                console = cls._get_cached_console(config)

                # AIDEV-NOTE: RichHandler provides colored output, structured formatting, and enhanced tracebacks
                handler = RichHandler(
                    console=console,
                    show_time=config.show_time,
                    show_path=config.show_path,
                    enable_link_path=config.enable_link_path,
                    rich_tracebacks=config.rich_tracebacks,
                    tracebacks_show_locals=level <= logging.DEBUG,  # Show local vars only in debug mode
                    markup=True,  # Enable rich markup in log messages
                )

                formatter = cls._get_cached_formatter(format_string)
                handler.setFormatter(formatter)
                cls._handler_cache[handler_key] = handler

            return cls._handler_cache[handler_key]

    @classmethod
    def _get_cached_console(cls, config: LoggerConfig) -> Console:
        """Get cached Console instance with thread-safe access.

        Args:
            config: LoggerConfig instance that may contain a console

        Returns:
            Cached or newly created Console instance
        """
        if config.console is not None:
            return config.console

        console_key = cls._get_console_cache_key(config)

        with cls._cache_lock:
            if console_key not in cls._console_cache:
                cls._console_cache[console_key] = Console(
                    theme=cls._SKILL_THEME,
                    force_terminal=None,  # Auto-detect terminal capabilities
                    no_color=os.getenv("RICH_NO_COLOR") is not None,
                )
            return cls._console_cache[console_key]

    @classmethod
    def _get_console_cache_key(cls, config: LoggerConfig) -> str:
        """Generate cache key for console based on environment.

        Args:
            config: LoggerConfig instance

        Returns:
            Cache key string for console identification
        """
        if config.console is not None:
            return f"custom_console_{id(config.console)}"
        return f"default_console_{os.getenv('RICH_NO_COLOR', 'None')}"

    @classmethod
    def _get_cached_formatter(cls, format_string: str, datefmt: str = "[%X]") -> logging.Formatter:
        """Get cached Formatter instance with thread-safe access.

        Args:
            format_string: Format string for the formatter
            datefmt: Date format string

        Returns:
            Cached or newly created Formatter instance
        """
        formatter_key = f"{format_string}_{datefmt}"

        with cls._cache_lock:
            if formatter_key not in cls._formatter_cache:
                cls._formatter_cache[formatter_key] = logging.Formatter(
                    fmt=format_string,
                    datefmt=datefmt,
                )
            return cls._formatter_cache[formatter_key]

    @classmethod
    def get_console_logger(
        cls,
        name: str,
        console: Console,
        level: int | None = None,
        config: LoggerConfig | None = None,
        format_string: str | None = None,
    ) -> logging.Logger:
        """Create a logger that uses a specific Console instance.

        Args:
            name: Logger name
            console: Console instance to use for output
            level: Optional log level override
            config: Optional LoggerConfig instance, console will be overridden
            format_string: Optional custom format string

        Returns:
            Logger configured with the provided Console instance
        """
        if config is None:
            config = LoggerConfig()

        # Override console in config
        config.console = console

        return cls.get_logger(
            name=name,
            level=level,
            config=config,
            format_string=format_string,
        )

    @classmethod
    def create_skill_console(
        cls,
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
            theme=cls._SKILL_THEME,
            width=width,
            force_terminal=force_terminal,
            no_color=os.getenv("RICH_NO_COLOR") is not None,
            **console_kwargs,
        )

    @classmethod
    def clear_cache(cls) -> None:
        """Clear all cached handlers, formatters, and consoles.

        Useful for testing or when you need to reset the cache state.
        This method is thread-safe.
        """
        with cls._cache_lock:
            cls._handler_cache.clear()
            cls._formatter_cache.clear()
            cls._console_cache.clear()

    @classmethod
    def get_cache_stats(cls) -> dict[str, int]:
        """Get statistics about cached objects.

        Returns:
            Dictionary with cache statistics for monitoring
        """
        with cls._cache_lock:
            return {
                "handlers_cached": len(cls._handler_cache),
                "formatters_cached": len(cls._formatter_cache),
                "consoles_cached": len(cls._console_cache),
            }
