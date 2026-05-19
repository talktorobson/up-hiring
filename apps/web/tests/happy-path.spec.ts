import { clerk, clerkSetup } from "@clerk/testing/playwright";
import { expect, test, type Page } from "@playwright/test";

/**
 * Sprint 4 #89 — único happy path:
 * login A → cria vaga → adiciona candidato → arrasta stage → refresh
 * persiste → login B (outra org) → não vê a vaga (RLS).
 *
 * Requer Clerk test users + org (setup externo — ver RUNBOOK). Sem os envs
 * o teste é SKIPPED em vez de falhar, pra não travar o merge enquanto os
 * secrets não estão provisionados.
 */
// .trim() defensivo: secret colado no GitHub frequentemente carrega \n ou
// espaço → Clerk rejeita com "Identifier is invalid".
const env = (k: string): string | undefined => process.env[k]?.trim();
const A_EMAIL = env("E2E_USER_A_EMAIL");
const A_PASSWORD = env("E2E_USER_A_PASSWORD");
const A_ORG_ID = env("E2E_CLERK_ORG_A_ID");
const B_EMAIL = env("E2E_USER_B_EMAIL");
const B_PASSWORD = env("E2E_USER_B_PASSWORD");
const B_ORG_ID = env("E2E_CLERK_ORG_B_ID");

const haveCreds =
  !!A_EMAIL &&
  !!A_PASSWORD &&
  !!A_ORG_ID &&
  !!B_EMAIL &&
  !!B_PASSWORD &&
  !!B_ORG_ID &&
  !!process.env.CLERK_SECRET_KEY;

