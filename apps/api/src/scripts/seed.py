"""Seed de demo (Sprint 4 #88).

Cria 2 tenants demo isolados, com 3 users, 5 jobs (7 stages cada via
JobService), 30 candidatos (CPF válido) e ~50 applications espalhadas pelos
stages — o suficiente pra demo de pipeline + paginação.

Uso:
    make seed                 # idempotente: se já semeado, não duplica
    uv run python -m src.scripts.seed --reset   # limpa demo antes

Os dados demo são identificados por `tenant.clerk_org_id LIKE 'org_demo_%'`,
então `--reset` nunca toca tenants reais.
"""
from __future__ import annotations

import argparse
import asyncio
import random

from sqlalchemy import delete, select, text

from src.db.session import AsyncSessionLocal
from src.models.application import Application
from src.models.candidate import Candidate
from src.models.enums import EmploymentType, JobStatus, StageKind
from src.models.job import Job
from src.models.stage import Stage
from src.models.tenant import AppUser, Membership, Role, Tenant
from src.schemas.job import JobCreate
from src.services.application import ApplicationDomainError, ApplicationService
from src.services.job import JobService

DEMO_ORG_PREFIX = "org_demo_"

TENANTS = [
    ("org_demo_alpha", "demo-alpha", "Acabamentos Alpha LTDA"),
    ("org_demo_beta", "demo-beta", "Comércio Beta ME"),
]

FIRST_NAMES = [
    "Ana", "Bruno", "Carla", "Diego", "Elaine", "Felipe", "Gabriela",
    "Heitor", "Isabela", "João", "Karina", "Lucas", "Marina", "Nina",
    "Otávio", "Paula", "Rafael", "Sofia", "Tiago", "Vera",
]
LAST_NAMES = [
    "Silva", "Souza", "Oliveira", "Santos", "Pereira", "Lima", "Costa",
    "Almeida", "Ribeiro", "Carvalho", "Gomes", "Martins", "Rocha", "Dias",
]
JOB_TITLES = [
    "Pessoa Vendedora Loja",
    "Auxiliar de Estoque",
    "Atendente de Balcão",
    "Caixa",
    "Supervisor de Loja",
    "Repositor",
    "Consultor de Vendas",
]
LOCATIONS = ["São Paulo, SP", "Campinas, SP", "Guarulhos, SP", "Santo André, SP"]


def _cpf_check_digit(digits: str, weights_start: int) -> int:
    total = sum(int(d) * (weights_start - i) for i, d in enumerate(digits))
    rest = total % 11
    return 0 if rest < 2 else 11 - rest


def gen_cpf(rng: random.Random) -> str:
    """Gera 11 dígitos com DV válido (mesma regra de src.utils.cpf)."""
    while True:
        base = "".join(str(rng.randint(0, 9)) for _ in range(9))
        if base == base[0] * 9:
            continue
        d1 = _cpf_check_digit(base, 10)
        d2 = _cpf_check_digit(base + str(d1), 11)
        return f"{base}{d1}{d2}"


async def reset_demo() -> None:
    """Apaga toda a árvore de dados dos tenants demo (FK-safe order)."""
    async with AsyncSessionLocal() as s:
        rows = await s.execute(
            select(Tenant.id).where(Tenant.clerk_org_id.like(f"{DEMO_ORG_PREFIX}%"))
        )
        ids = [r[0] for r in rows]
        if not ids:
            print("Nenhum tenant demo para limpar.")
            return
        for model in (Application, Stage, Job, Candidate, Membership):
            await s.execute(delete(model).where(model.tenant_id.in_(ids)))
        # activity é tenant-scoped também
        from src.models.activity import Activity

        await s.execute(delete(Activity).where(Activity.tenant_id.in_(ids)))
        # app_user não é tenant-scoped: remove os que só pertenciam a demo
        user_rows = await s.execute(
            select(AppUser.id).where(AppUser.clerk_user_id.like("user_demo_%"))
        )
        await s.execute(
            delete(AppUser).where(
                AppUser.id.in_([r[0] for r in user_rows])
            )
        )
        await s.execute(delete(Tenant).where(Tenant.id.in_(ids)))
        await s.commit()
        print(f"Removidos {len(ids)} tenants demo + dependências.")


