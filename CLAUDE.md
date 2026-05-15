# UpHiring — Claude project notes

> Herda do `personal/CLAUDE.md` (preferências gerais, git author, R$/CPF, never-expose-service_role, RLS obrigatório em novas tabelas). Aqui só o que é específico do up-hiring.

ATS para SME serviços/comércio no Brasil. Side project paralelo ao BPO RH (migração gradual a partir do Workable entre M18 e M24). Repo: https://github.com/talktorobson/up-hiring (público — necessário pra branch protection no plano free do GitHub).

## Stack

| Camada | Tecnologia | Onde roda |
|---|---|---|
| Web | Next.js 14 (App Router) + TS + Tailwind + shadcn + Clerk | Vercel (`up-hiring-frontend`) |
| API | FastAPI + SQLAlchemy 2 async + Alembic + Pydantic 2 | Fly.io (`up-hiring-api`, region `gru`) |
| DB | Postgres 17 + RLS multi-tenant | Supabase São Paulo (`sa-east-1`) |
| Storage | S3-compatible | Supabase Storage (`up-hiring-prod`) |
| Auth | Clerk com Organizations (multi-tenant) | Clerk dev tier |
| Observability | Sentry + Pydantic Logfire | free tiers |
| Monorepo | Turborepo + PNPM workspaces | local |

## Local dev — Colima obrigatório

**Este Mac não tem Docker Desktop.** Use Colima como runtime + `docker` CLI do brew. Não tente instalar Docker Desktop.

Pré-requisitos: `brew`, `node 20+`, `pnpm 9`, `uv`, `git`, mais:

```sh
brew install colima docker docker-compose
colima start --cpu 2 --memory 4 --disk 30
# Colima cria o contexto docker automaticamente.
# Confirme: `docker info | head -3` deve mostrar "Server Version".
```

Se `docker compose` reclamar de plugin não encontrado, garanta que `~/.docker/config.json` tem:
```json
{ "cliPluginsExtraDirs": ["/opt/homebrew/lib/docker/cli-plugins"] }
```

