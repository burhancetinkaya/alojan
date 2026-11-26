import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const fixture = JSON.parse(readFileSync(process.env.ALOJAN_WEB_TEST_FIXTURE!, "utf8"));

test("Pocket voice selection persists and EMA remains selectable", async ({ page }) => {
  await page.goto("/giris");
  await page.getByLabel("E-posta", { exact: true }).fill(fixture.mcp.login);
  await page.getByLabel("Şifre", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  await page.getByRole("link").filter({ hasText: "MCP JSON Asistanı" }).click();
  const voice = page.getByLabel("Ses", { exact: true });
  await expect(voice.locator("option")).toHaveCount(7);
  for (const selected of ["pocket-female_2", "pocket-male_3", "ema-default"]) {
    await voice.selectOption(selected);
    await page.getByRole("button", { name: "Taslağı kaydet", exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: "Taslak kaydedildi" })).toBeVisible();
    await page.reload();
    await expect(voice).toHaveValue(selected);
  }
});