async def _already_seeded() -> bool:
    async with AsyncSessionLocal() as s:
        existing = await s.scalar(
            select(Tenant.id).where(
                Tenant.clerk_org_id.like(f"{DEMO_ORG_PREFIX}%")
            )
        )
        return existing is not None


async def seed_tenant(
    clerk_org_id: str, slug: str, name: str, rng: random.Random
) -> None:
    """Cada tenant numa transação própria (SET LOCAL vale só na txn)."""
    async with AsyncSessionLocal() as s:
        tenant = Tenant(clerk_org_id=clerk_org_id, name=name, slug=slug)
        s.add(tenant)
        await s.flush()
        await s.execute(
            text(f"SET LOCAL app.current_tenant_id = '{tenant.id}'")
        )

        users: list[AppUser] = []
        for i in range(3):
            u = AppUser(
                clerk_user_id=f"user_demo_{slug}_{i}",
                email=f"user{i}@{slug}.demo",
                full_name=f"{FIRST_NAMES[i]} {LAST_NAMES[i]}",
            )
            s.add(u)
            users.append(u)
        await s.flush()
        roles = [Role.OWNER, Role.RECRUITER, Role.HIRING_MANAGER]
        for u, role in zip(users, roles, strict=True):
            s.add(Membership(user_id=u.id, tenant_id=tenant.id, role=role))
        await s.flush()
        actor = users[0].id

        jobs: list[Job] = []
        for j in range(5):
            payload = JobCreate(
                title=f"{JOB_TITLES[j % len(JOB_TITLES)]} #{j + 1}",
                description=f"<p>Vaga demo {j + 1} para {name}.</p>",
                location=rng.choice(LOCATIONS),
                employment_type=rng.choice(list(EmploymentType)),
                salary_min=2000 + j * 250,
                salary_max=3500 + j * 250,
                status=JobStatus.OPEN,
            )
            job = await JobService.create(
                s, payload, tenant_id=tenant.id, actor_user_id=actor
            )
            jobs.append(job)

        candidates: list[Candidate] = []
        for c in range(30):
            fn = rng.choice(FIRST_NAMES)
            ln = rng.choice(LAST_NAMES)
            cand = Candidate(
                tenant_id=tenant.id,
                full_name=f"{fn} {ln}",
                email=f"cand{c}@{slug}.demo",
                phone=f"11{rng.randint(900000000, 999999999)}",
                cpf=gen_cpf(rng),
                source=rng.choice(["indicação", "manual", "outro"]),
            )
            s.add(cand)
            candidates.append(cand)
        await s.flush()

        # ~50 applications: candidatos distintos por job, espalhados por stage.
        created = 0
        for job in jobs:
            stages = (
                (
                    await s.execute(
                        select(Stage)
                        .where(
                            Stage.job_id == job.id,
                            Stage.kind == StageKind.ACTIVE,
                        )
                        .order_by(Stage.position)
                    )
                )
                .scalars()
                .all()
            )
            pool = rng.sample(candidates, 10)
            for cand in pool:
                if created >= 50:
                    break
                try:
                    app = await ApplicationService.create(
                        s,
                        tenant_id=tenant.id,
                        job_id=job.id,
                        candidate_id=cand.id,
                        actor_user_id=actor,
                    )
                except ApplicationDomainError:
                    continue
                # Espalha: avança até um stage aleatório.
                target = rng.choice(stages)
                if target.id != app.current_stage_id:
                    await ApplicationService.move_stage(
                        s,
                        app,
                        target_stage_id=target.id,
                        actor_user_id=actor,
                    )
                created += 1
        await s.commit()
        print(
            f"  {name}: 3 users, {len(jobs)} jobs, "
            f"{len(candidates)} candidatos, {created} applications."
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed de dados demo UpHiring")
    parser.add_argument(
        "--reset", action="store_true", help="Limpa dados demo antes de semear"
    )
    args = parser.parse_args()

    if args.reset:
        await reset_demo()
    elif await _already_seeded():
        print("Dados demo já existem. Use --reset para recriar.")
        return

    rng = random.Random(42)
    print("Semeando dados demo…")
    for clerk_org_id, slug, name in TENANTS:
        await seed_tenant(clerk_org_id, slug, name, rng)
    print("Seed concluído.")


if __name__ == "__main__":
    asyncio.run(main())
