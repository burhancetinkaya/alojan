import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const fixture = JSON.parse(
  readFileSync(process.env.ALOJAN_WEB_TEST_FIXTURE!, "utf8"),
);

test("HTTP connection, typed mapping, exact grant and revocation use real scoped APIs without sends", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const external: string[] = [];
  page.on("request", (r) => {
    if (new URL(r.url()).hostname === "hooks.example.test")
      external.push(r.url());
  });
  await page.goto("/giris");
  await page.getByLabel("E-posta", { exact: true }).fill(fixture.mcp.login);
  await page.getByLabel("Şifre", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Agentlerin", exact: true }),
  ).toBeVisible();
  await page.goto("/baglantilar");
  const connections = page.getByRole("region", { name: "HTTP bağlantıları" });
  await connections.getByLabel("HTTP bağlantı adı").fill("Synthetic CRM");
  await connections
    .getByLabel("HTTPS hedef adresi")
    .fill("https://hooks.example.test/calls");
  await connections.getByLabel("HTTP kimlik doğrulama").selectOption("bearer");
  await connections
    .getByLabel("HTTP erişim anahtarı")
    .fill("synthetic-browser-http-token");
  await connections
    .getByRole("button", { name: "HTTP bağlantısını kaydet", exact: true })
    .click();
  await expect(
    connections.getByText("Synthetic CRM", { exact: true }),
  ).toBeVisible();
  await expect(connections.getByLabel("HTTP erişim anahtarı")).toHaveValue("");
  const created = await page.evaluate(async (f) => {
    const session = await (await fetch("/v1/auth/session")).json();
    const base = `/v1/workspaces/${f.scope}`;
    const old = await (await fetch(`${base}/agents/${f.agent}`)).json();
    const result = await fetch(`${base}/agents`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": session.csrf_token,
      },
      body: JSON.stringify({
        ...old.content,
        agent_name: "Webhook Asistanı",
        mcp_tools: [],
        post_call_actions: [],
      }),
    });
    if (!result.ok) throw new Error("Synthetic agent creation failed");
    return result.json();
  }, fixture.mcp);
  await page.goto(`/agentler/${created.id}`);
  await page.getByRole("tab", { name: "Çağrı sonrası", exact: true }).click();
  await page
    .getByRole("button", { name: "HTTP isteği ekle", exact: true })
    .click();
  const action = page.getByRole("region", { name: "HTTP işlemi 1" });
  await action
    .getByLabel("HTTP hedef bağlantısı")
    .selectOption({ label: "Synthetic CRM" });
  await action.getByLabel("HTTP yöntemi").selectOption("PATCH");
  await expect(action.getByLabel("Ne zaman gönderilsin?")).toHaveValue(
    "answered",
  );
  await action
    .getByLabel("Ne zaman gönderilsin?")
    .selectOption("summary_ready");
  await action
    .getByRole("button", { name: "Gövde alanı ekle", exact: true })
    .click();
  const rows = action.locator('[aria-label^="Gövde alanı"]');
  await rows.nth(1).getByLabel("Hedef alan adı").fill("reason");
  await rows.nth(1).getByLabel("Değer kaynağı").selectOption("summary.subject");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(2).getByLabel("Değer kaynağı")).toHaveValue(
    "summary_status",
  );
  await rows.nth(1).getByLabel("Bilgi bulunamazsa").selectOption("omit");
  await action
    .getByRole("button", { name: "Sorgu alanı ekle", exact: true })
    .click();
  const query = action.locator('[aria-label="Sorgu alanı 1"]');
  await query.getByLabel("Hedef alan adı").fill("active");
  await query.getByLabel("Değer kaynağı").selectOption("literal");
  await query.getByLabel("Sabit değer türü").selectOption("boolean");
  await query.getByLabel("Sabit değer", { exact: true }).selectOption("true");
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Taslak kaydedildi" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Gönderim iznini incele", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByText("Hedef: PATCH https://hooks.example.test/calls", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(dialog).toContainText("Gönderim koşulu: Yalnızca özet hazırsa");
  await dialog
    .getByText("Örnek istek · gerçek çağrı verisi içermez", { exact: true })
    .click();
  await expect(dialog.locator("pre").last()).toContainText("active=true");
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await dialog
    .getByRole("button", {
      name: "Bu hedeflere gönderime izin ver",
      exact: true,
    })
    .click();
  await expect(dialog).not.toBeVisible();
  const saved = await page.evaluate(
    async ({ scope, id }) => {
      const base = `/v1/workspaces/${scope}/agents/${id}`;
      return {
        agent: await (await fetch(base)).json(),
        grants: await (await fetch(base + "/action-grants")).json(),
      };
    },
    { scope: fixture.mcp.scope, id: created.id },
  );
  expect(saved.agent.content.post_call_actions[0].query.active.value).toBe(
    true,
  );
  expect(saved.grants.grants).toHaveLength(1);
  expect(saved.agent.content.post_call_actions[0].condition).toBe(
    "summary_ready",
  );
  await page.reload();
  await page.getByRole("tab", { name: "Çağrı sonrası", exact: true }).click();
  await expect(action.getByLabel("Ne zaman gönderilsin?")).toHaveValue(
    "summary_ready",
  );
  await action
    .getByLabel("Ne zaman gönderilsin?")
    .selectOption("summary_failed");
  await expect(
    page.getByRole("button", { name: "Gönderim iznini incele", exact: true }),
  ).toBeDisabled();
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
    "Gönderim koşulu: Yalnızca özet oluşturulamadıysa",
  );
  await expect(
    dialog.getByRole("button", {
      name: "Bu hedeflere gönderime izin ver",
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    dialog.getByRole("button", {
      name: "Bu gönderim iznini kaldır",
      exact: true,
    }),
  ).toHaveCount(0);
  await page.screenshot({
    path: "/evidence/http-condition-review-mobile.png",
    fullPage: true,
  });
  const changed = await page.evaluate(
    async ({ scope, id }) =>
      (
        await fetch(`/v1/workspaces/${scope}/agents/${id}/action-review`)
      ).json(),
    { scope: fixture.mcp.scope, id: created.id },
  );
  expect(changed.review.schema_version).toBe(4);
  expect(changed.review_digest).not.toBe(saved.grants.grants[0].review_digest);
  await page.keyboard.press("Escape");
  await page.goto("/baglantilar");
  const targetCard = connections
    .getByRole("article")
    .filter({ hasText: "Synthetic CRM" });
  await targetCard
    .getByRole("button", { name: "HTTP bağlantısını kapat", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Vazgeç", exact: true })
    .click();
  await expect(
    targetCard.getByRole("button", {
      name: "HTTP bağlantısını kapat",
      exact: true,
    }),
  ).toBeVisible();
  await targetCard
    .getByRole("button", { name: "HTTP bağlantısını kapat", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Bu HTTP bağlantısını kapat", exact: true })
    .click();
  await expect(targetCard.getByText(/Kapalı ·/)).toBeVisible();
  expect(external).toEqual([]);
  expect(errors).toEqual([]);
});
