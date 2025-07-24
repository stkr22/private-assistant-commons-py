#!/usr/bin/env python3
"""Performance benchmark for SkillLogger caching optimization."""

from __future__ import annotations

import time
from statistics import mean, stdev

from private_assistant_commons.skill_logger import SkillLogger


def benchmark_logger_creation(num_loggers: int = 1000, warmup_runs: int = 5) -> dict[str, float]:
    """Benchmark logger creation with and without caching.

    Args:
        num_loggers: Number of loggers to create in each test
        warmup_runs: Number of warmup runs to stabilize performance

    Returns:
        Dictionary with benchmark results
    """
    print("Benchmarking logger creation performance...")
    print(f"Creating {num_loggers} loggers with warmup of {warmup_runs} runs")

    # Warmup runs to stabilize performance
    print("Warming up...")
    for warmup in range(warmup_runs):
        SkillLogger.clear_cache()
        for i in range(min(100, num_loggers // 10)):
            SkillLogger.get_logger(f"warmup.{warmup}.logger{i}")

    # Test cached performance (warm cache)
    print("Testing cached performance...")
    SkillLogger.clear_cache()

    # Pre-populate cache with a few loggers
    for i in range(5):
        SkillLogger.get_logger(f"cache_seed.logger{i}")

    cached_times = []
    for run in range(3):  # Multiple runs for statistical accuracy
        start_time = time.perf_counter()
        for i in range(num_loggers):
            SkillLogger.get_logger(f"cached.run{run}.logger{i}")
        end_time = time.perf_counter()
        cached_times.append(end_time - start_time)

    # Test uncached performance (cold cache for each batch)
    print("Testing uncached performance...")
    uncached_times = []
    for run in range(3):  # Multiple runs for statistical accuracy
        SkillLogger.clear_cache()  # Clear cache for each run
        start_time = time.perf_counter()
        for i in range(num_loggers):
            SkillLogger.get_logger(f"uncached.run{run}.logger{i}")
        end_time = time.perf_counter()
        uncached_times.append(end_time - start_time)

    # Calculate statistics
    cached_mean = mean(cached_times)
    cached_std = stdev(cached_times) if len(cached_times) > 1 else 0
    uncached_mean = mean(uncached_times)
    uncached_std = stdev(uncached_times) if len(uncached_times) > 1 else 0

    improvement = ((uncached_mean - cached_mean) / uncached_mean) * 100

    return {
        "cached_mean": cached_mean,
        "cached_std": cached_std,
        "uncached_mean": uncached_mean,
        "uncached_std": uncached_std,
        "improvement_percent": improvement,
        "speedup_factor": uncached_mean / cached_mean if cached_mean > 0 else 1,
    }


def print_benchmark_results(results: dict[str, float], num_loggers: int) -> None:
    """Print formatted benchmark results.

    Args:
        results: Benchmark results dictionary
        num_loggers: Number of loggers used in benchmark
    """
    print("\n" + "=" * 60)
    print("PERFORMANCE BENCHMARK RESULTS")
    print("=" * 60)
    print(f"Number of loggers created: {num_loggers:,}")
    print()
    print("Timing Results:")
    print(f"  Cached (warm):   {results['cached_mean']:.4f}s ± {results['cached_std']:.4f}s")
    print(f"  Uncached (cold): {results['uncached_mean']:.4f}s ± {results['uncached_std']:.4f}s")
    print()
    print("Performance Improvement:")
    print(f"  Speed improvement: {results['improvement_percent']:.1f}%")
    print(f"  Speedup factor:    {results['speedup_factor']:.2f}x faster")
    print()
    print("Per-logger Performance:")
    print(f"  Cached:   {(results['cached_mean'] / num_loggers) * 1000:.3f} ms/logger")
    print(f"  Uncached: {(results['uncached_mean'] / num_loggers) * 1000:.3f} ms/logger")
    print("=" * 60)


def benchmark_cache_behavior() -> None:
    """Benchmark cache behavior and statistics."""
    print("\nCache Behavior Analysis:")
    print("-" * 30)

    # Start with empty cache
    SkillLogger.clear_cache()
    initial_stats = SkillLogger.get_cache_stats()
    print(f"Initial cache stats: {initial_stats}")

    # Create loggers with different configurations
    print("Creating loggers with different configurations...")

    configs = [
        ("default", {}),
        ("custom_format", {"format_string": "%(asctime)s - %(name)s - %(message)s"}),
        ("debug_level", {"level": 10}),  # DEBUG level
        ("info_level", {"level": 20}),  # INFO level
    ]

    for config_name, kwargs in configs:
        for i in range(5):
            SkillLogger.get_logger(f"{config_name}.logger{i}", **kwargs)

        stats = SkillLogger.get_cache_stats()
        print(f"After {config_name}: {stats}")

    final_stats = SkillLogger.get_cache_stats()
    print(f"Final cache stats: {final_stats}")

    # Test cache clearing
    SkillLogger.clear_cache()
    cleared_stats = SkillLogger.get_cache_stats()
    print(f"After clearing: {cleared_stats}")


if __name__ == "__main__":
    # Run main benchmark
    num_loggers = 1000
    results = benchmark_logger_creation(num_loggers)
    print_benchmark_results(results, num_loggers)

    # Analyze cache behavior
    benchmark_cache_behavior()

    print("\nBenchmark completed!")
