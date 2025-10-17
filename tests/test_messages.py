import uuid

import pytest
from pydantic import ValidationError

from private_assistant_commons import Alert, ClientRequest, Response


class TestClientRequest:
    """Test ClientRequest model."""

    def test_client_request_creation(self):
        """Test creating a client request."""
        request_id = uuid.uuid4()
        request = ClientRequest(
            id=request_id,
            text="Turn on the lights",
            room="living_room",
            output_topic="home/living_room/response",
        )
        assert request.id == request_id
        assert request.text == "Turn on the lights"
        assert request.room == "living_room"
        assert request.output_topic == "home/living_room/response"

    def test_client_request_validation_error(self):
        """Test validation errors for invalid client request."""
        with pytest.raises(ValidationError) as exc_info:
            ClientRequest(
                id="not-a-uuid",
                text=123,  # Should be string
                room=True,  # Should be string
                output_topic=None,  # Required field
            )
        errors = exc_info.value.errors()
        assert len(errors) >= 3  # noqa: PLR2004


class TestAlert:
    """Test Alert model."""

    def test_alert_creation_defaults(self):
        """Test creating an alert with default values."""
        alert = Alert()
        assert alert.play_before is False
        assert alert.play_after is False
        assert alert.sound == "default"

    def test_alert_creation_custom(self):
        """Test creating an alert with custom values."""
        alert = Alert(
            play_before=True,
            play_after=False,
            sound="success",
        )
        assert alert.play_before is True
        assert alert.play_after is False
        assert alert.sound == "success"


class TestResponse:
    """Test Response model."""

    def test_response_creation_minimal(self):
        """Test creating a response with minimal fields."""
        response = Response(text="Lights turned on")
        assert response.text == "Lights turned on"
        assert response.alert is None

    def test_response_creation_with_alert(self):
        """Test creating a response with an alert."""
        alert = Alert(play_after=True, sound="success")
        response = Response(
            text="Task completed",
            alert=alert,
        )
        assert response.text == "Task completed"
        assert response.alert == alert
        assert response.alert.play_after is True
        assert response.alert.sound == "success"

    def test_response_validation_error(self):
        """Test validation errors for invalid response."""
        with pytest.raises(ValidationError) as exc_info:
            Response(text=None)  # text is required
        errors = exc_info.value.errors()
        assert len(errors) >= 1
