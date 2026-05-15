"""Cursor pagination helper."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from src.models.enums import JobStatus
from src.models.job import Job
from src.utils.pagination import (
    DEFAULT_LIMIT,
    InvalidCursorError,
    decode_cursor,
    encode_cursor,
    paginate,
)


def test_encode_decode_roundtrip():
    when = datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)
    uid = uuid4()
    token = encode_cursor(when, uid)
    cur = decode_cursor(token)
    assert cur.created_at == when
    assert cur.id == uid


def test_decode_cursor_invalid_raises():
    with pytest.raises(InvalidCursorError):
        decode_cursor("not-base64-and-no-pipe")


def test_default_limit_constant():
    assert DEFAULT_LIMIT == 25


async def _seed_jobs(db_session, tenant_id, n: int) -> list[Job]:
    """Cria n jobs com created_at espaçados pra ordenação determinística."""
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    jobs = [
        Job(
            tenant_id=tenant_id,
            title=f"Job {i:02d}",
            employment_type="clt",
            status=JobStatus.OPEN,
            created_at=base + timedelta(minutes=i),
        )
        for i in range(n)
    ]
    db_session.add_all(jobs)
    await db_session.commit()
    return jobs


@pytest.mark.asyncio
async def test_paginate_walks_all_records(db_session, two_tenants):
    a, _, _, _ = two_tenants
    jobs = await _seed_jobs(db_session, a.id, 50)
    # Mais recentes (i=49) devem aparecer primeiro.
    expected_order = sorted(jobs, key=lambda j: (j.created_at, j.id), reverse=True)

    seen = []
    cursor = None
    pages = 0
    while True:
        rows, next_cursor, has_more = await paginate(
            db_session, select(Job).where(Job.tenant_id == a.id), Job,
            cursor=cursor, limit=10,
        )
        pages += 1
        seen.extend(rows)
        if not has_more:
            assert next_cursor is None
            break
        assert next_cursor is not None
        cursor = next_cursor
        assert pages < 20, "loop infinito"

    assert pages == 5  # 50 / 10
    assert len(seen) == 50
    assert [j.id for j in seen] == [j.id for j in expected_order]


@pytest.mark.asyncio
async def test_paginate_limit_caps_at_max(db_session, two_tenants):
    a, _, _, _ = two_tenants
    await _seed_jobs(db_session, a.id, 5)
    rows, next_cursor, has_more = await paginate(
        db_session, select(Job).where(Job.tenant_id == a.id), Job,
        cursor=None, limit=10_000,
    )
    # Tudo cabe em uma página → next_cursor None, has_more False.
    assert len(rows) == 5
    assert not has_more
    assert next_cursor is None
