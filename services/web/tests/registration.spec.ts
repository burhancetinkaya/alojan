import { test, expect, type Page } from "@playwright/test";

async function fillAccount(page: Page, email: string) {
  await page.goto("/kayit");
  await page.getByLabel("Adın soyadın", { exact: true }).fill("Selin Yılmaz");
  await page.getByLabel("E-posta", { exact: true }).fill(email);
  await page
    .getByLabel("Şifre", { exact: true })
    .fill("Synthetic registration password 123!");
}
async function readWorkspace(page: Page) {
  return page.evaluate(async () => {
    const session = await (await fetch("/v1/auth/session")).json();
    const scope = session.workspaces[0].id;
    const agents = await (await fetch(`/v1/workspaces/${scope}/agents`)).json();
    const numbers = await (
      await fetch(`/v1/workspaces/${scope}/numbers`)
    ).json();
    return { session, scope, agents: agents.agents, numbers: numbers.numbers };
  });
}

test("registration persists an isolated draft and offers preparation without publishing", async ({
  page,
}) => {
  const errors: string[] = [];
  const writes: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => {
    if (r.method() !== "GET" && r.url().includes("/v1/"))
      writes.push(new URL(r.url()).pathname);
  });
  await fillAccount(page, "onboarding.owner@example.test");
  const password = page.getByLabel("Şifre", { exact: true });
  await expect(password).toHaveAttribute("minlength", "8");
  await password.fill("Seven7!");
  expect(
    await password.evaluate((el: HTMLInputElement) => el.validity.tooShort),
  ).toBe(true);
  await password.fill("Eight88!");
  expect(
    await password.evaluate((el: HTMLInputElement) => el.checkValidity()),
  ).toBe(true);

  await page.getByRole("button", { name: "Şifreyi göster" }).click();
  await expect(page.getByLabel("Şifre", { exact: true })).toHaveAttribute(
    "type",
    "text",
  );
  await page.getByRole("button", { name: "Şifreyi gizle" }).click();
  await expect(page.getByLabel("Şifre", { exact: true })).toHaveAttribute(
    "type",
    "password",
  );
  await page.screenshot({
    path: "/evidence/registration-account.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Hesap oluştur", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Ona bir isim ver." }),
  ).toBeVisible();
  expect((await readWorkspace(page)).agents).toEqual([]);
  await expect(page.getByLabel("Kimin asistanı?")).toHaveValue("Selin Yılmaz");
  await page.getByLabel("Agentının adı").fill("Deniz");
  await page.getByLabel("Kimin asistanı?").fill("Ece Kaya");
  await page
    .getByLabel("Arayanlara nasıl yardımcı olsun?")
    .fill("Arayanın mesajını not al. Kısa ve nazik konuş.");
  await expect(page.locator(".registration-preview")).toContainText(
    "Ece Kaya adlı kişinin yapay zekâ asistanıyım",
  );
  await page.screenshot({
    path: "/evidence/registration-agent.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Agent taslağımı oluştur" }).click();
  await expect(
    page.getByRole("heading", { name: "Deniz ile başlayalım." }),
  ).toBeVisible();
  await expect(
    page.getByText("Taslak · Henüz çağrı karşılamıyor"),
  ).toBeVisible();
  const state = await readWorkspace(page);
  expect(state.agents).toHaveLength(1);
  expect(state.numbers).toEqual([]);
  const saved = await page.evaluate(
    async ({ scope, id }) => ({
      draft: await (await fetch(`/v1/workspaces/${scope}/agents/${id}`)).json(),
      releases: await (
        await fetch(`/v1/workspaces/${scope}/agents/${id}/releases`)
      ).json(),
    }),
    { scope: state.scope, id: state.agents[0].id },
  );
  expect(saved.draft.content).toMatchObject({
    agent_name: "Deniz",
    owner_display_name: "Ece Kaya",
    instructions: "Arayanın mesajını not al. Kısa ve nazik konuş.",
  });
  expect(saved.draft.content.post_call_actions ?? []).toEqual([]);
  expect(saved.releases.current_release).toBeNull();
  expect(saved.releases.releases).toEqual([]);
  expect(writes).toEqual([
    "/v1/auth/register",
    `/v1/workspaces/${state.scope}/agents`,
  ]);
  await page.screenshot({
    path: "/evidence/registration-next.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Agentımı düzenle" }).click();
  await expect(page.getByLabel("Görevi", { exact: true })).toHaveValue(
    saved.draft.content.instructions,
  );
  await page.goto("/baslangic");
  await expect(page).toHaveURL(/\/agentler$/);
  expect((await readWorkspace(page)).agents).toHaveLength(1);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
  expect(errors).toEqual([]);
});

