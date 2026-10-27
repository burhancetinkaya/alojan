import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const fixture = JSON.parse(readFileSync(process.env.ALOJAN_WEB_TEST_FIXTURE!, "utf8"));

test("waiting preferences persist without publishing or exposing engine tuning", async ({ page }) => {
  await page.goto("/giris");
  await page.getByLabel("E-posta", { exact: true }).fill(fixture.mcp.login);
  await page.getByLabel("Şifre", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  await page.getByRole("link").filter({ hasText: "MCP JSON Asistanı" }).click();
  const enabled = page.getByLabel("Araç yanıtı uzadığında arayanı bilgilendir");
  await expect(enabled).not.toBeChecked();
  await enabled.check();
  await page.getByLabel("Bekleme ifadesi", { exact: true }).selectOption("natural");
  await page.getByLabel("Özel bekleme cümlesi (isteğe bağlı)", { exact: true }).fill("Kontrol ediyorum.");
  await page.getByRole("button", { name: "Taslağı kaydet", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Taslak kaydedildi" })).toBeVisible();
  await page.reload();
  await expect(enabled).toBeChecked();
  await expect(page.getByLabel("Bekleme ifadesi", { exact: true })).toHaveValue("natural");
  await expect(page.getByLabel("Özel bekleme cümlesi (isteğe bağlı)", { exact: true })).toHaveValue("Kontrol ediyorum.");
  await page.screenshot({ path: "/evidence/response-experience.png", fullPage: true });
  const saved = await page.evaluate(async (f) => (await fetch(`/v1/workspaces/${f.scope}/agents/${f.json_agent}`)).json(), fixture.mcp);
  expect(saved.content.response_experience).toEqual({ schema_version: 1, enabled: true, style: "natural", waiting_text: "Kontrol ediyorum." });
  await enabled.uncheck();
  await page.getByRole("button", { name: "Taslağı kaydet", exact: true }).click();
  await expect(page.getByRole("status").filter({ hasText: "Taslak kaydedildi" })).toBeVisible();
});