Loop completo (sub-4min com Colima já rodando, sub-15min from-scratch — validado em #12):

```sh
pnpm install --frozen-lockfile
cd apps/api && uv sync && cd ../..
make dev-up      # postgres :5432 + redis :6379 + localstack :4566
make migrate     # alembic upgrade head
make dev-api     # uvicorn :8000 com --reload
make dev-web     # next dev :3000
```

### Convenção de env files

| Arquivo | O que é | Gitignored? |
|---|---|---|
| `.env` | Dev local (DATABASE_URL → localhost, S3 → localstack, etc.). Clerk/Sentry/Logfire podem ser as mesmas de prod (dev keys) | sim |
| `.env.prod` | Valores prod completos (Supabase SP, real Sentry, real Logfire). Usado pra testar conectividade contra prod ou rodar local apontando pra prod via `cp .env.prod .env` | sim |
| `.env.example` | Template documentado | **tracked** |

`.gitignore` usa `.env.*` + `!.env.example`. Nunca `git add -A` sem checar — `.env.prod` tem service role key da Supabase e secret key do Clerk.

## Footguns do projeto (cada um já mordeu uma vez)

- **`DATABASE_URL` precisa do driver `+asyncpg`** — Supabase serve `postgresql://...`, SQLAlchemy resolve pra psycopg2 (sync) e `create_async_engine` recusa. Toda criação de engine deve passar pelo helper `ensure_async_driver()` em `apps/api/src/db/url.py`. Aplicado em `src/db/session.py` e `alembic/env.py` (PRs #17, #19).

- **`ClerkAuthMiddleware` retorna `JSONResponse`, NÃO `raise HTTPException`** — `BaseHTTPMiddleware` engole exceções e devolve 500 genérico. Usar o helper `_unauthorized()` no topo de `apps/api/src/middleware/clerk.py` (issue #24, PR #25). Mesma armadilha se adicionar outro middleware ASGI.

- **`apps/web/middleware.ts` é obrigatório** — sem `clerkMiddleware()` registrado, qualquer Server Component do Clerk (`SignedIn`, `SignedOut`, `SignInButton`, `UserButton`, `auth()`) 500a em runtime. CI passa porque `next build` só prerendera (PR #14).

- **`apps/web/next.config.mjs` envolto em `withSentryConfig(...)`** — sem isso, `sentry.client.config.ts` não é injetado no bundle e o SDK client-side nunca inicializa. `instrumentation.ts` cobre só server/edge (PR #23).

- **`turbo.json > tasks.build.env`** — Turborepo só passa pro build as env vars listadas. Adicionar lá qualquer `NEXT_PUBLIC_*` ou env de build novo, senão Vercel logga "WILL NOT be available to your application".

- **LocalStack pinned em `:3`** — `localstack/localstack:latest` virou paywalled (exit 55 sem `LOCALSTACK_AUTH_TOKEN`). v3 community ainda tem S3 free, suficiente pra dev (PR #26).

- **Rotas catch-all do Clerk** — `apps/web/app/sign-in/[[...sign-in]]/page.tsx` e `apps/web/app/sign-up/[[...sign-up]]/page.tsx` montam o widget. Sem elas, deep-links em emails Clerk 404am (PR #15).

- **`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` = `CLERK_PUBLISHABLE_KEY`** — é a mesma chave nas duas vars (uma é exposta ao client via Next, outra ao server). Discrepância quebra `<ClerkProvider>` no frontend.

## Git / repo

- `main` é protegida: PR obrigatório, status checks `api` + `web` exigidos, linear history, force-push e delete bloqueados. Owner pode `gh pr merge --admin` em casos extremos (review automática de bot deixa o PR `BLOCKED` mesmo com tudo verde).
- Default merge: `gh pr merge <n> --squash --delete-branch`.
- Repo é **público**. Trocar pra privado destrava branch protection no plano free do GitHub.

## Deploy

**API** — push em `apps/api/**` ou no próprio workflow dispara `.github/workflows/deploy-api.yml`:
- `flyctl deploy --remote-only --strategy rolling` constrói imagem e provisiona machine.
- `[deploy].release_command = 'uv run alembic upgrade head'` no `fly.toml` roda migrations em VM efêmera antes do tráfego mudar (NÃO via `flyctl ssh console` — máquina fica parada por `auto_stop_machines='stop'`).
- Cold start ~22s na primeira request (free tier, `min_machines_running=0`).
- Smoke: `curl https://up-hiring-api.fly.dev/health` → `{"status":"ok"}`.

**Web** — qualquer push em `main` dispara redeploy automático na Vercel:
- Project: `up-hiring-frontend`, root directory `apps/web`, framework Next.js.
- Env vars (Production + Preview): `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_CLERK_SIGN_{IN,UP}_URL`, `NEXT_PUBLIC_SENTRY_DSN`.
- Smoke: `https://up-hiring-frontend.vercel.app/` → 200, HTML contém `<title>UpHiring</title>` e o botão "Entrar".

## Convenções do projeto

- **Nova rota API**: arquivo em `apps/api/src/api/v1/<resource>.py`, registrar router em `apps/api/src/api/v1/__init__.py`. Se for público (sem JWT), adicionar o path em `PUBLIC_PATHS` no `middleware/clerk.py` (já contém `/health`, `/docs`, `/openapi.json`, `/api/v1/webhooks/clerk`).
- **RLS multi-tenant**: cada sessão SQLAlchemy define `SET LOCAL app.current_tenant_id` via `apps/api/src/db/session.py:get_db`. Toda nova tabela com `tenant_id` precisa de policy em `apps/api/src/db/rls.py`. **Nunca** use `service_role` ou bypass de RLS no código de aplicação.
- **Web**: Next 14 App Router; componentes Clerk em Server Components por padrão. Tailwind classes diretas (sem `cn()` se desnecessário).
- **Testes**: pytest em `apps/api/tests/` roda no CI. Pra testar middleware/auth, usar `TestClient` + `jwt.encode` (referência: `apps/api/tests/test_clerk_middleware.py`).

## Common mistakes

- Criar engine SQLAlchemy sem `ensure_async_driver` → asyncpg error
- `raise HTTPException` em middleware → 500 mascarado
- `docker compose up -d` sem confirmar `localstack:3` no compose → exit 55
- `git add -A` sem checar `.env.*` antes
- `gh pr merge` sem `--admin` quando o bot review automática deixou o PR `BLOCKED`
- Adicionar `NEXT_PUBLIC_*` no Vercel sem listar em `turbo.json[build].env`

## Arquivos-chave (referência rápida)

```
apps/api/
  src/db/url.py              # ensure_async_driver()
  src/db/session.py          # engine + current_tenant_id ContextVar
  src/db/rls.py              # policies (placeholder por enquanto)
  src/middleware/clerk.py    # _unauthorized(), PUBLIC_PATHS, JWT decode
  src/api/v1/__init__.py     # registry de routers
  src/api/v1/webhooks.py     # placeholder Clerk webhook (svix verify)
  fly.toml                   # release_command, region gru, auto_stop
  Dockerfile                 # uv-based build
  alembic/env.py             # usa ensure_async_driver
  tests/test_clerk_middleware.py

apps/web/
  middleware.ts              # clerkMiddleware()
  next.config.mjs            # withSentryConfig wrap
  instrumentation.ts         # Sentry server + edge hook
  sentry.{client,server,edge}.config.ts
  app/sign-in/[[...sign-in]]/page.tsx
  app/sign-up/[[...sign-up]]/page.tsx
  app/layout.tsx             # ClerkProvider
  .eslintrc.json             # next/core-web-vitals

turbo.json                   # tasks.build.env passa NEXT_PUBLIC_* etc
docker-compose.yml           # localstack:3 pin
Makefile                     # dev-up / migrate / dev-api / dev-web
.github/workflows/ci.yml     # api + web jobs
.github/workflows/deploy-api.yml  # Fly deploy on push apps/api/**
```
