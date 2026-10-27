import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const fixture = JSON.parse(
  readFileSync(process.env.ALOJAN_WEB_TEST_FIXTURE!, "utf8"),
);

test("no-answer and interrupted conditions persist, require exact review and exclude undisclosed transcript", async ({
  page,
}) => {
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
    const old = await (await fetch(`${base}/agents/${f.agent}`)).json();
    const target = await fetch(`${base}/http-connections`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        label: "Lifecycle preview",
        endpoint: "https://lifecycle.example.test/calls",
        auth_type: "none",
        token: null,
      }),
    });
    if (!target.ok) throw new Error("Synthetic target failed");
    const result = await fetch(`${base}/agents`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        ...old.content,
        agent_name: "Çağrı Koşulları",
        mcp_tools: [],
        outputs: [],
        post_call_actions: [],
      }),
    });
    if (!result.ok) throw new Error("Synthetic agent failed");
    return result.json();
  }, fixture.mcp);

  await page.goto(`/agentler/${created.id}`);
  await page.getByRole("tab", { name: "Çağrı sonrası", exact: true }).click();
  await page
    .getByRole("button", { name: "HTTP isteği ekle", exact: true })
    .click();
  const action = page.getByRole("region", {
    name: "HTTP işlemi 1",
    exact: true,
  });
  await action
    .getByLabel("HTTP hedef bağlantısı")
    .selectOption({ label: "Lifecycle preview" });
  const condition = action.getByLabel("Ne zaman gönderilsin?");
  const sharing = action.getByLabel("Konuşma dökümünü bu hedefle paylaş", {
    exact: true,
  });
  await condition.selectOption("no_answer");
  await expect(sharing).toBeDisabled();
  await expect(action).toContainText("Cevaplanmayan çağrıda özet hazırlanmaz");
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Taslak kaydedildi" }),
  ).toBeVisible();
  await page.reload();
  await page.getByRole("tab", { name: "Çağrı sonrası", exact: true }).click();
  await expect(condition).toHaveValue("no_answer");
  await page
    .getByRole("button", { name: "Gönderim iznini incele", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText(
    "Gönderim koşulu: Yalnızca cevaplanmayan çağrılar",
  );
  await dialog
    .getByRole("button", {
      name: "Bu hedeflere gönderime izin ver",
      exact: true,
    })
    .click();
  await expect(dialog).not.toBeVisible();
  await condition.selectOption("interrupted");
  await expect(sharing).toBeEnabled();
  await sharing.check();
  await expect(condition.locator('option[value="no_answer"]')).toBeDisabled();
  await sharing.uncheck();
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Taslak kaydedildi" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Gönderim iznini incele", exact: true })
    .click();
  await expect(dialog).toContainText(
    "Gönderim koşulu: Arayan kapattıysa veya görüşme kesildiyse",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
