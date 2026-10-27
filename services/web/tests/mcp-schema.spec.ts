import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const fixture = JSON.parse(
  readFileSync(process.env.ALOJAN_WEB_TEST_FIXTURE!, "utf8"),
);

test("qualified remote schemas preserve omitted, null and fixed values through the real API", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/giris");
  await page.getByLabel("E-posta", { exact: true }).fill(fixture.mcp.login);
  await page.getByLabel("Şifre", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  await page.getByRole("link").filter({ hasText: "MCP Şema Asistanı" }).click();
  await page.getByRole("tab", { name: "Araçlar", exact: true }).click();
  await page
    .getByLabel("MCP bağlantısı", { exact: true })
    .selectOption(fixture.mcp.connection);
  await page
    .getByLabel("MCP aracı", { exact: true })
    .selectOption(fixture.mcp.qualified_review);
  await page
    .getByRole("button", { name: "MCP aracı ekle", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("query değerini sabitle").check();
  await expect(dialog.getByLabel("query · Boş değer gönder")).toBeChecked();
  await dialog.getByLabel("query · Boş değer gönder").uncheck();
  await dialog.getByLabel("query", { exact: true }).fill("synthetic");
  await expect(dialog.getByLabel("query", { exact: true })).toHaveAttribute(
    "maxlength",
    "4096",
  );
  await dialog.getByLabel("query · Boş değer gönder").check();
  await dialog.getByLabel("limit değerini sabitle").check();
  await dialog.getByLabel("limit", { exact: true }).fill("1");
  await dialog.getByRole("button", { name: "Araç ayarlarını uygula" }).click();
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Taslak kaydedildi" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Araç iznini incele" }).click();
  await expect(
    dialog.getByText("Konuşmadan alınabilecek alanlar: offset", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    dialog.getByText(/Metinler en fazla 4096 karakter/),
  ).toBeVisible();
  await expect(dialog.locator("dd")).toHaveText(["1", "null"]);
  await dialog.getByRole("button", { name: "Bu araçlara izin ver" }).click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Seçili araçlara izin verildi" }),
  ).toBeVisible();
  const review = await page.evaluate(
    async (f) =>
      (
        await fetch(
          `/v1/workspaces/${f.scope}/agents/${f.qualified_agent}/mcp-review`,
        )
      ).json(),
    fixture.mcp,
  );
  expect(review.review.schema_version).toBe(2);
  expect(review.review.tools[0].fixed_arguments).toEqual({
    query: null,
    limit: 1,
  });
  expect(review.review.tools[0].schema_policy).toBe("bounded.v1");
  expect(
    review.review.tools[0].tool.inputSchema.properties.query.anyOf,
  ).toHaveLength(2);
  await page
    .getByRole("button", { name: "Aracı düzenle", exact: true })
    .click();
  await expect(dialog.getByLabel("query · Boş değer gönder")).toBeChecked();
  await dialog.getByLabel("query değerini sabitle").uncheck();
  await dialog.getByRole("button", { name: "Araç ayarlarını uygula" }).click();
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Taslak kaydedildi" }),
  ).toBeVisible();
  const next = await page.evaluate(
    async (f) =>
      (
        await fetch(
          `/v1/workspaces/${f.scope}/agents/${f.qualified_agent}/mcp-review`,
        )
      ).json(),
    fixture.mcp,
  );
  expect(next.review.tools[0].fixed_arguments).toEqual({ limit: 1 });
  expect(next.review_digest).not.toBe(review.review_digest);
  expect(errors).toEqual([]);
});

test("schema-less JSON tools can be saved and consented without invented output fields", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/giris");
  await page.getByLabel("E-posta", { exact: true }).fill(fixture.mcp.login);
  await page.getByLabel("Şifre", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  await page.getByRole("link").filter({ hasText: "MCP JSON Asistanı" }).click();
  await page.getByRole("tab", { name: "Araçlar", exact: true }).click();
  await page.getByLabel("MCP bağlantısı", { exact: true }).selectOption(fixture.mcp.connection);
  await page.getByLabel("MCP aracı", { exact: true }).selectOption(fixture.mcp.json_review);
  await page.getByRole("button", { name: "MCP aracı ekle", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("pageSize değerini sabitle").check();
  await dialog.getByLabel("pageSize", { exact: true }).fill("1");
  await dialog.getByRole("button", { name: "Araç ayarlarını uygula" }).click();
  await page.getByRole("button", { name: "Taslağı kaydet", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Taslak kaydedildi" })).toBeVisible();
  await page.getByRole("button", { name: "Araç iznini incele" }).click();
  await expect(dialog.getByText(/Sunucu çıktı alanlarını tanımlamıyor/)).toBeVisible();
  await dialog.getByRole("button", { name: "Bu araçlara izin ver" }).click();
  await expect(page.getByRole("status").filter({ hasText: "Seçili araçlara izin verildi" })).toBeVisible();
  const review = await page.evaluate(async (f) => (await fetch(`/v1/workspaces/${f.scope}/agents/${f.json_agent}/mcp-review`)).json(), fixture.mcp);
  expect(review.review.schema_version).toBe(3);
  expect(review.review.tools[0].output_schema).toBeNull();
  expect(review.review.tools[0].schema_policy).toBe("bounded.v2");
  expect(review.review.tools[0].fixed_arguments).toEqual({ pageSize: 1 });
  expect(errors).toEqual([]);
});
