import uuid

import pytest
from pydantic import ValidationError

from private_assistant_commons import (
    ClientRequest,
    IntentAnalysisResult,
    NumberAnalysisResult,
)

TEST_NUMBER_TOKEN_1 = 5
TEST_NUMBER_TOKEN_2 = 10


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
    number_analysis_result = NumberAnalysisResult(
        number_token=TEST_NUMBER_TOKEN_1, previous_token="bought", next_token="apples"
    )

    assert number_analysis_result.number_token == TEST_NUMBER_TOKEN_1
    assert number_analysis_result.previous_token == "bought"
    assert number_analysis_result.next_token == "apples"

    # Test with optional fields as None
    number_analysis_result_none = NumberAnalysisResult(number_token=TEST_NUMBER_TOKEN_2)

    assert number_analysis_result_none.number_token == TEST_NUMBER_TOKEN_2
    assert number_analysis_result_none.previous_token is None
    assert number_analysis_result_none.next_token is None


def test_intent_analysis_result():
    request_id = uuid.uuid4()
    client_request = ClientRequest(
        id=request_id, text="Turn on the lights", room="living_room", output_topic="topic/output"
    )
    number_analysis_result = NumberAnalysisResult(
        number_token=TEST_NUMBER_TOKEN_1, previous_token="bought", next_token="apples"
    )
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
