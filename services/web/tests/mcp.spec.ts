import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const fixture = JSON.parse(
  readFileSync(process.env.ALOJAN_WEB_TEST_FIXTURE!, "utf8"),
);

test("MCP selection, fixed parameters and historical consent use the real scoped API", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/giris");
  await page.getByLabel("E-posta", { exact: true }).fill(fixture.mcp.login);
  await page.getByLabel("Şifre", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  await page.getByRole("link").filter({ hasText: "MCP Asistanı" }).click();
  await page.getByRole("tab", { name: "Araçlar", exact: true }).click();
  await page
    .getByLabel("MCP bağlantısı", { exact: true })
    .selectOption(fixture.mcp.connection);
  await expect(
    page.getByRole("option", { name: "unreviewed · İnceleme bekliyor" }),
  ).toBeDisabled();
  await page
    .getByLabel("MCP aracı", { exact: true })
    .selectOption(fixture.mcp.review);
  await page
    .getByRole("button", { name: "MCP aracı ekle", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog
    .getByLabel("Talimatlarda kullanılacak araç adı")
    .fill("mcp_status");
  await dialog
    .getByLabel("Bu araç ne zaman kullanılmalı?")
    .fill("Ürün durumu sorulduğunda kullan.");
  await dialog.getByLabel("project değerini sabitle").check();
  await dialog.getByLabel("project", { exact: true }).fill("7");
  await dialog.getByRole("button", { name: "Araç ayarlarını uygula" }).click();
  await expect(
    page.getByRole("button", { name: "Araç iznini incele" }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Taslak kaydedildi" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Araç iznini incele" }).click();
  await expect(
    dialog.getByText(new URL('/tools', new URL("https:" + "//" + 'mcp.example.test')).href, { exact: true }),
  ).toBeVisible();
  await expect(
    dialog.getByText("Konuşmadan alınabilecek alanlar: query", { exact: true }),
  ).toBeVisible();
  await expect(dialog.locator("dd")).toHaveText("7");
  await dialog.getByRole("button", { name: "Bu araçlara izin ver" }).click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Seçili araçlara izin verildi" }),
  ).toBeVisible();
  // Removing a draft selection must not hide the previously issued release permission.
  await page.getByRole("button", { name: "Aracı kaldır", exact: true }).click();
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Taslak kaydedildi" }),
  ).toBeVisible();
  await page.getByText("Verilmiş izinler (1)", { exact: true }).click();
  await page.getByRole("button", { name: /İzni kaldır ·/ }).click();
  await dialog.getByRole("button", { name: "Bu araç iznini kaldır" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Araç izni kaldırıldı" }),
  ).toBeVisible();
  const grants = await page.evaluate(
    async (f) =>
      (
        await fetch(`/v1/workspaces/${f.scope}/agents/${f.agent}/mcp-grants`)
      ).json(),
    fixture.mcp,
  );
  expect(grants.grants).toHaveLength(1);
  expect(grants.grants[0].enabled).toBe(false);
  expect(errors).toEqual([]);
});
