# UpHiring — RUNBOOK

Guia operacional. Para contexto de produto/arquitetura veja `README.md` e
`CLAUDE.md`. Footguns conhecidos vivem no `CLAUDE.md` (seção "Footguns").

## 1. Subir o dev local

Pré: `brew`, `node 20+`, `pnpm 9`, `uv`, Colima (este Mac **não** tem Docker
Desktop — ver `CLAUDE.md`).

```sh
git clone https://github.com/talktorobson/up-hiring && cd up-hiring
cp .env.example .env            # ajuste Clerk/Sentry/Logfire (ver §3)
colima start --cpu 2 --memory 4 --disk 30
# Colima nem sempre cria/aponta o contexto docker:
docker info | grep -q "Server Version" || {
  docker context create colima --docker "host=unix://$HOME/.colima/default/docker.sock"
  docker context use colima
}
# `docker compose` sem plugin? ver CLAUDE.md (cliPluginsExtraDirs)
pnpm install --frozen-lockfile
cd apps/api && uv sync && cd ../..
make dev-up        # postgres :5432 + redis :6379 + localstack :4566
make migrate       # alembic upgrade head
make seed          # 2 tenants demo (idempotente; --reset recria)
make dev-api       # uvicorn :8000
make dev-web       # next :3000
```

> **Após CADA `git pull`: `pnpm install` antes de qualquer `make dev-*`.**
> Os targets do Makefile não rodam install; deps faltando fazem o
> `next dev` morrer com o erro enganoso `The 'border-border' class does
> not exist`. Se já tinha rodado o dev: `rm -rf apps/web/.next` também.

> **`.next` fora do Google Drive.** O sync do Drive corrompe o cache do
> Next (sintoma: `/_next/static/*` 404, HTML serve mas assets não). Next
> força `distDir` relativo ao projeto, então `make dev-web` faz `.next`
> virar **symlink** pra `$HOME/.cache/up-hiring/next` (override `NEXT_CACHE`).
> Rode via `make dev-web` (não `pnpm --filter web dev` cru). CI/Vercel não
> rodam o target → `.next` normal lá.

Smoke: `curl localhost:8000/health` → `{"status":"ok"}`; `localhost:3000`
mostra a landing com botão "Entrar". Seed esperado: 2 tenants · 10 jobs ·
70 stages · 60 candidatos · 100 applications.

## 2. Comandos

| Ação | Comando |
|---|---|
| Migrations | `make migrate` |
| Nova migration | `make migrate-new name="msg"` |
| Seed demo | `make seed` · recriar: `cd apps/api && uv run python -m src.scripts.seed --reset` |
| Testes API | `cd apps/api && uv run pytest` |
| Lint API | `cd apps/api && uv run ruff check .` |
| Lint/build web | `pnpm --filter web lint` · `pnpm --filter web build` |
| E2E (stack no ar) | `pnpm --filter web e2e` |

## 3. Onde estão as keys

1Password, vault **`uphiring`**: Clerk (pub/secret/webhook), Sentry DSN,
Logfire token (API e `NEXT_PUBLIC_LOGFIRE_TOKEN`), Supabase service role.
Nunca commitar — `.gitignore` cobre `.env*` exceto `.env.example`.
`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` == `CLERK_PUBLISHABLE_KEY` (mesma chave).

## 4. Vercel preview por PR

Projeto `up-hiring-frontend`, root `apps/web`, framework Next. O build usa
`apps/web/vercel.json`:

```json
{ "buildCommand": "cd ../.. && pnpm turbo build --filter=web",
  "installCommand": "cd ../.. && pnpm install --frozen-lockfile",
  "framework": "nextjs" }
```

