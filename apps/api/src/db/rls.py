"""Helpers para Row Level Security.

Padrão de uso: após criar uma tabela tenant scoped no Alembic,
chamar `enable_rls_for_table('nome_tabela')` na migration.
"""
from sqlalchemy import text


def enable_rls_sql(table_name: str) -> list[str]:
    """SQL para habilitar RLS e criar policy padrão de isolamento por tenant_id."""
    return [
        f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;",
        f"ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;",
        f"""
        CREATE POLICY tenant_isolation_{table_name} ON {table_name}
        USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
        WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
        """,
    ]


def disable_rls_sql(table_name: str) -> list[str]:
    return [
        f"DROP POLICY IF EXISTS tenant_isolation_{table_name} ON {table_name};",
        f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;",
    ]


async def execute_rls_setup(connection, table_name: str) -> None:
    """Executa setup de RLS em uma conexão (uso em migrations Alembic)."""
    for stmt in enable_rls_sql(table_name):
        await connection.execute(text(stmt))
