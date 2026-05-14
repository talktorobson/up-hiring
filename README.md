# UpHiring

ATS (Applicant Tracking System) focado no mercado brasileiro, segmento SME serviços e comércio.

Side project paralelo ao BPO RH, com objetivo de migração gradual a partir do Workable entre M18 e M24 do BPO.

## Stack final (Fase 0 e Fase 1)

| Camada | Tecnologia | Hospedagem | Custo Fase 0 |
|---|---|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind, Shadcn UI | **Vercel** (free tier) | USD 0 |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 async, Pydantic 2 | **Fly.io** (free tier, region `gru` São Paulo) | USD 0 |
| Banco | PostgreSQL 16 com Row Level Security | **Supabase** (region São Paulo, free tier 500 MB) | USD 0 |
| Storage | S3 compatible (CV, contratos) | **Supabase Storage** (1 GB free tier) | USD 0 |
| Auth + Organizations | Clerk (com Organizations nativo, MFA, social login) | **Clerk** (free tier até 10k MAU) | USD 0 |
| Async/Jobs | RQ + Redis | **Upstash** free OU Fly.io Redis | USD 0 |
| Migrations | Alembic | (parte do backend) | |
| Observability | Sentry + Pydantic Logfire | (free tiers) | USD 0 |
| Monorepo | Turborepo + PNPM workspaces | (local) | |

**Custo total Fase 0: USD 0 a USD 1/mês.**

Plano B documentado: Hetzner CX22 (EUR 6/mês) com Docker Compose + Caddy. Use se Fly.io passar de USD 50/mês ou se precisar hospedar mais serviços no mesmo VPS. Arquivos `docker-compose.prod.yml` e `Caddyfile` ficam no repo como referência.

## Estrutura

```
up-hiring/
├── apps/
│   ├── api/                       # Backend FastAPI (deploy Fly.io)
│   │   ├── src/
│   │   ├── alembic/
│   │   ├── fly.toml               # Fly.io config
│   │   ├── Dockerfile
│   │   └── pyproject.toml
│   └── web/                       # Frontend Next.js (deploy Vercel)
│       ├── app/
│       ├── vercel.json
│       └── package.json
├── packages/
│   └── shared-types/              # TS types compartilhados
├── docker-compose.yml             # Dev local (Postgres + Redis + LocalStack)
├── docker-compose.prod.yml        # Plano B Hetzner (não usado por padrão)
├── Caddyfile                      # Plano B Hetzner
├── .github/workflows/             # CI + deploy Fly.io
├── pnpm-workspace.yaml
├── turbo.json
└── Makefile
```

## Setup local (15 minutos)

Pré requisitos: Node 20+, Python 3.12+, Docker, PNPM 9, uv, Fly.io CLI (`flyctl`).

```bash
# 1. Clone
git clone git@github.com:talktorobson/up-hiring.git
cd up-hiring

# 2. Configurar env
cp .env.example .env
# Edite .env com chaves Clerk dev, Supabase connection string e demais

# 3. Instalar deps
pnpm install
cd apps/api && uv sync && cd ../..

# 4. Subir Postgres + Redis + LocalStack locais (dev rápido, sem depender de Supabase no cycle)
make dev-up

# 5. Migrations
make migrate

# 6. Rodar tudo (terminais separados)
make dev-api    # FastAPI em http://localhost:8000
make dev-web    # Next em http://localhost:3000
```

## Setup das contas (Fase 0 Sprint 1)

1. **Supabase**
   1. Cria projeto em `app.supabase.com` na region South America (São Paulo).
   2. Em Settings > Database, copia a connection string (modo "Session pooler" porta 5432 para Alembic, modo "Transaction pooler" porta 6543 para SQLAlchemy async).
   3. Em Settings > API, copia `service_role` key para uso no backend.
   4. Em Storage, cria bucket `up-hiring-prod` (public read off).
   5. Coloca no `.env`.

2. **Clerk**
   1. Cria app em `dashboard.clerk.com`, ativa Organizations.
   2. Copia `publishable key` e `secret key` para `.env`.
   3. Configura webhook endpoint apontando para `https://SEU_API.fly.dev/api/v1/webhooks/clerk` (após primeiro deploy), eventos `organization.created`, `user.created`. Copia webhook secret.

3. **Vercel**
   1. Conecta o repo GitHub.
   2. Importa o projeto, root directory `apps/web`.
   3. Adiciona env vars: `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `NEXT_PUBLIC_API_URL` (vai apontar para o domínio Fly.io).
   4. Deploy automático no push para `main`.

4. **Fly.io**
   1. Instala `flyctl`, faz `flyctl auth login`.
   2. No diretório `apps/api`, roda `flyctl launch --no-deploy` (vai detectar Dockerfile, criar app em region `gru`).
   3. Configura secrets: `flyctl secrets set DATABASE_URL=... CLERK_SECRET_KEY=... CLERK_WEBHOOK_SECRET=... SENTRY_DSN=... LOGFIRE_TOKEN=...`.
   4. Deploy: `flyctl deploy`.

5. **Cloudflare DNS**
   1. Aponta `app.seu-dominio.com.br` para Vercel.
   2. Aponta `api.seu-dominio.com.br` para Fly.io (`flyctl certs add api.seu-dominio.com.br`).

## Deploy

`apps/web` deploya em Vercel automaticamente no push para `main`.
`apps/api` deploya em Fly.io via GitHub Actions (workflow `.github/workflows/deploy-api.yml`).

## Princípio RLS importante

Apesar de Supabase oferecer RLS com `auth.uid()` e `auth.jwt()`, **não estamos usando Supabase Auth**. Estamos usando Clerk. Por isso o backend FastAPI seta `app.current_tenant_id` explicitamente via `SET LOCAL` em cada sessão SQLAlchemy (ver `src/db/session.py`). As policies em `src/db/rls.py` leem esse setting. Funciona idêntico em Postgres self hosted ou Supabase, sem depender de auth JWT do Supabase.

## Roadmap

| Fase | Objetivo | Status |
|---|---|---|
| Fase 0 | Foundations (auth, RLS, modelo core, primeiro flow) | em planejamento |
| Fase 1 | Manual to Digital (Kanban, career page básica, emails) | |
| Fase 2 | Distribution + Sourcing (multipost, parsing, WhatsApp) | |
| Fase 3 | Communication + Workflow (self schedule, assessments, automação) | |
| Fase 4 | Brazilian Specifics (Idwall, Clicksign, offer CLT, LGPD) | |
| Fase 5 | eSocial + AI Layer (S-2200, admissional kit, agents) | |

Detalhes do plano da Fase 0: ver `../03_plano_fase0_ats_br.md`.

## Licença

Privado, propriedade do autor.