Esse `buildCommand` explícito evita o Turborepo pegar path errado no monorepo
(risco #5 do Sprint 4). Toda PR gera um preview; env vars Preview na Vercel:
`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, `NEXT_PUBLIC_API_URL`
(→ Fly), `NEXT_PUBLIC_CLERK_SIGN_{IN,UP}_URL`, `NEXT_PUBLIC_SENTRY_DSN`,
`NEXT_PUBLIC_LOGFIRE_TOKEN`. Toda `NEXT_PUBLIC_*` nova precisa estar em
`turbo.json > tasks.build.env`.

## 5. Debug de RLS

Conecte como `uphiring_app` (não como `ats`/superuser — superuser dá
BYPASSRLS e mascara o problema):

```sql
SET ROLE uphiring_app;
SET app.current_tenant_id = '<tenant-uuid>';
SELECT id, title, tenant_id FROM job;          -- só o tenant setado
RESET app.current_tenant_id;                    -- agora some tudo (RLS)
SELECT id, clerk_org_id, name FROM tenant;      -- mapear org→tenant
```

## 6. Troubleshooting (top 5)

1. **Clerk webhook não materializa tenant** → login cai em `/select-org` em
   loop. Cheque o endpoint `/api/v1/webhooks/clerk` (svix secret) e se o
   `organization.created` chegou; reenvie pelo dashboard Clerk.
2. **JWKS cache stale** → 401 após rotação de chave. Reinicie a API (cache
   em processo) ou aguarde o TTL.
3. **RLS mostrando vazio** → sessão sem `SET LOCAL app.current_tenant_id`
   (ver `apps/api/src/db/session.py`) ou rodando como superuser nos testes
   (use o fixture `app_role_session`).
4. **Migration falha no deploy** → `[deploy].release_command` no `fly.toml`
   roda `alembic upgrade head` em VM efêmera; veja logs `flyctl logs`. Não
   rode migration via `flyctl ssh` (máquina pode estar parada).
5. **Vercel build erro** → quase sempre `NEXT_PUBLIC_*` faltando em
   `turbo.json[build].env` ("WILL NOT be available") ou env var ausente no
   projeto Vercel; `lib/env.ts` falha o boot com mensagem zod clara.

## 7. Demo

Loom/OBS de ~90s mostrando: login → criar vaga → adicionar candidato →
arrastar stage no Kanban → refresh persiste → trocar org não vê a vaga.
Link: _(adicionar após gravar)_.

## 8. Setup externo pendente (Fase 0 → ativar)

Itens que dependem das suas contas (código já wired, só faltam credenciais):

> Progresso (2026-05-18): Fases A, B-1 (tunnel→local), B-2 (webhook
> Clerk→Fly→Supabase 200 `dispatched`) e C verificadas; Fly billing
> restaurado, API redeployada (#100 CORS + #102 Clerk `o.id` + #105
> telemetry live). **Phase D verificada** via delta no Supabase prod
> (preview Vercel → Clerk → Fly → Supabase: job/stage/candidate/
> application/activity materializados). Esta seção fica como referência
> de re-setup.

- [x] **Clerk Dev**: app com Organizations habilitado; keys no `.env` e
      Vercel Preview.
- [x] **Vercel Preview env vars**: setadas (§4) — Phase D verificada
      (preview → API Fly live → Supabase prod, delta confirmado).
- [x] **Clerk E2E** (Phase E): happy-path **single-user** verde
      (login → cria vaga → candidato → arrasta stage → refresh persiste).
      O 2º user / RLS cross-org foi removido do E2E — limitação estrutural
      do `@clerk/testing` multi-user numa instância **dev** (a 2ª sessão
      não persiste); RLS já coberto em `apps/api/tests/test_rls*.py`.
      Follow-up: **issue #108** (revisitar com instância Clerk prod).
      GitHub Actions secrets (repo settings → Secrets → Actions):

      | Secret | Onde achar |
      |---|---|
      | `E2E_USER_A_EMAIL` / `…_PASSWORD` | credenciais do test user A |
      | `E2E_CLERK_USER_A_ID` | Clerk Dashboard → Users → user → ID `user_…` |
      | `E2E_CLERK_ORG_A_ID` | Clerk Dashboard → Organizations → org → ID `org_…` |
      | `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk → API Keys (mesma instância do user) |
      | `CLERK_SECRET_KEY` | Clerk → API Keys |

      ⚠️ Cole os secrets **sem espaço/newline à toa** — o spec faz
      `.trim()` defensivo, mas Clerk rejeita identifier com whitespace
      (`Identifier is invalid`). Os IDs `org_…`/`user_…` (A) são
      consumidos por `src.scripts.seed_e2e` no workflow: em CI o webhook
      do Clerk não dispara, então o seed provisiona Tenant+AppUser+
      Membership pros IDs reais — sem isso o happy-path daria 403
      `tenant_not_provisioned`. (`e2e.yml`/`seed_e2e` ainda aceitam os
      secrets `…_B_…` — inertes hoje, prontos pro follow-up #108.)
      Faltando qualquer secret de A, o workflow `E2E` faz **skip limpo**
      (não bloqueia merge).
- [ ] **Sentry**: rodar `pnpm dlx @sentry/wizard@latest -i nextjs --saas`
      (projeto `uphiring-web`) ou confirmar o DSN atual; setar
      `NEXT_PUBLIC_SENTRY_DSN`.
- [ ] **Logfire web**: setar `NEXT_PUBLIC_LOGFIRE_TOKEN` (Vercel Preview +
      `.env`) pra ativar traces do browser (no-op sem o token).
- [ ] **Branch protection** (opcional): adicionar `e2e` aos required checks
      **depois** que os secrets de Clerk E2E estiverem no lugar e o
      workflow tiver passado verde ao menos uma vez.
- [ ] **Demo 90s**: gravar e colar o link em §7.