test("mobile skip creates no agent, supports resuming and handles validation errors", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await fillAccount(page, "onboarding.skip@example.test");
  await page.screenshot({
    path: "/evidence/registration-account-mobile.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Hesap oluştur", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Ona bir isim ver." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Şimdilik atla" }).click();
  await expect(
    page.getByRole("heading", { name: "İstediğinde başlayalım." }),
  ).toBeVisible();
  expect((await readWorkspace(page)).agents).toEqual([]);
  await page.getByRole("button", { name: "İlk agentımı oluştur" }).click();
  await page.getByLabel("Agentının adı").fill("   ");
  await page.getByRole("button", { name: "Agent taslağımı oluştur" }).click();
  await expect(page.locator(".notice.error")).toContainText(
    "Agent ayarları geçerli değil",
  );
  await expect(page.getByLabel("Kimin asistanı?")).toHaveValue("Selin Yılmaz");
  await page.getByLabel("Agentının adı").fill("Deniz");
  await page.screenshot({
    path: "/evidence/registration-agent-mobile.png",
    fullPage: true,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Agent taslağımı oluştur" }).click();
  await expect(
    page.getByRole("heading", { name: "Deniz ile başlayalım." }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/evidence/registration-next-mobile.png",
    fullPage: true,
  });
  await page.reload();
  await expect(page).toHaveURL(/\/agentler$/);
  expect((await readWorkspace(page)).agents).toHaveLength(1);
});

test("lost create response cannot be retried blindly and saved draft survives", async ({
  page,
}) => {
  await fillAccount(page, "onboarding.uncertain@example.test");
  // Keep the real session cookie but simulate a truncated registration body.
  let registrations = 0;
  await page.route("**/v1/auth/register", async (route) => {
    registrations++;
    const response = await route.fetch();
    expect(response.status()).toBe(201);
    await route.fulfill({ response, body: "{" });
  });
  await page
    .getByRole("button", { name: "Hesap oluştur", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Ona bir isim ver." }),
  ).toBeVisible();
  let creates = 0;
  await page.route("**/v1/workspaces/*/agents", async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    creates++;
    const response = await route.fetch();
    expect(response.status()).toBe(201);
    await route.abort("failed");
  });
  await page.getByLabel("Agentının adı").fill("Deniz");
  await page.getByRole("button", { name: "Agent taslağımı oluştur" }).click();
  await expect(page.locator(".notice.error")).toContainText(
    "Taslağın kaydedilmiş olabilir",
  );
  await expect(
    page.getByRole("button", { name: "Agent taslağımı oluştur" }),
  ).toBeDisabled();
  await page.getByRole("link", { name: "Çalışma alanına git" }).click();
  await expect(
    page.getByRole("link").filter({ hasText: "Deniz" }),
  ).toBeVisible();
  expect((await readWorkspace(page)).agents).toHaveLength(1);
  expect(creates).toBe(1);
  expect(registrations).toBe(1);
});

test("uncertain registration clears password and directs to login without resubmitting", async ({
  page,
}) => {
  await fillAccount(page, "onboarding.noresponse@example.test");
  let requests = 0;
  await page.route("**/v1/auth/register", (route) => {
    requests++;
    return route.abort("failed");
  });
  await page
    .getByRole("button", { name: "Hesap oluştur", exact: true })
    .click();
  await expect(page.locator(".notice.error")).toContainText(
    "Tekrar kayıt olmadan önce giriş yapmayı dene",
  );
  await expect(page.getByLabel("Şifre", { exact: true })).toHaveValue("");
  await expect(
    page.getByRole("button", { name: "Hesap oluştur", exact: true }),
  ).toBeDisabled();
  expect(requests).toBe(1);
  await page.getByRole("link", { name: "Giriş yap", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Tekrar hoş geldin" }),
  ).toBeVisible();
});