test.describe("UpHiring happy path", () => {
  test.skip(
    !haveCreds,
    "Clerk E2E credenciais ausentes (E2E_USER_*/CLERK_SECRET_KEY) — ver RUNBOOK",
  );

  test.beforeAll(async () => {
    await clerkSetup();
  });

  // dnd-kit (PointerSensor distance 6) precisa de mousemoves intermediários;
  // dragTo simples não dispara o drag. Helper com passos manuais.
  async function dragCard(page: Page, cardName: string, toColumn: string) {
    const card = page.getByRole("button", { name: new RegExp(cardName) });
    const target = page.getByText(toColumn, { exact: true });
    const cb = await card.boundingBox();
    const tb = await target.boundingBox();
    if (!cb || !tb) throw new Error("card/coluna sem bounding box");
    await page.mouse.move(cb.x + cb.width / 2, cb.y + cb.height / 2);
    await page.mouse.down();
    await page.mouse.move(cb.x + cb.width / 2, cb.y - 30, { steps: 8 });
    await page.mouse.move(tb.x + tb.width / 2, tb.y + 40, { steps: 12 });
    await page.mouse.up();
  }

  // @clerk/testing.signIn cria a sessão via client API, mas o getter
  // Clerk.session pode não estar "ativo" ainda → setActive sem `session`
  // dá "no active session", e depender de navegação pra hidratar é flaky
  // (handshake da instância dev). Passa session+organization explícitos a
  // partir de Clerk.client (disponível logo após o signIn, sem navegar) e
  // espera a org refletir antes de o caller ir pra /jobs.
  type ClerkWin = {
    Clerk?: {
      loaded?: boolean;
      session?: { id?: string } | null;
      organization?: { id?: string } | null;
      user?: {
        id?: string;
        primaryEmailAddress?: { emailAddress?: string } | null;
        organizationMemberships?: Array<{ organization: { id: string } }>;
      } | null;
      client?: {
        lastActiveSessionId?: string | null;
        sessions?: Array<{ id: string }>;
        signIn?: {
          create: (p: {
            strategy: string;
            identifier: string;
            password: string;
          }) => Promise<{
            status?: string;
            createdSessionId?: string;
            supportedFirstFactors?: Array<{ strategy?: string }> | null;
          }>;
        };
      };
      setActive?: (p: {
        session?: string;
        organization?: string;
      }) => Promise<unknown>;
    };
  };

  // signIn de User B via API crua (não @clerk/testing, que engole o
  // status). Captura status/createdSessionId/firstFactors/erro e — como o
  // reporter github suprime stdout — devolve tudo pra ser jogado na
  // mensagem de erro (único canal visível em CI). Faz o setActive aqui.
  async function rawSignIn(
    p: Page,
    identifier: string,
    password: string,
  ): Promise<void> {
    const r = await p.evaluate(
      async ({ identifier, password }) => {
        const c = (window as unknown as ClerkWin).Clerk;
        try {
          const res = await c!.client!.signIn!.create({
            strategy: "password",
            identifier,
            password,
          });
          if (res.status === "complete" && res.createdSessionId) {
            await c!.setActive!({ session: res.createdSessionId });
          }
          return {
            status: res.status ?? null,
            createdSessionId: res.createdSessionId ?? null,
            firstFactors:
              res.supportedFirstFactors?.map((f) => f.strategy) ?? null,
            err: null as string | null,
          };
        } catch (e) {
          return {
            status: null,
            createdSessionId: null,
            firstFactors: null,
            err: e instanceof Error ? e.message : String(e),
          };
        }
      },
      { identifier, password },
    );
    if (r.status !== "complete" || !r.createdSessionId) {
      throw new Error(`rawSignIn falhou: ${JSON.stringify(r)}`);
    }
  }

  // Snapshot do estado do ClerkJS — anexado às falhas pra diagnosticar
  // sessão/org/memberships sem adivinhação. Standalone (sem closure Node)
  // pra rodar dentro de page.evaluate.
  function clerkSnapshot(): string {
    const c = (window as unknown as ClerkWin).Clerk;
    return JSON.stringify({
      loaded: c?.loaded ?? null,
      userId: c?.user?.id ?? null,
      email: c?.user?.primaryEmailAddress?.emailAddress ?? null,
      sessionId: c?.session?.id ?? null,
      clientSessions: c?.client?.sessions?.length ?? null,
      lastActiveSessionId: c?.client?.lastActiveSessionId ?? null,
      activeOrg: c?.organization?.id ?? null,
      memberships:
        c?.user?.organizationMemberships?.map((m) => m.organization.id) ??
        null,
    });
  }

  // Espera o ClerkJS terminar load/handshake (instância dev) antes do
  // signIn — num contexto frio o signIn pode rodar com o client ainda
  // não pronto e o setActive interno vira no-op (sem sessão).
  async function waitClerkReady(p: Page): Promise<void> {
    await p.waitForFunction(
      () => (window as unknown as ClerkWin).Clerk?.loaded === true,
      undefined,
      { timeout: 30_000 },
    );
  }

  async function activateOrg(page: Page, orgId: string): Promise<void> {
    try {
      await page.waitForFunction(
        () => {
          const c = (window as unknown as ClerkWin).Clerk;
          return Boolean(
            c?.session?.id ||
              c?.client?.lastActiveSessionId ||
              c?.client?.sessions?.length,
          );
        },
        undefined,
        { timeout: 30_000 },
      );
    } catch {
      const snap = await page.evaluate(clerkSnapshot);
      throw new Error(
        `activateOrg(${orgId}): sessão Clerk não estabelecida. Clerk=${snap}`,
      );
    }
    await page.evaluate(async (id) => {
      const c = (window as unknown as ClerkWin).Clerk!;
      const sid =
        c.session?.id ??
        c.client?.lastActiveSessionId ??
        c.client?.sessions?.[0]?.id;
      await c.setActive!({ session: sid, organization: id });
    }, orgId);
    try {
      await page.waitForFunction(
        (id) =>
          (window as unknown as ClerkWin).Clerk?.organization?.id === id,
        orgId,
        { timeout: 20_000 },
      );
    } catch {
      const snap = await page.evaluate(clerkSnapshot);
      throw new Error(
        `activateOrg(${orgId}): org não ficou ativa. Clerk=${snap}`,
      );
    }
  }

  test("create job, add candidate, move stage, RLS isolation", async ({
    page,
  }) => {
    const jobTitle = `Pessoa Vendedora Loja ${Date.now()}`;

    // --- User A ---
    await page.goto("/");
    await clerk.signIn({
      page,
      signInParams: {
        strategy: "password",
        identifier: A_EMAIL!,
        password: A_PASSWORD!,
      },
    });
    await activateOrg(page, A_ORG_ID!);

    await page.goto("/jobs");
    await page.getByRole("link", { name: "Nova vaga" }).click();
    await page.getByLabel("Título *").fill(jobTitle);
    await page.getByLabel("Localização").fill("São Paulo, SP");
    await page.getByLabel("Salário mínimo (R$)").fill("2500");
    await page.getByLabel("Salário máximo (R$)").fill("3500");
    await page.getByRole("button", { name: "Criar vaga" }).click();

    await expect(
      page.getByRole("heading", { name: jobTitle }),
    ).toBeVisible();

    // Adiciona candidato novo
    await page.getByRole("button", { name: "Adicionar candidato" }).click();
    await page
      .getByRole("button", { name: "Criar novo candidato" })
      .click();
    const stamp = Date.now();
    await page.getByLabel("Nome completo *").fill("Joana Silva");
    await page
      .getByLabel("E-mail *")
      .fill(`joana${stamp}@test.com`);
    await page.getByLabel("CPF").fill("390.533.447-05");
    await page.getByRole("button", { name: "Criar candidato" }).click();

    // Card cai na 1ª stage active (Sourced)
    await page.getByRole("tab", { name: "Pipeline" }).click();
    await expect(page.getByText("Joana Silva")).toBeVisible();

    await dragCard(page, "Joana Silva", "Screening");
    await page.reload();
    await page.getByRole("tab", { name: "Pipeline" }).click();
    await expect(page.getByText("Joana Silva")).toBeVisible();

    // --- User B (outra org) não enxerga a vaga ---
    // MESMO contexto (default page): um browser.newContext() numa instância
    // Clerk *dev* nunca bootstrapa o dev-browser/handshake, então setActive
    // não persiste a 2ª sessão lá. O contexto default já tem o dev-browser
    // funcionando (fluxo do User A passa). signOut A, rawSignIn B aqui.
    await clerk.signOut({ page });
    await page.goto("/");
    await waitClerkReady(page);
    await rawSignIn(page, B_EMAIL!, B_PASSWORD!);
    await activateOrg(page, B_ORG_ID!);
    await page.goto("/jobs");
    await expect(page.getByText(jobTitle)).toHaveCount(0);
  });
});
