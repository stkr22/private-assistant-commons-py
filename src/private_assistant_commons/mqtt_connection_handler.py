import asyncio

import aiomqtt

from private_assistant_commons import skill_logger

logger = skill_logger.SkillLogger.get_logger(__name__)


async def mqtt_connection_handler(
    skill_class,
    mqtt_config: dict,
    retry_interval: int = 5,
    num_workers: int = 2,
    *args,
    **kwargs,
):
    """Handles MQTT connection, retry mechanism, and initializes the skill instance."""
    while True:
        try:
            async with aiomqtt.Client(**mqtt_config, logger=logger) as mqtt_client:
                logger.info("Connected successfully to MQTT broker.")

                # Create and manage the task group context
                async with asyncio.TaskGroup() as tg:
                    # Initialize the skill instance with the TaskGroup and any additional arguments
                    skill_instance = skill_class(mqtt_client=mqtt_client, task_group=tg, *args, **kwargs)

                    # Set up subscriptions
                    await skill_instance.setup_subscriptions()

                    # Add the MQTT listener task to the task group
                    tg.create_task(skill_instance.listen_to_messages(mqtt_client))

                    # The context block will handle the lifecycle of the task group and all tasks inside it

        except aiomqtt.MqttError:
            logger.error("Connection lost; reconnecting in %d seconds...", retry_interval)
            await asyncio.sleep(retry_interval)
