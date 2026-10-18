from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClientCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    company: str | None = Field(default=None, max_length=150)
    notes: str | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Client name cannot be empty.")
        return value


class ClientUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=150)
    email: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=30)
    company: str | None = Field(default=None, max_length=150)
    notes: str | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Client name cannot be null.")
        value = value.strip()
        if not value:
            raise ValueError("Client name cannot be empty.")
        return value


class ClientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str | None
    phone: str | None
    company: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
