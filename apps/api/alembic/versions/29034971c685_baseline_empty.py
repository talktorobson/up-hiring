"""baseline empty

Revision ID: 29034971c685
Revises:
Create Date: 2026-05-15 10:09:26.909912

"""
from collections.abc import Sequence

import sqlalchemy as sa  # noqa: F401

from alembic import op  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "29034971c685"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
