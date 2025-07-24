"""Tests for concurrent processing scenarios and edge cases."""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, Mock

import pytest

from private_assistant_commons import messages, skill_config
from private_assistant_commons.base_skill import BaseSkill


class TestConcurrentSkill(BaseSkill):
    """Test skill implementation for concurrent testing."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.processed_messages = []
        self.processing_times = []
        
    async def skill_preparations(self) -> None:
        """Test implementation of skill preparations."""
        pass
        
    async def calculate_certainty(self, intent_analysis_result: messages.IntentAnalysisResult) -> float:
        # Add small delay to simulate real processing
        await asyncio.sleep(0.001)
        return 0.9
        
    async def process_request(self, intent_analysis_result: messages.IntentAnalysisResult) -> None:
        # Track processed messages
        self.processed_messages.append(intent_analysis_result.id)
        await asyncio.sleep(0.001)  # Simulate processing time


class TestConcurrentProcessing:
    """Test concurrent message processing scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_mqtt_client = AsyncMock()
        self.task_group = AsyncMock()
        self.mock_config = Mock(spec=skill_config.SkillConfig)
        self.mock_config.client_id = "test_concurrent_skill"
        self.mock_config.intent_analysis_result_topic = "test/concurrent_intent"
        self.mock_config.broadcast_topic = "test/concurrent_broadcast"
        self.mock_config.intent_cache_size = 1000
    
    @pytest.mark.asyncio
    async def test_concurrent_message_processing(self):
        """Test processing multiple messages simultaneously."""
        skill = TestConcurrentSkill(
            config_obj=self.mock_config,
            mqtt_client=self.mock_mqtt_client,
            task_group=self.task_group,
        )
        
        # Create test messages
        message_count = 10
        test_messages = []
        for i in range(message_count):
            client_request = messages.ClientRequest(
                id=uuid.uuid4(),
                text=f"test message {i}",
                room="test_room",
                output_topic="test/output"
            )
            intent_result = messages.IntentAnalysisResult(
                id=uuid.uuid4(),
                client_request=client_request,
                numbers=[],
                nouns=[f"noun{i}"],
                verbs=[f"verb{i}"],
                rooms=[]
            )
            test_messages.append(intent_result.model_dump_json())
        
        # Process all messages concurrently
        tasks = [
            skill.handle_client_request_message(msg)
            for msg in test_messages
        ]
        
        start_time = asyncio.get_event_loop().time()
        await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()
        
        # Verify all messages were processed
        assert len(skill.processed_messages) == message_count
        
        # Verify concurrent processing (should be faster than sequential)
        processing_time = end_time - start_time
        max_expected_time = message_count * 0.005  # Allow for some overhead
        assert processing_time < max_expected_time, (
            f"Processing took {processing_time:.3f}s, expected < {max_expected_time:.3f}s"
        )
        
        # Verify cache contains all results
        assert len(skill.intent_analysis_results) == message_count
    
    @pytest.mark.asyncio
    async def test_memory_leak_prevention(self):
        """Test that intent cache doesn't grow unbounded."""
        skill = TestConcurrentSkill(
            config_obj=self.mock_config,
            mqtt_client=self.mock_mqtt_client,
            task_group=self.task_group,
        )
        
        # Set smaller cache size for testing
        skill.intent_analysis_results.max_size = 50
        
        # Process more messages than cache size
        message_count = 75
        tasks = []
        for i in range(message_count):
            client_request = messages.ClientRequest(
                id=uuid.uuid4(),
                text=f"cache test {i}",
                room="test_room",
                output_topic="test/output"
            )
            intent_result = messages.IntentAnalysisResult(
                id=uuid.uuid4(),
                client_request=client_request,
                numbers=[],
                nouns=[f"cache_noun{i}"],
                verbs=["cache_verb"],
                rooms=[]
            )
            tasks.append(skill.handle_client_request_message(intent_result.model_dump_json()))
        
        await asyncio.gather(*tasks)
        
        # Verify cache size is bounded
        assert len(skill.intent_analysis_results) <= 50
        assert len(skill.processed_messages) == message_count
    
    @pytest.mark.asyncio 
    async def test_task_lifecycle_management(self):
        """Test task creation, tracking, and cleanup."""
        skill = TestConcurrentSkill(
            config_obj=self.mock_config,
            mqtt_client=self.mock_mqtt_client,
            task_group=self.task_group,
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
    
    @pytest.mark.asyncio
    async def test_concurrent_task_creation(self):
        """Test creating tasks concurrently from multiple coroutines."""
        skill = TestConcurrentSkill(
            config_obj=self.mock_config,
            mqtt_client=self.mock_mqtt_client,
            task_group=self.task_group,
        )
        
        created_tasks = []
        def mock_create_task(coro, name=None):
            task = asyncio.create_task(coro, name=name)
            created_tasks.append(task)
            return task
        
        skill.task_group.create_task = mock_create_task
        
        async def task_creator(creator_id: int):
            """Create multiple tasks from this coroutine."""
            tasks = []
            for i in range(3):
                async def worker_task():
                    await asyncio.sleep(0.001)
                    return f"creator_{creator_id}_task_{i}"
                
                task = skill.add_task(worker_task(), name=f"creator_{creator_id}_task_{i}")
                tasks.append(task)
            
            # Wait for all tasks from this creator
            return await asyncio.gather(*tasks)
        
        # Create tasks from multiple concurrent creators
        creator_count = 4
        creator_tasks = [task_creator(i) for i in range(creator_count)]
        
        results = await asyncio.gather(*creator_tasks)
        
        # Verify all tasks were created and completed
        expected_task_count = creator_count * 3
        assert len(created_tasks) == expected_task_count
        
        # Verify all results were returned
        flat_results = [result for creator_results in results for result in creator_results]
        assert len(flat_results) == expected_task_count


class TestMqttErrorRecovery:
    """Test MQTT connection failure recovery scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock(spec=skill_config.SkillConfig)
        self.mock_config.client_id = "test_recovery_skill"
        self.mock_config.intent_analysis_result_topic = "test/recovery_intent"
        self.mock_config.broadcast_topic = "test/recovery_broadcast"
        self.mock_config.intent_cache_size = 1000
    
    @pytest.mark.asyncio
    async def test_mqtt_publish_retry_logic(self):
        """Test MQTT publish with retry on failure."""
        mock_mqtt_client = AsyncMock()
        task_group = AsyncMock()
        
        skill = TestConcurrentSkill(
            config_obj=self.mock_config,
            mqtt_client=mock_mqtt_client,
            task_group=task_group,
        )
        
        # Configure mock to fail first two attempts, succeed on third
        mock_mqtt_client.publish.side_effect = [
            Exception("Connection lost"),
            Exception("Network error"), 
            None  # Success
        ]
        
        client_request = messages.ClientRequest(
            id=uuid.uuid4(),
            text="test retry message",
            room="test_room",
            output_topic="test/output"
        )
        
        # Test with retry logic
        success = await skill.send_response("Test response", client_request)
        
        # Verify retry occurred and eventually succeeded
        assert success is True
        assert mock_mqtt_client.publish.call_count == 3
    
    @pytest.mark.asyncio
    async def test_mqtt_publish_failure_handling(self):
        """Test handling of persistent MQTT publish failures."""
        mock_mqtt_client = AsyncMock()
        task_group = AsyncMock()
        
        skill = TestConcurrentSkill(
            config_obj=self.mock_config,
            mqtt_client=mock_mqtt_client,
            task_group=task_group,
        )
        
        # Configure all attempts to fail
        mock_mqtt_client.publish.side_effect = Exception("Persistent failure")
        
        client_request = messages.ClientRequest(
            id=uuid.uuid4(),
            text="test failure message",
            room="test_room", 
            output_topic="test/output"
        )
        
        # Test failure handling
        success = await skill.send_response("Test response", client_request)
        
        # Verify failure was handled gracefully
        assert success is False
        assert mock_mqtt_client.publish.call_count == 4  # Initial + 3 retries
    
    @pytest.mark.asyncio
    async def test_concurrent_mqtt_operations(self):
        """Test concurrent MQTT publish operations."""
        mock_mqtt_client = AsyncMock()
        task_group = AsyncMock()
        
        skill = TestConcurrentSkill(
            config_obj=self.mock_config,
            mqtt_client=mock_mqtt_client,
            task_group=task_group,
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
            client_request = messages.ClientRequest(
                id=uuid.uuid4(),
                text=f"concurrent message {i}",
                room="test_room",
                output_topic=f"test/output_{i}"
            )
            client_requests.append(client_request)
        
        # Execute concurrent publishes
        tasks = [
            skill.send_response(f"Response {i}", req)
            for i, req in enumerate(client_requests)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Verify results (some should succeed after retries)
        success_count = sum(1 for result in results if result)
        assert success_count >= 2  # At least 2 should succeed
        
        # Verify retry attempts were made
        assert mock_mqtt_client.publish.call_count >= len(client_requests)


class TestPerformanceUnderLoad:
    """Test system performance under concurrent load."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_config = Mock(spec=skill_config.SkillConfig)
        self.mock_config.client_id = "test_load_skill"
        self.mock_config.intent_analysis_result_topic = "test/load_intent"
        self.mock_config.broadcast_topic = "test/load_broadcast"
        self.mock_config.intent_cache_size = 1000
    
    @pytest.mark.asyncio
    @pytest.mark.performance
    async def test_high_throughput_message_processing(self):
        """Test processing high volume of messages concurrently."""
        mock_mqtt_client = AsyncMock()
        task_group = AsyncMock()
        
        skill = TestConcurrentSkill(
            config_obj=self.mock_config,
            mqtt_client=mock_mqtt_client,
            task_group=task_group,
        )
        
        # Create large number of test messages
        message_count = 100
        test_messages = []
        
        for i in range(message_count):
            client_request = messages.ClientRequest(
                id=uuid.uuid4(),
                text=f"load test message {i}",
                room="load_test_room",
                output_topic="test/load_output"
            )
            intent_result = messages.IntentAnalysisResult(
                id=uuid.uuid4(),
                client_request=client_request,
                numbers=[],
                nouns=[f"load_noun_{i}"],
                verbs=["load_test"],
                rooms=[]
            )
            test_messages.append(intent_result.model_dump_json())
        
        # Process with timing
        start_time = asyncio.get_event_loop().time()
        
        # Process in batches to simulate realistic load
        batch_size = 20
        for i in range(0, message_count, batch_size):
            batch = test_messages[i:i+batch_size]
            tasks = [skill.handle_client_request_message(msg) for msg in batch]
            await asyncio.gather(*tasks)
            
            # Small delay between batches
            await asyncio.sleep(0.001)
        
        end_time = asyncio.get_event_loop().time()
        processing_time = end_time - start_time
        
        # Verify all messages were processed
        assert len(skill.processed_messages) == message_count
        
        # Verify reasonable throughput (messages per second)
        throughput = message_count / processing_time
        assert throughput > 50, f"Throughput {throughput:.1f} msg/s is too low"
        
        # Verify cache management worked correctly
        assert len(skill.intent_analysis_results) <= skill.intent_analysis_results.max_size
    
    @pytest.mark.asyncio
    async def test_resource_cleanup_under_load(self):
        """Test that resources are properly cleaned up under high load."""
        mock_mqtt_client = AsyncMock()
        task_group = AsyncMock()
        
        skill = TestConcurrentSkill(
            config_obj=self.mock_config,
            mqtt_client=mock_mqtt_client,
            task_group=task_group,
        )
        
        # Track task creation and cleanup
        active_tasks = set()
        
        def mock_create_task(coro, name=None):
            task = asyncio.create_task(coro, name=name)
            active_tasks.add(task)
            
            # Add done callback to remove from active set
            def cleanup_task(t):
                active_tasks.discard(t)
            task.add_done_callback(cleanup_task)
            
            return task
        
        skill.task_group.create_task = mock_create_task
        
        # Create many short-lived tasks
        task_count = 50
        
        async def short_task(task_id: int):
            await asyncio.sleep(0.01)
            return task_id
        
        # Add tasks in waves
        wave_size = 10
        for wave in range(task_count // wave_size):
            wave_tasks = []
            for i in range(wave_size):
                task_id = wave * wave_size + i
                task = skill.add_task(short_task(task_id), name=f"wave_{wave}_task_{i}")
                wave_tasks.append(task)
            
            # Wait for wave to complete
            await asyncio.gather(*wave_tasks)
            
            # Verify tasks are cleaned up
            await asyncio.sleep(0.01)  # Allow cleanup callbacks
        
        # Verify all tasks were cleaned up
        assert len(active_tasks) == 0
        assert skill.get_active_task_count() == 0