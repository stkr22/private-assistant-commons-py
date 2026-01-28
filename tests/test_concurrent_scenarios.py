"""Tests for concurrent processing scenarios and edge cases."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, Mock

import pytest

from private_assistant_commons import intent, skill_config
from private_assistant_commons.base_skill import BaseSkill
from private_assistant_commons.messages import ClientRequest

# Test constants
EXPECTED_RETRY_COUNT = 3
EXPECTED_TOTAL_ATTEMPTS = 4  # Initial + 3 retries
MIN_SUCCESS_COUNT = 2


class TestConcurrentSkill(BaseSkill):
    """Test skill implementation for concurrent testing."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.processed_messages = []
        self.processing_times = []
        # Configure supported intents with per-intent confidence thresholds
        self.supported_intents = {
            intent.IntentType.DEVICE_ON: 0.8,
            intent.IntentType.DEVICE_OFF: 0.8,
        }

    async def skill_preparations(self) -> None:
        """Test implementation of skill preparations."""

    async def process_request(self, intent_request: intent.IntentRequest) -> None:
        # Track processed messages
        self.processed_messages.append(intent_request.id)
        await asyncio.sleep(0.001)  # Simulate processing time


class TestConcurrentProcessing:
    """Test concurrent message processing scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_mqtt_client = AsyncMock()
        self.task_group = AsyncMock()
        self.mock_engine = AsyncMock()
        self.mock_config = Mock(spec=skill_config.SkillConfig)
        self.mock_config.client_id = "test_concurrent_skill"
        self.mock_config.skill_id = "test_concurrent_skill"
        self.mock_config.intent_analysis_result_topic = "test/concurrent_intent"
        self.mock_config.broadcast_topic = "test/concurrent_broadcast"
        self.mock_config.intent_cache_size = 1000

    @pytest.mark.asyncio
    async def test_task_lifecycle_management(self):
        """Test task creation, tracking, and cleanup."""
        skill = TestConcurrentSkill(
            config_obj=self.mock_config,
            mqtt_client=self.mock_mqtt_client,
            task_group=self.task_group,
            engine=self.mock_engine,
        )

        # Mock task group to track task creation
        created_tasks = []

        def mock_create_task(coro, name=None):
            task = asyncio.create_task(coro, name=name)
            created_tasks.append(task)
            return task

        skill.task_group.create_task = mock_create_task

        # Add multiple tasks
        async def sample_task(task_id: int):
            await asyncio.sleep(0.01)
            return f"task_{task_id}_result"

        task_count = 5
        added_tasks = []
        for i in range(task_count):
            task = skill.add_task(sample_task(i), name=f"test_task_{i}")
            added_tasks.append(task)

        # Verify tasks were created
        assert len(created_tasks) == task_count
        assert skill.get_active_task_count() == task_count

        # Wait for tasks to complete
        await asyncio.gather(*added_tasks)

        # Small delay to allow cleanup callbacks to execute
        await asyncio.sleep(0.02)

        # Verify cleanup occurred
        assert skill.get_active_task_count() == 0


class TestMqttErrorRecovery:
    """Test MQTT connection failure recovery scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock(spec=skill_config.SkillConfig)
        self.mock_config.client_id = "test_recovery_skill"
        self.mock_config.skill_id = "test_recovery_skill"
        self.mock_config.intent_analysis_result_topic = "test/recovery_intent"
        self.mock_config.broadcast_topic = "test/recovery_broadcast"
        self.mock_config.intent_cache_size = 1000

    @pytest.mark.asyncio
    async def test_mqtt_publish_retry_logic(self):
        """Test MQTT publish with retry on failure."""
        mock_mqtt_client = AsyncMock()
        task_group = AsyncMock()
        mock_engine = AsyncMock()

        skill = TestConcurrentSkill(
            config_obj=self.mock_config,
            mqtt_client=mock_mqtt_client,
            task_group=task_group,
            engine=mock_engine,
        )

        # Configure mock to fail first two attempts, succeed on third
        mock_mqtt_client.publish.side_effect = [
            Exception("Connection lost"),
            Exception("Network error"),
            None,  # Success
        ]

        client_request = ClientRequest(
            id=uuid.uuid4(), text="test retry message", room="test_room", output_topic="test/output"
        )

        # Test with retry logic
        success = await skill.send_response("Test response", client_request)

        # Verify retry occurred and eventually succeeded
        assert success is True
        assert mock_mqtt_client.publish.call_count == EXPECTED_RETRY_COUNT

    @pytest.mark.asyncio
    async def test_mqtt_publish_failure_handling(self):
        """Test handling of persistent MQTT publish failures."""
        mock_mqtt_client = AsyncMock()
        task_group = AsyncMock()
        mock_engine = AsyncMock()

        skill = TestConcurrentSkill(
            config_obj=self.mock_config,
            mqtt_client=mock_mqtt_client,
            task_group=task_group,
            engine=mock_engine,
        )

        # Configure all attempts to fail
        mock_mqtt_client.publish.side_effect = Exception("Persistent failure")

        client_request = ClientRequest(
            id=uuid.uuid4(), text="test failure message", room="test_room", output_topic="test/output"
        )

        # Test failure handling
        success = await skill.send_response("Test response", client_request)

        # Verify failure was handled gracefully
        assert success is False
        assert mock_mqtt_client.publish.call_count == EXPECTED_TOTAL_ATTEMPTS  # Initial + 3 retries

    @pytest.mark.asyncio
    async def test_concurrent_mqtt_operations(self):
        """Test concurrent MQTT publish operations."""
        mock_mqtt_client = AsyncMock()
        task_group = AsyncMock()
        mock_engine = AsyncMock()

        skill = TestConcurrentSkill(
            config_obj=self.mock_config,
            mqtt_client=mock_mqtt_client,
            task_group=task_group,
            engine=mock_engine,
        )

        # Configure some operations to succeed, others to fail
        publish_results = [
            None,  # Success
            Exception("Temporary failure"),
            None,  # Success
            Exception("Another failure"),
            None,  # Success (after retry)
            None,  # Success (after retry)
        ]
        mock_mqtt_client.publish.side_effect = publish_results

        # Create multiple concurrent publish operations
        client_requests = []
        for i in range(3):
            client_request = ClientRequest(
                id=uuid.uuid4(), text=f"concurrent message {i}", room="test_room", output_topic=f"test/output_{i}"
            )
            client_requests.append(client_request)

        # Execute concurrent publishes
        tasks = [skill.send_response(f"Response {i}", req) for i, req in enumerate(client_requests)]

        results = await asyncio.gather(*tasks)

        # Verify results (some should succeed after retries)
        success_count = sum(1 for result in results if result)
        assert success_count >= MIN_SUCCESS_COUNT  # At least 2 should succeed

        # Verify retry attempts were made
        assert mock_mqtt_client.publish.call_count >= len(client_requests)
