"""Enums centralizados.

Postgres registra cada enum como um tipo nominal — sem `name` explícito,
SQLAlchemy gera nomes auto que colidem se duas colunas Python apontam para
o mesmo Enum Python (cada uma vira um tipo Postgres independente).

Usar `SAEnum(MyEnum, name="my_enum", create_type=False)` na coluna SQLAlchemy
mantém todas as referências apontando para o mesmo tipo PG.
"""
from enum import StrEnum


class JobStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    PAUSED = "paused"
    CLOSED = "closed"


class EmploymentType(StrEnum):
    CLT = "clt"
    PJ = "pj"
    ESTAGIO = "estagio"
    TEMP = "temp"
    FREELANCER = "freelancer"


class StageKind(StrEnum):
    ACTIVE = "active"
    TERMINAL_HIRED = "terminal_hired"
    TERMINAL_REJECTED = "terminal_rejected"


class ApplicationStatus(StrEnum):
    ACTIVE = "active"
    HIRED = "hired"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ActivityEntityType(StrEnum):
    JOB = "job"
    CANDIDATE = "candidate"
    APPLICATION = "application"


JOB_STATUS_ENUM_NAME = "job_status_enum"
EMPLOYMENT_TYPE_ENUM_NAME = "employment_type_enum"
STAGE_KIND_ENUM_NAME = "stage_kind_enum"
APPLICATION_STATUS_ENUM_NAME = "application_status_enum"
ACTIVITY_ENTITY_TYPE_ENUM_NAME = "activity_entity_type_enum"
