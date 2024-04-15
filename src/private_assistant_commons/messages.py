import uuid

from pydantic import BaseModel


class SkillCertainty(BaseModel):
    message_id: uuid.UUID
    certainty: float
    skill_id: str


class SkillRegistration(BaseModel):
    skill_id: str
    feedback_topic: str


class ClientRequest(BaseModel):
    id: uuid.UUID
    text: str
    room: str
    output_topic: str
