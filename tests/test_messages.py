import uuid

import pytest
from private_assistant_commons import (  # Replace 'your_module' with the actual module name
    ClientRequest,
    IntentAnalysisResult,
    NumberAnalysisResult,
    SkillCertainty,
    SkillRegistration,
)
from pydantic import ValidationError


def test_skill_certainty():
    message_id = uuid.uuid4()
    skill_certainty = SkillCertainty(message_id=message_id, certainty=0.95, skill_id="skill_1")

    assert skill_certainty.message_id == message_id
    assert skill_certainty.certainty == 0.95
    assert skill_certainty.skill_id == "skill_1"


def test_skill_registration():
    skill_registration = SkillRegistration(skill_id="skill_1", feedback_topic="topic/feedback")

    assert skill_registration.skill_id == "skill_1"
    assert skill_registration.feedback_topic == "topic/feedback"


def test_client_request():
    request_id = uuid.uuid4()
    client_request = ClientRequest(
        id=request_id, text="Turn on the lights", room="living_room", output_topic="topic/output"
    )

    assert client_request.id == request_id
    assert client_request.text == "Turn on the lights"
    assert client_request.room == "living_room"
    assert client_request.output_topic == "topic/output"


def test_number_analysis_result():
    number_analysis_result = NumberAnalysisResult(number_token=5, previous_token="bought", next_token="apples")

    assert number_analysis_result.number_token == 5
    assert number_analysis_result.previous_token == "bought"
    assert number_analysis_result.next_token == "apples"

    # Test with optional fields as None
    number_analysis_result_none = NumberAnalysisResult(number_token=10)

    assert number_analysis_result_none.number_token == 10
    assert number_analysis_result_none.previous_token is None
    assert number_analysis_result_none.next_token is None


def test_intent_analysis_result():
    request_id = uuid.uuid4()
    client_request = ClientRequest(
        id=request_id, text="Turn on the lights", room="living_room", output_topic="topic/output"
    )
    number_analysis_result = NumberAnalysisResult(number_token=5, previous_token="bought", next_token="apples")
    intent_analysis_result = IntentAnalysisResult(
        client_request=client_request,
        numbers=[number_analysis_result],
        nouns=["lights", "living_room"],
        verbs=["turn", "on"],
    )

    assert intent_analysis_result.client_request == client_request
    assert intent_analysis_result.numbers == [number_analysis_result]
    assert intent_analysis_result.nouns == ["lights", "living_room"]
    assert intent_analysis_result.verbs == ["turn", "on"]


def test_invalid_skill_certainty():
    with pytest.raises(ValidationError):
        SkillCertainty(message_id="invalid_uuid", certainty="high", skill_id=123)


def test_invalid_skill_registration():
    with pytest.raises(ValidationError):
        SkillRegistration(skill_id=123, feedback_topic=456)


def test_invalid_client_request():
    with pytest.raises(ValidationError):
        ClientRequest(id="invalid_uuid", text=123, room=True, output_topic=None)


def test_invalid_number_analysis_result():
    with pytest.raises(ValidationError):
        NumberAnalysisResult(number_token="five", previous_token=123, next_token=456)


def test_invalid_intent_analysis_result():
    request_id = uuid.uuid4()
    client_request = ClientRequest(
        id=request_id, text="Turn on the lights", room="living_room", output_topic="topic/output"
    )
    with pytest.raises(ValidationError):
        IntentAnalysisResult(
            client_request=client_request, numbers="not_a_list", nouns="not_a_list", verbs="not_a_list"
        )


if __name__ == "__main__":
    pytest.main()
