"""Skill context tracking for stateful decision making.

This module provides context tracking for skills to implement context-aware
intent handling with confidence modifiers based on recent actions.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from private_assistant_commons.intent.models import IntentType


# AIDEV-NOTE: Stateful context tracking for skill-side decision making
class RecentAction(BaseModel):
    """Represents a single recent action in the skill context history."""

    action: str
    executed_at: datetime
    entities: dict[str, Any] = Field(default_factory=dict)


# AIDEV-NOTE: Confidence threshold modifiers for context-aware intent processing
class ConfidenceModifier(BaseModel):
    """Defines how recent intents affect confidence thresholds for other intents.

    When a skill has recently handled certain intents, it may want to lower
    the confidence threshold for related follow-up intents to improve
    conversation flow.

    Example:
        If a user just said "turn on the lights", a follow-up command
        "turn them off" might have lower confidence but should still be handled.
    """

    trigger_intent: IntentType
    lowers_threshold_for: IntentType
    reduced_threshold: float
    time_window_seconds: int = 300  # 5 minutes by default


class SkillContext(BaseModel):
    """Context tracking for skill-side decision making.

    Provides utilities for tracking recent actions and querying context state.
    Skills should implement their own logic for determining whether to handle
    intents based on this context.
    """

    skill_name: str
    recent_actions: list[RecentAction] = Field(default_factory=list)
    command_count_since_last: int = 0
    max_recent_actions: int = 10

    # Expiry settings
    recency_window_seconds: int = 300  # 5 minutes
    max_follow_up_commands: int = 5

    def has_recent_activity(self) -> bool:
        """Check if there are any valid recent actions.

        Returns:
            True if there are recent actions within the recency window
        """
        self._cleanup_expired_actions()
        return len(self.recent_actions) > 0

    def find_recent_action(self, action: str, within_seconds: int | None = None) -> RecentAction | None:
        """Find a specific action in recent history.

        Args:
            action: The action name to search for
            within_seconds: Optional time window to search within (defaults to recency_window_seconds)

        Returns:
            The most recent matching action, or None if not found
        """
        self._cleanup_expired_actions()

        if not self.recent_actions:
            return None

        time_window = within_seconds if within_seconds is not None else self.recency_window_seconds
        cutoff_time = datetime.now().timestamp() - time_window

        # Search backwards through recent actions
        for recent_action in reversed(self.recent_actions):
            if recent_action.action == action and recent_action.executed_at.timestamp() > cutoff_time:
                return recent_action

        return None

    def has_recent_intent(self, intent_type: IntentType | str) -> bool:
        """Check if a specific intent type was recently handled.

        Args:
            intent_type: The intent type to search for

        Returns:
            True if this intent type was recently handled
        """
        intent_str = intent_type.value if isinstance(intent_type, IntentType) else intent_type
        return self.find_recent_action(intent_str) is not None

    def _cleanup_expired_actions(self) -> None:
        """Remove expired actions from the history based on recency window."""
        if not self.recent_actions:
            return

        now = datetime.now()
        cutoff_time = now.timestamp() - self.recency_window_seconds

        # Keep only actions within the recency window
        self.recent_actions = [action for action in self.recent_actions if action.executed_at.timestamp() > cutoff_time]

    def add_action(self, action: str, entities: dict[str, Any] | None = None) -> None:
        """Add a new action to the recent actions history.

        Args:
            action: Name of the action executed
            entities: Optional entities associated with the action
        """
        recent_action = RecentAction(
            action=action,
            executed_at=datetime.now(),
            entities=entities or {},
        )
        self.recent_actions.append(recent_action)

        # Trim to max size
        if len(self.recent_actions) > self.max_recent_actions:
            self.recent_actions = self.recent_actions[-self.max_recent_actions :]

    def get_last_action(self) -> RecentAction | None:
        """Get the most recent action.

        Returns:
            The most recent action, or None if no actions exist
        """
        return self.recent_actions[-1] if self.recent_actions else None

    def get_recent_entities(self, entity_type: str | None = None) -> dict[str, Any]:
        """Get entities from recent actions.

        Args:
            entity_type: Optional filter for specific entity type

        Returns:
            Dictionary of entities from the most recent action, or all recent entities
        """
        if not self.recent_actions:
            return {}

        if entity_type:
            # Search backwards through recent actions for this entity type
            for action in reversed(self.recent_actions):
                if entity_type in action.entities:
                    return {entity_type: action.entities[entity_type]}
            return {}

        # Return all entities from the most recent action
        return self.recent_actions[-1].entities
