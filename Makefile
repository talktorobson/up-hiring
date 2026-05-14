.PHONY: help dev-up dev-down dev-api dev-web migrate seed test lint format clean

help:
	@echo "Targets:"
	@echo "  dev-up      Sobe Postgres + Redis + LocalStack"
	@echo "  dev-down    Derruba os containers de dev"
	@echo "  dev-api     Roda a API FastAPI em modo reload"
	@echo "  dev-web     Roda o Next em modo dev"
	@echo "  migrate     Aplica migrations Alembic"
	@echo "  seed        Roda script de seed"
	@echo "  test        Roda testes (api + web)"
	@echo "  lint        Lint em todo o monorepo"
	@echo "  format      Formata código (ruff + prettier)"
	@echo "  clean       Remove caches e builds"

dev-up:
	docker compose up -d
	@echo "Aguardando Postgres pronto..."
	@until docker compose exec -T postgres pg_isready -U ats -d ats > /dev/null 2>&1; do sleep 1; done
	@echo "Pronto. Postgres: localhost:5432  Redis: localhost:6379  S3: localhost:4566"

dev-down:
	docker compose down

dev-api:
	cd apps/api && uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

dev-web:
	pnpm --filter web dev

migrate:
	cd apps/api && uv run alembic upgrade head

migrate-new:
	cd apps/api && uv run alembic revision --autogenerate -m "$(name)"

seed:
	cd apps/api && uv run python -m src.scripts.seed

test:
	cd apps/api && uv run pytest -v
	pnpm test

lint:
	cd apps/api && uv run ruff check .
	pnpm lint

format:
	cd apps/api && uv run ruff format .
	pnpm format

clean:
	rm -rf node_modules apps/*/node_modules packages/*/node_modules
	rm -rf apps/*/.next apps/*/dist
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
