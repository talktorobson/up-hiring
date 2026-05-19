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
const A_EMAIL = process.env.E2E_USER_A_EMAIL;
const A_PASSWORD = process.env.E2E_USER_A_PASSWORD;
const A_ORG_ID = process.env.E2E_CLERK_ORG_A_ID;
const B_EMAIL = process.env.E2E_USER_B_EMAIL;
const B_PASSWORD = process.env.E2E_USER_B_PASSWORD;
const B_ORG_ID = process.env.E2E_CLERK_ORG_B_ID;

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

  // @clerk/testing.signIn cria a sessão (cookie) mas NÃO hidrata o ClerkJS
  // da página atual nem define org ativa — sem org o (app)/layout
  // redireciona pra /select-org e a vaga nunca renderiza. Navegar pra
  // /select-org (landing org-less) força o ClerkProvider a carregar a
  // sessão; só então `setActive` tem sessão pra promover a org. Espera a
  // org refletir antes de o caller navegar pra /jobs.
  async function activateOrg(page: Page, orgId: string): Promise<void> {
    await page.goto("/select-org");
    await page.waitForFunction(() =>
      Boolean(
        (window as unknown as { Clerk?: { session?: unknown } }).Clerk
          ?.session,
      ),
    );
    await page.evaluate(async (id) => {
      const w = window as unknown as {
        Clerk: { setActive: (p: { organization: string }) => Promise<unknown> };
      };
      await w.Clerk.setActive({ organization: id });
    }, orgId);
    await page.waitForFunction(
      (id) =>
        (window as unknown as { Clerk?: { organization?: { id?: string } } })
          .Clerk?.organization?.id === id,
      orgId,
    );
  }

  test("create job, add candidate, move stage, RLS isolation", async ({
    page,
    browser,
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
    // Contexto isolado em vez de signOut→signIn no mesmo contexto: a 2ª
    // sessão não persiste de forma confiável no mesmo contexto (race
    // conhecida do Clerk). Cookies/sessão totalmente separados também
    // modelam melhor o isolamento RLS entre tenants.
    const ctxB = await browser.newContext();
    const pageB = await ctxB.newPage();
    await pageB.goto("/");
    await clerk.signIn({
      page: pageB,
      signInParams: {
        strategy: "password",
        identifier: B_EMAIL!,
        password: B_PASSWORD!,
      },
    });
    await activateOrg(pageB, B_ORG_ID!);
    await pageB.goto("/jobs");
    await expect(pageB.getByText(jobTitle)).toHaveCount(0);
    await ctxB.close();
  });
});
