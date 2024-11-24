import uuid

from pydantic import BaseModel, Field


class ClientRequest(BaseModel):
    id: uuid.UUID
    text: str
    room: str
    output_topic: str


class NumberAnalysisResult(BaseModel):
    number_token: int
    previous_token: str | None = None
    next_token: str | None = None


class IntentAnalysisResult(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    client_request: ClientRequest
    numbers: list[NumberAnalysisResult]
    nouns: list[str]
    verbs: list[str]
    rooms: list[str] = []


class Alert(BaseModel):
    play_before: bool = False
    play_after: bool = False
    sound: str = "default"


class Response(BaseModel):
    text: str
    alert: Alert | None = None
