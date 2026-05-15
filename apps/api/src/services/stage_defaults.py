"""5 stages active + 2 terminais — seedados na criação de cada Job.

Customização de stages por tenant entra na Fase 1. Sprint 3 mantém esses 7
fixos pra eliminar fricção do MVP.
"""
from src.models.enums import StageKind

DEFAULT_STAGES: tuple[tuple[str, int, StageKind], ...] = (
    ("Sourced", 0, StageKind.ACTIVE),
    ("Applied", 1, StageKind.ACTIVE),
    ("Screening", 2, StageKind.ACTIVE),
    ("Interview", 3, StageKind.ACTIVE),
    ("Offer", 4, StageKind.ACTIVE),
    ("Hired", 5, StageKind.TERMINAL_HIRED),
    ("Rejected", 6, StageKind.TERMINAL_REJECTED),
)
