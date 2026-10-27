import { test, expect, request } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";

test("personal MCP token lifecycle and same-user credential handoff", async ({
  page,
  baseURL,
}) => {
  const fixture = process.env.ALOJAN_WEB_TEST_FIXTURE
    ? JSON.parse(readFileSync(process.env.ALOJAN_WEB_TEST_FIXTURE, "utf8"))
    : null;
  // Share the full-suite fixture without consuming the registration abuse budget.
  const password = fixture?.password || "Synthetic MCP browser password 123!";
  const registered = await page.request.post(
    fixture ? "/v1/auth/login" : "/v1/auth/register",
    {
      headers: { Origin: baseURL! },
      data: {
        login:
          fixture?.token_login ||
          `mcp.${randomUUID().slice(0, 8)}@example.test`,
        password,
        ...(fixture ? {} : { display_name: "MCP Browser Owner" }),
      },
    },
  );
  expect(registered.status()).toBe(fixture ? 200 : 201);
  const session = await registered.json();
  const scope = session.workspaces[0].id;
  await page.goto("/mcp-erisim");
  await expect(
    page.getByRole("heading", { name: "MCP erişimi" }),
  ).toBeVisible();
  await page
    .getByLabel("Token adı", { exact: true })
    .fill("Synthetic Codex access");
  await page
    .getByLabel("Bağlantıları yönet ve araçları tara", { exact: true })
    .check();
  await expect(page.getByLabel("İstemci bağlantı ayarı")).toContainText(
    'bearer_token_env_var = "ALOJAN_MCP_TOKEN"',
  );
  await page.getByLabel("Bağlanacağın uygulama").selectOption("claude-code");
  const codeConfig = JSON.parse(
    (await page.getByLabel("İstemci bağlantı ayarı").textContent())!,
  );
  expect(codeConfig.mcpServers.alojan.headers.Authorization).toBe(
    "Bearer ${ALOJAN_MCP_TOKEN}",
  );
  await page
    .getByLabel("Mevcut şifren", { exact: true })
    .fill("Wrong synthetic password");
  await page
    .getByRole("button", { name: "Token oluştur", exact: true })
    .click();
  await expect(page.getByText("E-posta veya şifre doğru değil.")).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "MCP erişimi" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Token listesini kontrol et" }),
  ).toHaveCount(0);
  await expect(page.getByLabel("Mevcut şifren", { exact: true })).toHaveValue(
    "",
  );
  await page.getByLabel("Mevcut şifren", { exact: true }).fill(password);
  await page
    .getByRole("button", { name: "Token oluştur", exact: true })
    .click();
  const secret = await page
    .getByLabel("Yeni token — bir kez gösterilir")
    .inputValue();
  expect(secret).toMatch(/^alojan_pat_/);
  expect(
    await page.getByLabel("Mevcut şifren", { exact: true }).inputValue(),
  ).toBe("");
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
  const machine = await request.newContext({
    baseURL,
    ignoreHTTPSErrors: true,
    extraHTTPHeaders: { Authorization: `Bearer ${secret}` },
  });
  try {
    expect((await machine.get("/v1/mcp/context")).status()).toBe(200);
    expect(
      (
        await machine.post(`/v1/workspaces/${scope}/agents`, {
          data: {},
          headers: { "Idempotency-Key": randomUUID() },
        })
      ).status(),
    ).toBe(403);
    const started = await machine.post(
      `/v1/workspaces/${scope}/connection-setups`,
      {
        headers: { "Idempotency-Key": randomUUID() },
        data: {
          kind: "http",
          configuration: {
            label: "Synthetic protected hook",
            endpoint: "https://hooks.example.test/calls",
            auth_type: "bearer",
          },
        },
      },
    );
    expect(started.status()).toBe(201);
    const setup = await started.json();
    await page.goto(setup.setup_url);
    await expect(
      page.getByRole("heading", { name: "Bağlantıyı tamamla" }),
    ).toBeVisible();
    await page
      .getByLabel("Erişim anahtarı", { exact: true })
      .fill("synthetic-never-sent-provider-credential");
    await page
      .getByRole("button", { name: "Bağlantıyı oluştur", exact: true })
      .click();
    await expect(page.getByText(/Bağlantı hazır/)).toBeVisible();
    const status = await machine.get(
      `/v1/workspaces/${scope}/connection-setups/${setup.id}`,
    );
    expect((await status.json()).status).toBe("complete");
    expect(await status.text()).not.toContain(
      "synthetic-never-sent-provider-credential",
    );
    await page.goto("/mcp-erisim");
    await expect(
      page.getByLabel("Yeni token — bir kez gösterilir"),
    ).toHaveCount(0);
    page.once("dialog", (dialog) => dialog.accept());
    await page
      .getByRole("button", { name: "Erişimi iptal et", exact: true })
      .click();
    await expect(
      page.getByRole("button", { name: "İptal edildi", exact: true }),
    ).toBeDisabled();
    expect((await machine.get("/v1/mcp/context")).status()).toBe(401);
  } finally {
    await machine.dispose();
  }
});
