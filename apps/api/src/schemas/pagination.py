"""Page genérico para endpoints de listagem cursor-based."""
from pydantic import BaseModel


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None = None
    has_more: bool = False
