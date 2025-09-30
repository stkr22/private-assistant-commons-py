"""Performance metrics and observability for Private Assistant skills.

This module provides comprehensive metrics collection for monitoring skill performance,
MQTT operations, task management, and system health in production environments.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

# AIDEV-NOTE: Health check threshold constants for monitoring
MESSAGE_SUCCESS_RATE_THRESHOLD = 0.95
MQTT_SUCCESS_RATE_THRESHOLD = 0.98
CRITICAL_ERROR_RATE_THRESHOLD = 0.1
WARNING_ERROR_RATE_THRESHOLD = 0.01
MAX_LATENCY_MS_THRESHOLD = 1000
CACHE_HIT_RATE_THRESHOLD = 0.8


@dataclass
class PerformanceMetrics:
    """Container for skill performance metrics."""

    # Message processing metrics
    messages_processed: int = 0
    messages_failed: int = 0
    processing_times: deque[float] = field(default_factory=lambda: deque(maxlen=1000))
    certainty_scores: deque[float] = field(default_factory=lambda: deque(maxlen=1000))

    # Task management metrics
    tasks_created: int = 0
    tasks_completed: int = 0
    tasks_failed: int = 0
    task_durations: deque[float] = field(default_factory=lambda: deque(maxlen=500))

    # MQTT operation metrics
    mqtt_publishes: int = 0
    mqtt_publish_failures: int = 0
    mqtt_reconnections: int = 0
    mqtt_response_times: deque[float] = field(default_factory=lambda: deque(maxlen=500))

    # Cache and memory metrics
    cache_hits: int = 0
    cache_misses: int = 0
    cache_evictions: int = 0
    peak_cache_size: int = 0

    # System health metrics
    error_count: int = 0
    warning_count: int = 0
    uptime_start: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Initialize derived metrics."""
        if not hasattr(self, "_lock"):
            self._lock = threading.Lock()


