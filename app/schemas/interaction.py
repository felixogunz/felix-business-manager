from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


InteractionType = Literal["call", "meeting", "email", "note"]


class InteractionCreate(BaseModel):
    client_id: int = Field(gt=0)
    project_id: int | None = Field(default=None, gt=0)
    interaction_type: InteractionType
    subject: str = Field(min_length=1, max_length=200)
    details: str | None = None
    occurred_at: datetime | None = None

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Interaction subject cannot be empty.")
        return value


class InteractionUpdate(BaseModel):
    client_id: int | None = Field(default=None, gt=0)
    project_id: int | None = Field(default=None, gt=0)
    interaction_type: InteractionType | None = None
    subject: str | None = Field(default=None, min_length=1, max_length=200)
    details: str | None = None
    occurred_at: datetime | None = None

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Interaction subject cannot be null.")
        value = value.strip()
        if not value:
            raise ValueError("Interaction subject cannot be empty.")
        return value


class InteractionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    project_id: int | None
    interaction_type: str
    subject: str
    details: str | None
    occurred_at: datetime
    created_at: datetime
