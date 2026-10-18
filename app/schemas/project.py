from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


ProjectStatus = Literal["planned", "in_progress", "completed", "on_hold"]


class ProjectCreate(BaseModel):
    client_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: ProjectStatus = "planned"
    budget: Decimal | None = Field(default=None, ge=0)
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project title cannot be empty.")
        return value


class ProjectUpdate(BaseModel):
    client_id: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: ProjectStatus | None = None
    budget: Decimal | None = Field(default=None, ge=0)
    due_date: date | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Project title cannot be null.")
        value = value.strip()
        if not value:
            raise ValueError("Project title cannot be empty.")
        return value


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    title: str
    description: str | None
    status: str
    budget: Decimal | None
    due_date: date | None
    created_at: datetime
    updated_at: datetime
