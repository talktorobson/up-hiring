# Scripts

## `seed.py` — dados de demo

Popula 2 tenants demo isolados para demo de pipeline e teste de paginação.

```sh
make seed                                  # idempotente (não duplica)
cd apps/api && uv run python -m src.scripts.seed --reset   # recria do zero
```

Gera por tenant: 3 users (+ membership), 5 jobs (cada um com os 7 stages
padrão via `JobService`), 30 candidatos com CPF válido, ~50 applications
espalhadas pelos stages active.

`--reset` apaga **apenas** dados cujo `tenant.clerk_org_id` começa com
`org_demo_` — tenants reais nunca são tocados. RNG com seed fixo (42), então
o conjunto é determinístico.

Requer DB no ar (`make dev-up && make migrate`). Roda em poucos segundos.
