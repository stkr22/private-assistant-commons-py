"""MQTT connection management with automatic retry logic for skills.

Provides resilient MQTT connectivity that handles reconnections and
integrates with the skill lifecycle management.
"""
import asyncio
import logging

import aiomqtt

from private_assistant_commons import SkillConfig


# AIDEV-NOTE: Main entry point for skill lifecycle - handles MQTT connection and retry logic
async def mqtt_connection_handler(
    skill_class,
    skill_config: SkillConfig,
    retry_interval: int = 5,
    logger: logging.Logger | None = None,
    **kwargs,
):
    """Handle MQTT connection lifecycle and skill initialization.
    
    Manages MQTT connection with automatic retry on failure and provides
    a complete skill runtime environment with task management.
    
    Args:
        skill_class: Class that inherits from BaseSkill to instantiate
        skill_config: MQTT and topic configuration
        retry_interval: Seconds to wait between reconnection attempts
        logger: Optional custom logger
        **kwargs: Additional arguments passed to skill constructor
        
    The function runs indefinitely, handling:
    1. MQTT connection establishment
    2. Skill instantiation and setup
    3. Task group management for concurrent operations
    4. Automatic reconnection on connection loss
    """
    if not logger:
        logger = logging.getLogger()
    if skill_config.mqtt_server_host and skill_config.mqtt_server_port:
        client = aiomqtt.Client(skill_config.mqtt_server_host, port=skill_config.mqtt_server_port, logger=logger)
    else:
        raise ValueError("Unknown mqtt config option combination.")
    while True:
        try:
            async with client as mqtt_client:
                logger.info("Connected successfully to MQTT broker.")

                # Create and manage the task group context
                async with asyncio.TaskGroup() as tg:
                    # Initialize the skill instance with the TaskGroup and any additional arguments
                    skill_instance = skill_class(
                        mqtt_client=mqtt_client, task_group=tg, logger=logger, config_obj=skill_config, **kwargs
                    )

                    # Set up subscriptions
                    await skill_instance.setup_mqtt_subscriptions()
                    await skill_instance.skill_preparations()

                    # Add the MQTT listener task to the task group
                    tg.create_task(skill_instance.listen_to_messages(mqtt_client))

                    # The context block will handle the lifecycle of the task group and all tasks inside it

        except aiomqtt.MqttError:
            logger.error("Connection lost; reconnecting in %d seconds...", retry_interval, exc_info=True)
            await asyncio.sleep(retry_interval)
