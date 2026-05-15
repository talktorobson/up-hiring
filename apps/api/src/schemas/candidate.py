"""Schemas de Candidate.

CPF aceita formatado (`123.456.789-09`) ou cru (`12345678909`). O validator
normaliza para 11 dígitos antes de gravar — UI escolhe o formato que quiser
ler do banco (sempre cru) e formatar na renderização.
"""
import re
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


def _normalize_cpf(value: Any) -> Any:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return re.sub(r"\D", "", value)
    return value


class CandidateCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)
    cpf: str | None = None
    linkedin_url: str | None = Field(default=None, max_length=512)
    source: str | None = Field(default=None, max_length=64)
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _strip_cpf(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data["cpf"] = _normalize_cpf(data.get("cpf"))
        return data


class CandidateUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=255)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    cpf: str | None = None
    linkedin_url: str | None = Field(default=None, max_length=512)
    source: str | None = Field(default=None, max_length=64)
    notes: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _strip_cpf(cls, data: Any) -> Any:
        if isinstance(data, dict) and "cpf" in data:
            data["cpf"] = _normalize_cpf(data["cpf"])
        return data


class CandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    full_name: str
    email: EmailStr
    phone: str | None
    cpf: str | None
    linkedin_url: str | None
    source: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
