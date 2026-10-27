import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const fixture = JSON.parse(
  readFileSync(process.env.ALOJAN_WEB_TEST_FIXTURE!, "utf8"),
);

test("owner declares conversation and reviewed tool fields, maps and grants exact output definitions", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/giris");
  await page.getByLabel("E-posta", { exact: true }).fill(fixture.mcp.login);
  await page.getByLabel("Şifre", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Agentlerin", exact: true }),
  ).toBeVisible();
  const created = await page.evaluate(async (f) => {
    const session = await (await fetch("/v1/auth/session")).json();
    const base = `/v1/workspaces/${f.scope}`;
    const headers = {
      "Content-Type": "application/json",
      "X-CSRF-Token": session.csrf_token,
    };
    const existing = await (await fetch(`${base}/agents/${f.agent}`)).json();
    const target = await fetch(`${base}/http-connections`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        label: "Output preview",
        endpoint: "https://outputs.example.test/calls",
        auth_type: "none",
        token: null,
      }),
    });
    if (!target.ok) throw new Error("Synthetic connection setup failed");
    const result = await fetch(`${base}/agents`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        ...existing.content,
        agent_name: "Özel Alan Asistanı",
        outputs: [],
        post_call_actions: [],
        mcp_tools: [
          {
            connection_id: f.connection,
            review_id: f.review,
            alias: "mcp_search",
            fixed_arguments: { project: 7 },
          },
        ],
      }),
    });
    if (!result.ok) throw new Error("Synthetic draft setup failed");
    return result.json();
  }, fixture.mcp);
  await page.goto(`/agentler/${created.id}`);
  await page.getByRole("tab", { name: "Çağrı sonrası", exact: true }).click();
  const outputs = page.getByRole("region", {
    name: "Özel sonuç alanları",
    exact: true,
  });
  await outputs
    .getByRole("button", { name: "Özel alan ekle", exact: true })
    .click();
  const first = outputs.getByRole("region", {
    name: "Özel alan 1",
    exact: true,
  });
  await first.getByLabel("Alan adı", { exact: true }).fill("products");
  await first
    .getByLabel("Alan türü", { exact: true })
    .selectOption("string_array");
  await first
    .getByLabel("Hangi bilgi alınsın?", { exact: true })
    .fill("Arayanın açıkça belirttiği ürün adları");
  await outputs
    .getByRole("button", { name: "Özel alan ekle", exact: true })
    .click();
  const second = outputs.getByRole("region", {
    name: "Özel alan 2",
    exact: true,
  });
  await second.getByLabel("Alan adı", { exact: true }).fill("lookup");
  await second
    .getByLabel("Hangi bilgi alınsın?", { exact: true })
    .fill("Onaylı arama aracının sonuç alanı");
  await second
    .getByLabel("Bilgi kaynağı", { exact: true })
    .selectOption("tool");
  await second
    .getByLabel("Sonucu alınacak araç", { exact: true })
    .selectOption("mcp_search");
  await expect(
    second.getByLabel("Araç sonuç alanı", { exact: true }).locator("option"),
  ).toHaveCount(2);
  await second
    .getByLabel("Araç sonuç alanı", { exact: true })
    .selectOption("answer");
  await page
    .getByRole("button", { name: "HTTP isteği ekle", exact: true })
    .click();
  const action = page.getByRole("region", {
    name: "HTTP işlemi 1",
    exact: true,
  });
  await action
    .getByLabel("HTTP hedef bağlantısı")
    .selectOption({ label: "Output preview" });
  for (const [name, source] of [
    ["products", "outputs.products"],
    ["lookup", "outputs.lookup"],
  ]) {
    await action
      .getByRole("button", { name: "Gövde alanı ekle", exact: true })
      .click();
    const row = action.locator('[aria-label^="Gövde alanı"]').last();
    await row.getByLabel("Hedef alan adı", { exact: true }).fill(name);
    await row.getByLabel("Değer kaynağı", { exact: true }).selectOption(source);
  }
  await expect(action.locator('[aria-label^="Gövde alanı"]')).toHaveCount(5);
  await expect(first.getByLabel("Alan adı", { exact: true })).toBeDisabled();
  await expect(
    first.getByRole("button", { name: "Özel alanı kaldır", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Taslak kaydedildi" }),
  ).toBeVisible();
  await page.reload();
  await page.getByRole("tab", { name: "Çağrı sonrası", exact: true }).click();
  await expect(
    page.getByLabel("Alan adı", { exact: true }).first(),
  ).toHaveValue("products");
  await page
    .getByRole("button", { name: "Gönderim iznini incele", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.locator("pre").first()).toContainText(
    "Arayanın açıkça belirttiği ürün adları",
  );
  await expect(dialog.locator("pre").first()).toContainText("mcp_search");
  await dialog
    .getByText("Örnek istek · gerçek çağrı verisi içermez", { exact: true })
    .click();
  await expect(dialog.locator("pre").last()).toContainText('"products": [');
  await dialog
    .getByRole("button", {
      name: "Bu hedeflere gönderime izin ver",
      exact: true,
    })
    .click();
  await expect(dialog).not.toBeVisible();
  await page.screenshot({
    path: "/evidence/declared-outputs-editor.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(errors).toEqual([]);
});

test("call detail displays typed outputs and missing states as escaped data", async ({
  page,
}) => {
  await page.goto("/giris");
  await page.getByLabel("E-posta", { exact: true }).fill(fixture.call_login);
  await page.getByLabel("Şifre", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Agentlerin", exact: true }),
  ).toBeVisible();
  await page.route(
    /\/v1\/workspaces\/[^/]+\/calls\/[0-9a-f-]+$/,
    async (route) => {
      const response = await route.fetch();
      await route.fulfill({
        response,
        json: {
          ...(await response.json()),
          outputs: {
            product: "<script>window.outputLeak=true</script>",
            quantity: 2.5,
            tags: ["a", "b"],
            unknown: null,
          },
          output_status: {
            product: "done",
            quantity: "done",
            tags: "done",
            unknown: "missing",
          },
        },
      });
    },
  );
  await page.getByRole("link", { name: "Aramalar", exact: true }).click();
  await page.getByRole("link").filter({ hasText: "Çağrı Asistanı" }).click();
  const fields = page.getByRole("region", {
    name: "Görüşmenin özel alanları",
    exact: true,
  });
  await expect(
    fields.getByText("<script>window.outputLeak=true</script>", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(fields.getByText('["a","b"]', { exact: true })).toBeVisible();
  await expect(
    fields.getByText("Bilgi bulunamadı", { exact: true }),
  ).toBeVisible();
  await expect(fields.locator("script")).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
