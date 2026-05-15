"""Cursor-based pagination (`created_at, id`).

- Estável: tie-breaker `id` evita drift quando dois registros têm o mesmo
  `created_at`.
- Mais robusto que offset: inserções no início não geram registros vistos
  duas vezes nem pulados.
- Cursor é opaco (base64) — clientes não devem interpretar.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import and_, or_, tuple_

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy import Select
    from sqlalchemy.ext.asyncio import AsyncSession


DEFAULT_LIMIT = 25
MAX_LIMIT = 100


class InvalidCursorError(ValueError):
    pass


@dataclass(frozen=True)
class Cursor:
    created_at: datetime
    id: UUID


def encode_cursor(created_at: datetime, id_: UUID) -> str:
    raw = f"{created_at.isoformat()}|{id_}".encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def decode_cursor(cursor: str) -> Cursor:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(padded).decode()
        iso, id_str = raw.split("|", 1)
        return Cursor(created_at=datetime.fromisoformat(iso), id=UUID(id_str))
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise InvalidCursorError(f"invalid_cursor: {cursor!r}") from exc


def _clamped_limit(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    if limit < 1:
        return 1
    return min(limit, MAX_LIMIT)


def apply_cursor(stmt: Select[Any], model: Any, cursor: str | None, limit: int) -> Select[Any]:
    """Aplica WHERE (created_at, id) < cursor + ORDER BY (desc, desc) + LIMIT n+1.

    Pegamos `limit + 1` pra saber se há mais sem fazer COUNT(*).
    """
    if cursor is not None:
        cur = decode_cursor(cursor)
        # Keyset paginate: (a, b) < (cur_a, cur_b) ⟺ a < cur_a OR (a = cur_a AND b < cur_b).
        # SQLAlchemy `tuple_(...).self_group() < tuple_(...)` é traduzido por algumas DBs,
        # mas asyncpg lida melhor com a forma explícita abaixo.
        stmt = stmt.where(
            or_(
                model.created_at < cur.created_at,
                and_(model.created_at == cur.created_at, model.id < cur.id),
            )
        )
    return stmt.order_by(model.created_at.desc(), model.id.desc()).limit(limit + 1)


async def paginate(
    session: AsyncSession,
    stmt: Select[Any],
    model: Any,
    *,
    cursor: str | None,
    limit: int | None,
) -> tuple[Sequence[Any], str | None, bool]:
    """Executa a query paginada. Retorna (items, next_cursor, has_more)."""
    eff_limit = _clamped_limit(limit)
    stmt = apply_cursor(stmt, model, cursor, eff_limit)
    result = await session.execute(stmt)
    rows: list[Any] = list(result.scalars().all())
    has_more = len(rows) > eff_limit
    if has_more:
        rows = rows[:eff_limit]
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None
    return rows, next_cursor, has_more


# `tuple_` import kept for callers that want the alt expression style.
__all__ = [
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
    "Cursor",
    "InvalidCursorError",
    "apply_cursor",
    "decode_cursor",
    "encode_cursor",
    "paginate",
    "tuple_",
]
