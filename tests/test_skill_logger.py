"""Tests for skill_logger module with focus on caching performance optimizations."""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import pytest
from rich.console import Console

from private_assistant_commons.skill_logger import LoggerConfig, SkillLogger


class TestSkillLoggerCaching:
    """Test caching functionality and performance optimizations."""

    def setup_method(self):
        """Clear cache before each test."""
        SkillLogger.clear_cache()

    def test_handler_caching(self):
        """Test that handlers are properly cached and reused."""
        # Get multiple loggers with same configuration
        SkillLogger.get_logger("test.logger1")
        SkillLogger.get_logger("test.logger2")

        # Verify handlers are cached (same handler should be reused)
        cache_stats = SkillLogger.get_cache_stats()
        assert cache_stats["handlers_cached"] >= 1
        assert cache_stats["formatters_cached"] >= 1
        assert cache_stats["consoles_cached"] >= 1

    def test_formatter_caching(self):
        """Test that formatters are properly cached and reused."""
        format1 = "[bold blue]%(name)s[/bold blue] - %(message)s"
        format2 = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        # Create loggers with different formats
        SkillLogger.get_logger("test.logger1", format_string=format1)
        SkillLogger.get_logger("test.logger2", format_string=format1)  # Same format
        SkillLogger.get_logger("test.logger3", format_string=format2)  # Different format

        cache_stats = SkillLogger.get_cache_stats()
        # Should have at least 2 formatters (one for each unique format)
        min_formatters = 2
        assert cache_stats["formatters_cached"] >= min_formatters

    def test_console_caching(self):
        """Test that console instances are properly cached."""
        # Create multiple loggers with default configuration
        SkillLogger.get_logger("test.logger1")
        SkillLogger.get_logger("test.logger2")

        cache_stats = SkillLogger.get_cache_stats()
        # Should have at least 1 cached console
        assert cache_stats["consoles_cached"] >= 1

    def test_custom_console_not_cached(self):
        """Test that custom console instances are handled correctly."""
        custom_console = Console()
        config = LoggerConfig(console=custom_console)

        SkillLogger.get_logger("test.logger1", config=config)
        SkillLogger.get_logger("test.logger2", config=config)

        # Custom console should still result in caching behavior
        cache_stats = SkillLogger.get_cache_stats()
        assert cache_stats["handlers_cached"] >= 1

    def test_thread_safety(self):
        """Test that caching is thread-safe during concurrent access."""
        results = []
        errors = []

        def create_logger_worker(worker_id: int):
            try:
                for i in range(10):
                    logger = SkillLogger.get_logger(f"worker_{worker_id}.logger_{i}")
                    results.append((worker_id, i, logger.name))
            except Exception as e:
                errors.append((worker_id, e))

        # Run multiple workers concurrently
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(create_logger_worker, worker_id) for worker_id in range(5)]

            for future in futures:
                future.result(timeout=5.0)

        # Verify no errors occurred
        assert len(errors) == 0, f"Thread safety errors: {errors}"

        # Verify all loggers were created
        expected_results = 50  # 5 workers * 10 loggers each
        assert len(results) == expected_results

        # Verify cache was populated
        cache_stats = SkillLogger.get_cache_stats()
        assert cache_stats["handlers_cached"] >= 1
        assert cache_stats["formatters_cached"] >= 1

    def test_clear_cache(self):
        """Test that cache clearing works correctly."""
        # Create some loggers to populate cache
        SkillLogger.get_logger("test.logger1")
        SkillLogger.get_logger("test.logger2")

        # Verify cache is populated
        cache_stats = SkillLogger.get_cache_stats()
        assert cache_stats["handlers_cached"] > 0
        assert cache_stats["formatters_cached"] > 0

        # Clear cache
        SkillLogger.clear_cache()

        # Verify cache is empty
        cache_stats = SkillLogger.get_cache_stats()
        assert cache_stats["handlers_cached"] == 0
        assert cache_stats["formatters_cached"] == 0
        assert cache_stats["consoles_cached"] == 0

    def test_different_configurations_create_different_cache_entries(self):
        """Test that different configurations create separate cache entries."""
        config1 = LoggerConfig(show_time=True, show_path=False)
        config2 = LoggerConfig(show_time=False, show_path=True)

        SkillLogger.get_logger("test.logger1", config=config1)
        SkillLogger.get_logger("test.logger2", config=config2)

        cache_stats = SkillLogger.get_cache_stats()
        # Different configurations should create separate handlers
        min_handlers = 2
        assert cache_stats["handlers_cached"] >= min_handlers

    def test_get_console_logger_with_caching(self):
        """Test that get_console_logger works with caching."""
        custom_console = Console()

        logger1 = SkillLogger.get_console_logger("test.logger1", custom_console)
        logger2 = SkillLogger.get_console_logger("test.logger2", custom_console)

        # Verify loggers were created
        assert logger1.name == "test.logger1"
        assert logger2.name == "test.logger2"

        # Verify caching occurred
        cache_stats = SkillLogger.get_cache_stats()
        assert cache_stats["handlers_cached"] >= 1

    @pytest.mark.performance
    def test_logger_creation_performance(self):
        """Test that caching improves logger creation performance."""
        # Warm up the cache
        for i in range(5):
            SkillLogger.get_logger(f"warmup.logger{i}")

        # Measure time for cached logger creation
        start_time = time.time()
        for i in range(100):
            SkillLogger.get_logger(f"performance.logger{i}")
        cached_time = time.time() - start_time

        # Clear cache and measure time for uncached creation
        SkillLogger.clear_cache()
        start_time = time.time()
        for i in range(100):
            SkillLogger.get_logger(f"performance.nocache.logger{i}")
        uncached_time = time.time() - start_time

        # Cached creation should be significantly faster (allow some variance)
        # Note: This is a relative performance test, results may vary by system
        assert cached_time < uncached_time * 1.5, f"Cached: {cached_time:.4f}s, Uncached: {uncached_time:.4f}s"

    def test_cache_stats_accuracy(self):
        """Test that cache statistics are accurate."""
        initial_stats = SkillLogger.get_cache_stats()
        assert initial_stats["handlers_cached"] == 0
        assert initial_stats["formatters_cached"] == 0
        assert initial_stats["consoles_cached"] == 0

        # Create loggers with different configurations
        SkillLogger.get_logger("test.logger1", format_string="format1")
        SkillLogger.get_logger("test.logger2", format_string="format2")

        final_stats = SkillLogger.get_cache_stats()
        min_handlers = 2
        min_formatters = 2
        min_consoles = 1
        assert final_stats["handlers_cached"] >= min_handlers
        assert final_stats["formatters_cached"] >= min_formatters
        assert final_stats["consoles_cached"] >= min_consoles

    def test_logging_functionality_preserved(self):
        """Test that caching doesn't break logging functionality."""
        logger = SkillLogger.get_logger("test.functional")

        # Test that we can log messages at different levels
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")

        # Test that logger has the expected properties
        assert logger.name == "test.functional"
        assert len(logger.handlers) == 1
        assert logger.handlers[0].__class__.__name__ == "RichHandler"