class MetricsCollector:
    """Thread-safe metrics collection and aggregation system."""

    def __init__(self, skill_name: str):
        """Initialize metrics collector.

        Args:
            skill_name: Name of the skill for metrics identification
        """
        self.skill_name = skill_name
        self.metrics = PerformanceMetrics()
        self._active_timers: dict[str, float] = {}
        self._lock = threading.Lock()
        self._logger = logging.getLogger(f"{__name__}.{skill_name}")

    def start_timer(self, operation: str) -> str:
        """Start timing an operation.

        Args:
            operation: Name of the operation being timed

        Returns:
            Timer ID for ending the timer
        """
        timer_id = f"{operation}_{int(time.time() * 1000)}_{id(self)}"
        with self._lock:
            self._active_timers[timer_id] = time.perf_counter()
        return timer_id

    def end_timer(self, timer_id: str) -> float | None:
        """End timing and record duration.

        Args:
            timer_id: Timer ID returned by start_timer

        Returns:
            Duration in seconds, or None if timer not found
        """
        with self._lock:
            start_time = self._active_timers.pop(timer_id, None)
            if start_time is None:
                return None

            duration = time.perf_counter() - start_time

            # Categorize timing by operation type
            if "message_processing" in timer_id:
                self.metrics.processing_times.append(duration)
            elif "mqtt_publish" in timer_id:
                self.metrics.mqtt_response_times.append(duration)
            elif "task" in timer_id:
                self.metrics.task_durations.append(duration)

            return duration

    def record_message_processed(self, success: bool = True, certainty: float | None = None):
        """Record message processing result.

        Args:
            success: Whether message processing succeeded
            certainty: Certainty score for the message (0.0-1.0)
        """
        with self._lock:
            if success:
                self.metrics.messages_processed += 1
            else:
                self.metrics.messages_failed += 1
                self.metrics.error_count += 1

            if certainty is not None:
                self.metrics.certainty_scores.append(certainty)

    def record_task_event(self, event: str, duration: float | None = None):
        """Record task lifecycle events.

        Args:
            event: Event type ('created', 'completed', 'failed')
            duration: Task duration in seconds (for completed/failed events)
        """
        with self._lock:
            if event == "created":
                self.metrics.tasks_created += 1
            elif event == "completed":
                self.metrics.tasks_completed += 1
                if duration is not None:
                    self.metrics.task_durations.append(duration)
            elif event == "failed":
                self.metrics.tasks_failed += 1
                self.metrics.error_count += 1
                if duration is not None:
                    self.metrics.task_durations.append(duration)

    def record_mqtt_event(self, event: str, success: bool = True, duration: float | None = None):
        """Record MQTT operation results.

        Args:
            event: Event type ('publish', 'reconnection')
            success: Whether the operation succeeded
            duration: Operation duration in seconds
        """
        with self._lock:
            if event == "publish":
                if success:
                    self.metrics.mqtt_publishes += 1
                else:
                    self.metrics.mqtt_publish_failures += 1
                    self.metrics.error_count += 1

                if duration is not None:
                    self.metrics.mqtt_response_times.append(duration)

            elif event == "reconnection":
                self.metrics.mqtt_reconnections += 1
                if not success:
                    self.metrics.error_count += 1

    def record_cache_event(self, event: str, cache_size: int | None = None):
        """Record cache operation events.

        Args:
            event: Event type ('hit', 'miss', 'eviction')
            cache_size: Current cache size
        """
        with self._lock:
            if event == "hit":
                self.metrics.cache_hits += 1
            elif event == "miss":
                self.metrics.cache_misses += 1
            elif event == "eviction":
                self.metrics.cache_evictions += 1

            if cache_size is not None and cache_size > self.metrics.peak_cache_size:
                self.metrics.peak_cache_size = cache_size

    def record_log_event(self, level: str):
        """Record logging events for health monitoring.

        Args:
            level: Log level ('ERROR', 'WARNING', etc.)
        """
        with self._lock:
            if level == "ERROR":
                self.metrics.error_count += 1
            elif level == "WARNING":
                self.metrics.warning_count += 1

    def get_metrics_summary(self) -> dict[str, Any]:
        """Get comprehensive metrics summary.

        Returns:
            Dictionary containing all collected metrics and computed statistics
        """
        with self._lock:
            now = datetime.now()
            uptime = now - self.metrics.uptime_start

            # Calculate processing statistics
            processing_times = list(self.metrics.processing_times)
            if processing_times:
                avg_processing_time = sum(processing_times) / len(processing_times)
                processing_times_sorted = sorted(processing_times)
                p50_processing = processing_times_sorted[len(processing_times_sorted) // 2]
                p95_processing = processing_times_sorted[int(len(processing_times_sorted) * 0.95)]
                p99_processing = processing_times_sorted[int(len(processing_times_sorted) * 0.99)]
            else:
                avg_processing_time = p50_processing = p95_processing = p99_processing = 0

            # Calculate MQTT statistics
            mqtt_times = list(self.metrics.mqtt_response_times)
            if mqtt_times:
                avg_mqtt_time = sum(mqtt_times) / len(mqtt_times)
                mqtt_times_sorted = sorted(mqtt_times)
                p95_mqtt = mqtt_times_sorted[int(len(mqtt_times_sorted) * 0.95)]
            else:
                avg_mqtt_time = p95_mqtt = 0

            # Calculate certainty statistics
            certainty_scores = list(self.metrics.certainty_scores)
            if certainty_scores:
                avg_certainty = sum(certainty_scores) / len(certainty_scores)
                min_certainty = min(certainty_scores)
                max_certainty = max(certainty_scores)
            else:
                avg_certainty = min_certainty = max_certainty = 0

            # Calculate success rates
            total_messages = self.metrics.messages_processed + self.metrics.messages_failed
            message_success_rate = self.metrics.messages_processed / total_messages if total_messages > 0 else 0

            total_mqtt_ops = self.metrics.mqtt_publishes + self.metrics.mqtt_publish_failures
            mqtt_success_rate = self.metrics.mqtt_publishes / total_mqtt_ops if total_mqtt_ops > 0 else 0

            total_tasks = self.metrics.tasks_completed + self.metrics.tasks_failed
            task_success_rate = self.metrics.tasks_completed / total_tasks if total_tasks > 0 else 0

            # Calculate throughput
            throughput = self.metrics.messages_processed / uptime.total_seconds() if uptime.total_seconds() > 0 else 0

            return {
                "skill_name": self.skill_name,
                "timestamp": now.isoformat(),
                "uptime_seconds": uptime.total_seconds(),
                "message_processing": {
                    "total_processed": self.metrics.messages_processed,
                    "total_failed": self.metrics.messages_failed,
                    "success_rate": message_success_rate,
                    "throughput_per_second": throughput,
                    "latency_ms": {
                        "avg": avg_processing_time * 1000,
                        "p50": p50_processing * 1000,
                        "p95": p95_processing * 1000,
                        "p99": p99_processing * 1000,
                    },
                },
                "certainty_analysis": {
                    "avg_certainty": avg_certainty,
                    "min_certainty": min_certainty,
                    "max_certainty": max_certainty,
                    "total_evaluations": len(certainty_scores),
                },
                "task_management": {
                    "created": self.metrics.tasks_created,
                    "completed": self.metrics.tasks_completed,
                    "failed": self.metrics.tasks_failed,
                    "success_rate": task_success_rate,
                    "avg_duration_ms": (
                        sum(self.metrics.task_durations) / len(self.metrics.task_durations) * 1000
                        if self.metrics.task_durations
                        else 0
                    ),
                },
                "mqtt_operations": {
                    "publishes": self.metrics.mqtt_publishes,
                    "publish_failures": self.metrics.mqtt_publish_failures,
                    "success_rate": mqtt_success_rate,
                    "reconnections": self.metrics.mqtt_reconnections,
                    "avg_response_time_ms": avg_mqtt_time * 1000,
                    "p95_response_time_ms": p95_mqtt * 1000,
                },
                "cache_performance": {
                    "hits": self.metrics.cache_hits,
                    "misses": self.metrics.cache_misses,
                    "hit_rate": (
                        self.metrics.cache_hits / (self.metrics.cache_hits + self.metrics.cache_misses)
                        if (self.metrics.cache_hits + self.metrics.cache_misses) > 0
                        else 0
                    ),
                    "evictions": self.metrics.cache_evictions,
                    "peak_size": self.metrics.peak_cache_size,
                },
                "system_health": {
                    "error_count": self.metrics.error_count,
                    "warning_count": self.metrics.warning_count,
                    "error_rate": (
                        self.metrics.error_count / uptime.total_seconds() if uptime.total_seconds() > 0 else 0
                    ),
                    "active_timers": len(self._active_timers),
                },
            }

    def get_prometheus_metrics(self) -> str:
        """Export metrics in Prometheus format.

        Returns:
            Prometheus-formatted metrics string
        """
        summary = self.get_metrics_summary()
        msg_processed = summary["message_processing"]["total_processed"]
        msg_failed = summary["message_processing"]["total_failed"]
        processing_sum = sum(self.metrics.processing_times)
        processing_count = len(self.metrics.processing_times)
        throughput = summary["message_processing"]["throughput_per_second"]
        mqtt_publishes = summary["mqtt_operations"]["publishes"]
        mqtt_failures = summary["mqtt_operations"]["publish_failures"]

        lines = [
            "# HELP skill_messages_processed_total Total number of messages processed",
            "# TYPE skill_messages_processed_total counter",
            f'skill_messages_processed_total{{skill_name="{self.skill_name}"}} {msg_processed}',
            "",
            "# HELP skill_messages_failed_total Total number of failed message processing attempts",
            "# TYPE skill_messages_failed_total counter",
            f'skill_messages_failed_total{{skill_name="{self.skill_name}"}} {msg_failed}',
            "",
            "# HELP skill_message_processing_duration_seconds Message processing duration",
            "# TYPE skill_message_processing_duration_seconds histogram",
            f'skill_message_processing_duration_seconds_sum{{skill_name="{self.skill_name}"}} {processing_sum}',
            f'skill_message_processing_duration_seconds_count{{skill_name="{self.skill_name}"}} {processing_count}',
            "",
            "# HELP skill_throughput_messages_per_second Current message processing throughput",
            "# TYPE skill_throughput_messages_per_second gauge",
            f'skill_throughput_messages_per_second{{skill_name="{self.skill_name}"}} {throughput:.3f}',
            "",
            "# HELP skill_mqtt_publishes_total Total MQTT publish operations",
            "# TYPE skill_mqtt_publishes_total counter",
            f'skill_mqtt_publishes_total{{skill_name="{self.skill_name}"}} {mqtt_publishes}',
            "",
            "# HELP skill_mqtt_publish_failures_total Total MQTT publish failures",
            "# TYPE skill_mqtt_publish_failures_total counter",
            f'skill_mqtt_publish_failures_total{{skill_name="{self.skill_name}"}} {mqtt_failures}',
            "",
            "# HELP skill_tasks_created_total Total tasks created",
            "# TYPE skill_tasks_created_total counter",
            f'skill_tasks_created_total{{skill_name="{self.skill_name}"}} {summary["task_management"]["created"]}',
            "",
            "# HELP skill_cache_hits_total Total cache hits",
            "# TYPE skill_cache_hits_total counter",
            f'skill_cache_hits_total{{skill_name="{self.skill_name}"}} {summary["cache_performance"]["hits"]}',
            "",
            "# HELP skill_uptime_seconds Skill uptime in seconds",
            "# TYPE skill_uptime_seconds gauge",
            f'skill_uptime_seconds{{skill_name="{self.skill_name}"}} {summary["uptime_seconds"]:.1f}',
        ]

        return "\n".join(lines)

    def reset_metrics(self):
        """Reset all metrics to initial state."""
        with self._lock:
            self.metrics = PerformanceMetrics()
            self._active_timers.clear()
            self._logger.info("Metrics reset for skill: %s", self.skill_name)

    def export_to_json(self) -> str:
        """Export metrics as JSON string.

        Returns:
            JSON-formatted metrics string
        """
        summary = self.get_metrics_summary()
        return json.dumps(summary, indent=2)


class HealthChecker:
    """System health checking and alerting."""

    def __init__(self, metrics_collector: MetricsCollector):
        """Initialize health checker.

        Args:
            metrics_collector: Metrics collector to monitor
        """
        self.metrics = metrics_collector
        self._logger = logging.getLogger(f"{__name__}.health")

    def check_health(self) -> dict[str, Any]:
        """Perform comprehensive health check.

        Returns:
            Health status dictionary with issues and recommendations
        """
        summary = self.metrics.get_metrics_summary()
        health_status: dict[str, Any] = {"overall_status": "healthy", "checks": {}, "alerts": [], "recommendations": []}

        alerts: list[str] = health_status["alerts"]
        recommendations: list[str] = health_status["recommendations"]
        checks: dict[str, str] = health_status["checks"]

        # Check message processing health
        msg_success_rate = summary["message_processing"]["success_rate"]
        if msg_success_rate < MESSAGE_SUCCESS_RATE_THRESHOLD:
            checks["message_processing"] = "degraded"
            alerts.append(
                f"Message success rate is {msg_success_rate:.1%} (below {MESSAGE_SUCCESS_RATE_THRESHOLD:.0%} threshold)"
            )
            health_status["overall_status"] = "degraded"
        else:
            checks["message_processing"] = "healthy"

        # Check MQTT operation health
        mqtt_success_rate = summary["mqtt_operations"]["success_rate"]
        if mqtt_success_rate < MQTT_SUCCESS_RATE_THRESHOLD:
            checks["mqtt_operations"] = "degraded"
            alerts.append(
                f"MQTT success rate is {mqtt_success_rate:.1%} (below {MQTT_SUCCESS_RATE_THRESHOLD:.0%} threshold)"
            )
            health_status["overall_status"] = "degraded"
        else:
            checks["mqtt_operations"] = "healthy"

        # Check error rate
        error_rate = summary["system_health"]["error_rate"]
        if error_rate > CRITICAL_ERROR_RATE_THRESHOLD:
            checks["error_rate"] = "critical"
            alerts.append(f"High error rate: {error_rate:.3f} errors/second")
            health_status["overall_status"] = "critical"
        elif error_rate > WARNING_ERROR_RATE_THRESHOLD:
            checks["error_rate"] = "warning"
            alerts.append(f"Elevated error rate: {error_rate:.3f} errors/second")
        else:
            checks["error_rate"] = "healthy"

        # Check performance
        avg_latency = summary["message_processing"]["latency_ms"]["avg"]
        if avg_latency > MAX_LATENCY_MS_THRESHOLD:
            checks["performance"] = "degraded"
            recommendations.append(f"High average latency: {avg_latency:.0f}ms - consider optimization")
        else:
            checks["performance"] = "healthy"

        # Check cache performance
        cache_hit_rate = summary["cache_performance"]["hit_rate"]
        if cache_hit_rate < CACHE_HIT_RATE_THRESHOLD and summary["cache_performance"]["hits"] > 0:
            recommendations.append(f"Low cache hit rate: {cache_hit_rate:.1%} - consider cache tuning")

        return health_status
