import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
const fixture = JSON.parse(
  readFileSync(process.env.ALOJAN_WEB_TEST_FIXTURE!, "utf8"),
);

test("transcript sharing is opt-in, reviewed with disclosure, reloads and can be removed", async ({
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
    const old = await (await fetch(`${base}/agents/${f.agent}`)).json();
    const target = await fetch(`${base}/http-connections`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        label: "Transcript preview",
        endpoint: "https://transcript.example.test/calls",
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
        agent_name: "Döküm Asistanı",
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
    .selectOption({ label: "Transcript preview" });
  const toggle = action.getByLabel("Konuşma dökümünü bu hedefle paylaş", {
    exact: true,
  });
  await expect(toggle).not.toBeChecked();
  await toggle.check();
  await expect(action).toContainText("otomatik sansür uygulanmaz");
  const rows = action.locator('[aria-label^="Gövde alanı"]');
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(1).getByLabel("Değer kaynağı")).toHaveValue(
    "transcript.text",
  );
  await expect(rows.nth(2).getByLabel("Değer kaynağı")).toHaveValue(
    "transcript.status",
  );
  await expect(
    rows.nth(1).getByRole("button", { name: "Alanı kaldır", exact: true }),
  ).toBeDisabled();
  const save = async () => {
    await page
      .getByRole("button", { name: "Taslağı kaydet", exact: true })
      .click();
    await expect(
      page.getByRole("status").filter({ hasText: "Taslak kaydedildi" }),
    ).toBeVisible();
  };
  await save();
  await page.reload();
  await page.getByRole("tab", { name: "Çağrı sonrası", exact: true }).click();
  await expect(toggle).toBeChecked();
  await page.getByRole("button", { name: "Metni önizle", exact: true }).click();
  await expect(
    page
      .getByText(
        /yazılı dökümü, görüşme sonunda bağlı hizmet sağlayıcılarla paylaşılabilir/,
      )
      .last(),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Gönderim iznini incele", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Bu hedefe konuşma dökümü gönderilecek");
  await expect(dialog).toContainText("otomatik sansür uygulanmaz");
  await dialog
    .getByText("Örnek istek · gerçek çağrı verisi içermez", { exact: true })
    .click();
  await expect(dialog.locator("pre").last()).toContainText(
    "Örnek görüşme metni",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(
    true,
  );
  await page.screenshot({
    path: "/evidence/transcript-consent-mobile.png",
    fullPage: false,
  });
  await dialog
    .getByRole("button", {
      name: "Bu hedeflere gönderime izin ver",
      exact: true,
    })
    .click();
  await expect(dialog).not.toBeVisible();
  await toggle.uncheck();
  await expect(rows).toHaveCount(1);
  await save();
  const state = await page.evaluate(
    async ({ scope, id }) => {
      const path = `/v1/workspaces/${scope}/agents/${id}`;
      const session = await (await fetch("/v1/auth/session")).json();
      return {
        agent: await (await fetch(path)).json(),
        review: await (await fetch(path + "/action-review")).json(),
        preview: await (
          await fetch(path + "/preview", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-CSRF-Token": session.csrf_token,
            },
            body: "{}",
          })
        ).json(),
      };
    },
    { scope: fixture.mcp.scope, id: created.id },
  );
  expect(
    state.agent.content.post_call_actions[0].transcript_policy,
  ).toBeUndefined();
  expect(state.preview.greeting).not.toContain("yazılı dökümü");
  expect(state.review.review.actions[0].body).toEqual({
    call_id: { kind: "source", source: "call_id", on_missing: "fail" },
  });
  expect(errors).toEqual([]);
});
