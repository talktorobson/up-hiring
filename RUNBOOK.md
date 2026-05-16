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
pnpm install --frozen-lockfile
cd apps/api && uv sync && cd ../..
make dev-up        # postgres :5432 + redis :6379 + localstack :4566
make migrate       # alembic upgrade head
make seed          # 2 tenants demo (idempotente; --reset recria)
make dev-api       # uvicorn :8000
make dev-web       # next :3000
```

Smoke: `curl localhost:8000/health` → `{"status":"ok"}`; `localhost:3000`
mostra a landing com botão "Entrar".

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

- [ ] **Clerk Dev**: app `uphiring-dev` com Organizations habilitado; copiar
      keys pro `.env` e Vercel Preview.
- [ ] **Clerk E2E**: 2 test users + 1 org; gravar como GitHub Actions
      secrets `E2E_USER_A_EMAIL/PASSWORD`, `E2E_USER_B_EMAIL/PASSWORD`,
      `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`. Sem isso o
      workflow `E2E` faz skip limpo (não bloqueia merge).
- [ ] **Sentry**: rodar `pnpm dlx @sentry/wizard@latest -i nextjs --saas`
      (projeto `uphiring-web`) ou confirmar o DSN atual; setar
      `NEXT_PUBLIC_SENTRY_DSN`.
- [ ] **Logfire web**: setar `NEXT_PUBLIC_LOGFIRE_TOKEN` (Vercel Preview +
      `.env`) pra ativar traces do browser (no-op sem o token).
- [ ] **Vercel Preview env vars**: ver §4.
- [ ] **Branch protection** (opcional): adicionar `e2e` aos required checks
      depois que os secrets de Clerk E2E estiverem no lugar.
- [ ] **Demo 90s**: gravar e colar o link em §7.
