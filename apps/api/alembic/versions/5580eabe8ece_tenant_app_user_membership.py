"""tenant app_user membership

Revision ID: 5580eabe8ece
Revises: 29034971c685
Create Date: 2026-05-15 10:16:00.488336

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from src.db.rls import disable_rls_sql, enable_rls_for_tenant_table, enable_rls_sql

# revision identifiers, used by Alembic.
revision: str = "5580eabe8ece"
down_revision: str | None = "29034971c685"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Tabelas job/stage/candidate/application ficaram fora desta migration.
# Sprint 3 vai materializá-las junto com seus endpoints — manter o autogenerate
# atual desperdiça churn (precisaria refatorar quando os modelos evoluírem).


def upgrade() -> None:
    op.create_table(
        "tenant",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clerk_org_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index(op.f("ix_tenant_clerk_org_id"), "tenant", ["clerk_org_id"], unique=True)

    op.create_table(
        "app_user",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("clerk_user_id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_app_user_clerk_user_id"), "app_user", ["clerk_user_id"], unique=True
    )

    op.create_table(
        "membership",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenant.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "tenant_id", name="uq_membership_user_tenant"),
    )
    op.create_index(op.f("ix_membership_tenant_id"), "membership", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_membership_user_id"), "membership", ["user_id"], unique=False)

    # Application role usada para validar RLS sem BYPASS. Idempotente: roles são
    # cluster-scoped, então re-aplicar a migration em outro DB não pode falhar.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'uphiring_app') THEN
                CREATE ROLE uphiring_app NOLOGIN;
            END IF;
        END
        $$;
        """
    )
    op.execute("GRANT USAGE ON SCHEMA public TO uphiring_app;")
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON tenant, app_user, membership TO uphiring_app;"
    )

    # RLS na tabela tenant: chave é `id`, não `tenant_id`.
    for stmt in enable_rls_for_tenant_table():
        op.execute(stmt)

    # RLS em membership via helper padrão (tenant_id).
    for stmt in enable_rls_sql("membership"):
        op.execute(stmt)

    # app_user é cross-tenant por design — sem RLS, leitura controlada via JOIN.


def downgrade() -> None:
    for stmt in disable_rls_sql("membership"):
        op.execute(stmt)
    for stmt in disable_rls_sql("tenant"):
        op.execute(stmt)

    op.execute(
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON tenant, app_user, membership "
        "FROM uphiring_app;"
    )
    op.execute("REVOKE USAGE ON SCHEMA public FROM uphiring_app;")
    # Role é cluster-scoped: não dropamos, pode ser usado por outros DBs.

    op.drop_index(op.f("ix_membership_user_id"), table_name="membership")
    op.drop_index(op.f("ix_membership_tenant_id"), table_name="membership")
    op.drop_table("membership")

    op.drop_index(op.f("ix_app_user_clerk_user_id"), table_name="app_user")
    op.drop_table("app_user")

    op.drop_index(op.f("ix_tenant_clerk_org_id"), table_name="tenant")
    op.drop_table("tenant")