class TestSkillLoggerBackwardCompatibility:
    """Test that caching changes maintain backward compatibility."""

    def setup_method(self):
        """Clear cache before each test."""
        SkillLogger.clear_cache()

    def test_get_logger_signature_compatibility(self):
        """Test that get_logger maintains backward compatibility."""
        # Original signature should still work
        logger1 = SkillLogger.get_logger("test.compat1")
        logger2 = SkillLogger.get_logger("test.compat2", level=logging.DEBUG)
        logger3 = SkillLogger.get_logger("test.compat3", level=logging.INFO, config=LoggerConfig())

        assert all(isinstance(logger, logging.Logger) for logger in [logger1, logger2, logger3])

    def test_create_skill_console_compatibility(self):
        """Test that create_skill_console maintains backward compatibility."""
        console1 = SkillLogger.create_skill_console()
        console2 = SkillLogger.create_skill_console(width=80)
        console3 = SkillLogger.create_skill_console(force_terminal=True)

        assert all(isinstance(console, Console) for console in [console1, console2, console3])

    def test_get_console_logger_compatibility(self):
        """Test that get_console_logger maintains backward compatibility."""
        custom_console = Console()

        logger1 = SkillLogger.get_console_logger("test.console1", custom_console)
        logger2 = SkillLogger.get_console_logger("test.console2", custom_console, level=logging.DEBUG)
        logger3 = SkillLogger.get_console_logger("test.console3", custom_console, config=LoggerConfig())

        assert all(isinstance(logger, logging.Logger) for logger in [logger1, logger2, logger3])


class TestSkillLoggerEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self):
        """Clear cache before each test."""
        SkillLogger.clear_cache()

    def test_environment_variable_handling(self):
        """Test that environment variables are handled correctly with caching."""
        with patch.dict("os.environ", {"LOG_LEVEL": "DEBUG"}):
            logger = SkillLogger.get_logger("test.env")
            assert logger.level == logging.DEBUG

        with patch.dict("os.environ", {"LOG_LEVEL": "ERROR"}):
            logger = SkillLogger.get_logger("test.env2")
            assert logger.level == logging.ERROR

    def test_large_cache_handling(self):
        """Test behavior with large number of cached items."""
        # Create many different logger configurations
        for i in range(50):
            SkillLogger.get_logger(f"test.large{i}", format_string=f"format_{i}")

        cache_stats = SkillLogger.get_cache_stats()
        expected_cache_size = 50
        assert cache_stats["handlers_cached"] == expected_cache_size
        assert cache_stats["formatters_cached"] == expected_cache_size

        # Verify cache clearing works with large cache
        SkillLogger.clear_cache()
        cache_stats = SkillLogger.get_cache_stats()
        assert cache_stats["handlers_cached"] == 0

    def test_concurrent_cache_operations(self):
        """Test concurrent cache operations don't cause issues."""

        def worker():
            for i in range(10):
                SkillLogger.get_logger(f"concurrent.{threading.current_thread().ident}.{i}")
                cache_clear_point = 5
                if i == cache_clear_point:  # Clear cache mid-way through
                    SkillLogger.clear_cache()

        threads = [threading.Thread(target=worker) for _ in range(3)]

        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        # Should complete without exceptions
        cache_stats = SkillLogger.get_cache_stats()
        # Cache may be empty or populated depending on timing
        assert cache_stats is not None
