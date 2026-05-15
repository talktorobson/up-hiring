# UpHiring API

FastAPI + SQLAlchemy 2 (async) + Alembic + Postgres 17. Roda em Fly.io (`up-hiring-api`, region `gru`).

Para o setup completo (Colima, env files, footguns) veja o [`CLAUDE.md`](../../CLAUDE.md) na raiz.

## Quickstart local

```sh
make dev-up          # postgres :5432 + redis :6379 + localstack :4566 (na raiz do repo)
cd apps/api && uv sync
uv run alembic upgrade head    # ou `make migrate` da raiz
uv run uvicorn src.main:app --reload --port 8000
```

Smoke: `curl localhost:8000/health` → `{"status":"ok"}`.

## Migrations Alembic

`alembic.ini` aponta `script_location = alembic`. `env.py` injeta `ensure_async_driver()` em `DATABASE_URL` e importa todos os modelos via `src.models` para popular `Base.metadata`.

### Ciclo de migration

```sh
# 1. Mexeu nos modelos? Gere o diff:
uv run alembic revision --autogenerate -m "descrição curta no imperativo"

# 2. SEMPRE revise o arquivo gerado em alembic/versions/.
#    Autogenerate erra com: enums, índices parciais, server_default,
#    RLS policies (precisa adicionar manual via op.execute).

# 3. Adicione RLS para tabelas tenant scoped:
#    use src.db.rls.enable_rls_sql() — não escreva SQL inline.

# 4. Aplique:
uv run alembic upgrade head     # ou `make migrate`

# 5. Validar reversibilidade antes de commitar:
uv run alembic downgrade -1
uv run alembic upgrade head
```

### Comandos úteis

```sh
uv run alembic current          # revision atual no DB
uv run alembic history --verbose
uv run alembic downgrade base   # zera o schema (cuidado: dropa tudo)
uv run alembic stamp head       # marca o DB como em head sem rodar migrations
```

### Convenções

- Mensagem da revision: lowercase, infinitivo, sem ponto. Ex.: `"create tenant app_user membership"`.
- Uma migration por PR, salvo casos triviais (renames + data fix juntos).
- Nunca editar uma migration já mergeada em `main` — crie nova revision corrigindo.
- Migrations rodam em produção via `release_command` no `fly.toml`, em VM efêmera antes do tráfego mudar.

## Estrutura

```
src/
  main.py                # FastAPI app, middleware order
  config.py              # Pydantic Settings
  api/v1/                # routers REST
  db/
    base.py              # Base, TimestampMixin, TenantScopedMixin
    session.py           # AsyncSessionLocal + current_tenant_id ContextVar
    url.py               # ensure_async_driver() — força +asyncpg
    rls.py               # helpers de policy RLS
  middleware/clerk.py    # JWT verify + tenant resolve
  models/                # SQLAlchemy ORM
alembic/
  env.py                 # async migrations runner
  versions/              # uma file por revision
tests/                   # pytest async
```

## Tests

```sh
make test                # raiz
# ou
cd apps/api && uv run pytest -v
```
