import { test, expect, type Page } from "@playwright/test";
import { readFileSync } from "node:fs";
const fixture = JSON.parse(
  readFileSync(process.env.ALOJAN_WEB_TEST_FIXTURE!, "utf8"),
);
async function login(
  page: Page,
  address = fixture.login,
  agentName = "Test Asistanı",
) {
  await page.goto("/giris");
  await page.getByLabel("E-posta", { exact: true }).fill(address);
  await page.getByLabel("Şifre", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Agentlerin", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(agentName, { exact: true })).toBeVisible();
}

test("HTTPS login, session security, scoped listing and logout", async ({
  page,
  context,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await login(page);
  expect(await page.evaluate(() => document.cookie)).not.toContain(
    "__Host-alojan",
  );
  const cookie = (await context.cookies()).find(
    (c) => c.name === "__Host-alojan",
  );
  expect(cookie).toMatchObject({
    secure: true,
    httpOnly: true,
    sameSite: "Strict",
    path: "/",
  });
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
  const denied = await page.evaluate(
    async (scope) => (await fetch(`/v1/workspaces/${scope}/agents`)).status,
    fixture.other_scope,
  );
  expect(denied).toBe(404);
  await expect(
    page.getByText("Other private agent", { exact: true }),
  ).toHaveCount(0);
  await page.screenshot({ path: "/evidence/agent-list.png", fullPage: true });
  await page.getByRole("link", { name: /Hesap ayarları/ }).click();
  await page.getByRole("button", { name: "Çıkış yap", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Tekrar hoş geldin" }),
  ).toBeVisible();
  expect(
    (await context.cookies()).find((c) => c.name === "__Host-alojan"),
  ).toBeUndefined();
  expect(errors).toEqual([]);
});

test("release rollback is reviewed, version checked and never changes draft or routing", async ({
  page,
}) => {
  await page.goto("/giris");
  await page.getByLabel("E-posta", { exact: true }).fill(fixture.call_login);
  await page.getByLabel("Şifre", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Agentlerin", exact: true }),
  ).toBeVisible();
  await page.getByRole("link").filter({ hasText: "Çağrı Asistanı" }).click();
  const path = `/v1/workspaces/${fixture.call_scope}/agents/${fixture.call_agent}`;
  const read = () =>
    page.evaluate(
      async (path) => ({
        releases: await (await fetch(`${path}/releases`)).json(),
        draft: await (await fetch(path)).json(),
      }),
      path,
    );
  const before = await read();
  expect(before.releases.releases).toHaveLength(2);
  await page.getByLabel("Görevi", { exact: true }).fill("Kaydedilmemiş taslak");
  const historyButton = page.getByRole("button", {
    name: "Sürüm geçmişi",
    exact: true,
  });
  await historyButton.click();
  const dialog = page.getByRole("dialog");
  const choose = () =>
    dialog.getByRole("button", { name: "Sürüm 1 seç", exact: true });
  await expect(choose()).toBeDisabled();
  await dialog.getByRole("button", { name: "Kapat", exact: true }).click();
  await page
    .getByLabel("Görevi", { exact: true })
    .fill(before.draft.content.instructions);
  await historyButton.click();
  await choose().click();
  await expect(
    dialog.getByRole("region", { name: "Geri dönüş onayı" }),
  ).toContainText("Sürüm 1 yeniden yayınlanacak");
  await expect(dialog).toContainText(
    "numara eşlemeleri ve devam eden görüşmeler değişmez",
  );
  await dialog.getByRole("button", { name: "Kapat", exact: true }).click();
  expect((await read()).releases).toEqual(before.releases);
  await historyButton.click();
  await choose().click();
  // A second tab publishes after this dialog read its version.
  const concurrent = await page.evaluate(
    async ({ path, preparation }) => {
      const session = await (await fetch("/v1/auth/session")).json();
      return (
        await fetch(`${path}/publish`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": session.csrf_token,
            "If-Match": '"2"',
          },
          body: JSON.stringify({ preparation_id: preparation }),
        })
      ).status;
    },
    { path, preparation: fixture.call_preparation },
  );
  expect(concurrent).toBe(201);
  const confirm = () =>
    dialog.getByRole("button", {
      name: "Seçilen sürümü yeniden yayınla",
      exact: true,
    });
  await confirm().click();
  await expect(dialog).toContainText("Yayın başka bir yerde değişti");
  await expect(choose()).toBeDisabled();
  expect((await read()).releases.releases).toHaveLength(3);
  await dialog
    .getByRole("button", { name: "Geçmişi yenile", exact: true })
    .click();
  await choose().click();
  await page.screenshot({
    path: "/evidence/release-rollback.png",
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(async () => (await dialog.boundingBox())?.x ?? -1)
    .toBeGreaterThanOrEqual(15);
  await expect
    .poll(async () => {
      const b = await dialog.boundingBox();
      return b ? b.x + b.width : 999;
    })
    .toBeLessThanOrEqual(375);
  await expect
    .poll(async () => {
      const b = await page.locator(".sidebar").boundingBox();
      return b ? b.x + b.width : 0;
    })
    .toBeLessThanOrEqual(0);
  expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(
    true,
  );
  await page.screenshot({
    path: "/evidence/release-rollback-mobile.png",
    fullPage: false,
  });
  // Accept in the isolated API, then lose the response. UI must require a fresh review.
  await page.route(
    `**/agents/${fixture.call_agent}/rollback`,
    async (route) => {
      const response = await route.fetch();
      expect(response.status()).toBe(201);
      await route.abort("failed");
    },
    { times: 1 },
  );
  await confirm().click();
  await expect(dialog).toContainText("İşlem tamamlanmış olabilir");
  await expect(confirm()).toHaveCount(0);
  expect((await read()).releases.releases).toHaveLength(4);
  await dialog
    .getByRole("button", { name: "Geçmişi yenile", exact: true })
    .click();
  await expect(dialog).toContainText("Sürüm 4 · Son yayın");
  await expect(dialog).toContainText("Sürüm 1 üzerinden geri dönüş");
  expect((await read()).releases.releases).toHaveLength(4);
  await dialog
    .getByRole("button", { name: "Sürüm 2 seç", exact: true })
    .click();
  await confirm().click();
  await expect(dialog).toContainText("yeni sürüm 5 olarak yayınlandı");
  await expect(dialog).toContainText("Sürüm 5 · Son yayın");
  const after = await read();
  expect(after.draft).toEqual(before.draft);
  expect(after.releases.releases).toHaveLength(5);
  expect(after.releases.releases[1].rollback_of).toBe(fixture.call_release);
  const numbers = await page.evaluate(
    async (scope) => (await fetch(`/v1/workspaces/${scope}/numbers`)).json(),
    fixture.call_scope,
  );
  expect(numbers.numbers[0].release_id).toBe(fixture.call_release);
});

test("editing preserves long instructions and unexposed configuration; conflict keeps local work", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("link").filter({ hasText: "Test Asistanı" }).click();
  await expect(page.getByLabel("Görevi", { exact: true })).toHaveValue(
    fixture.instructions,
  );
  expect(
    (await page.getByLabel("Görevi", { exact: true }).boundingBox())!.height,
  ).toBeLessThanOrEqual(480);
  await expect(
    page.getByLabel("Model", { exact: true }).locator("option:checked"),
  ).toHaveText("GPT-OSS 120B");
  await page.screenshot({ path: "/evidence/agent-editor.png", fullPage: true });
  await page
    .getByLabel("Görevi", { exact: true })
    .fill(fixture.instructions + " Yeni not.");
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Taslak kaydedildi");
  const saved = await page.evaluate(
    async ({ scope, agent }) =>
      (await fetch(`/v1/workspaces/${scope}/agents/${agent}`)).json(),
    fixture,
  );
  expect(saved.content.instructions).toBe(fixture.instructions + " Yeni not.");
  expect(saved.content.vocabulary).toEqual(["Test Terimi"]);
  expect(saved.content.note_ack_template).toBe(fixture.note_ack);
  await page.getByLabel("Görevi", { exact: true }).fill("Local unsaved edit");
  await page.evaluate(async ({ scope, agent }) => {
    const s = await (await fetch("/v1/auth/session")).json();
    const path = `/v1/workspaces/${scope}/agents/${agent}`;
    const a = await (await fetch(path)).json();
    await fetch(path, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": s.csrf_token,
        "If-Match": `"${a.version}"`,
      },
      body: JSON.stringify(a.content),
    });
  }, fixture);
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "başka bir yerde değişti" }),
  ).toBeVisible();
  await expect(page.getByLabel("Görevi", { exact: true })).toHaveValue(
    "Local unsaved edit",
  );
});

test("new draft creation and preview; missing audio prevents publishing", async ({
  page,
}) => {
  await login(page);
  await page
    .getByRole("button", { name: "Agent oluştur", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Agent adı", { exact: true }).fill("Yeni Test");
  await dialog
    .getByLabel("Kimin asistanı?", { exact: true })
    .fill("Test Sahibi");
  await dialog
    .getByLabel("Görevi", { exact: true })
    .fill("Arayanın mesajını not al.");
  await dialog
    .getByRole("button", { name: "Agent oluştur", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Yeni Test", exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Model bağlantısı", { exact: true })
    .selectOption(fixture.connection);
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(page.getByRole("status")).toContainText("Taslak kaydedildi");
  await page.getByRole("button", { name: "Metni önizle", exact: true }).click();
  await expect(page.locator("blockquote")).toContainText("yapay zekâ");
  await page
    .getByRole("button", { name: "Sürümü yayınla", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "ses dosyalarının hazırlanması",
  );
  await expect(
    page.getByRole("button", { name: "Bu sürümü yayınla", exact: true }),
  ).toHaveCount(0);
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Sesi hazırla", exact: true }).click();
  await expect(
    page.getByText("Hazırlık kuyruğunda", { exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByText("Hazırlık kuyruğunda", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Sesi hazırla", exact: true }),
  ).toHaveCount(0);
});

test("CSRF rejection and expired session cannot save", async ({
  page,
  context,
}) => {
  await login(page);
  const status = await page.evaluate(
    async (scope) =>
      (
        await fetch(`/v1/workspaces/${scope}/agents`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: "{}",
        })
      ).status,
    fixture.scope,
  );
  expect(status).toBe(403);
  await page.getByRole("link").filter({ hasText: "Test Asistanı" }).click();
  await page
    .getByLabel("Görevi", { exact: true })
    .fill("Must not save without session");
  await context.clearCookies();
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Tekrar hoş geldin" }),
  ).toBeVisible();
});

test("registration creates an empty separate workspace", async ({ page }) => {
  await page.goto("/kayit");
  await page.getByLabel("Adın soyadın", { exact: true }).fill("New Test Owner");
  await page
    .getByLabel("E-posta", { exact: true })
    .fill("new.user@example.test");
  await page
    .getByLabel("Şifre", { exact: true })
    .fill("A unique synthetic password 123!");
  await page
    .getByRole("button", { name: "Hesap oluştur", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Ona bir isim ver." }),
  ).toBeVisible();
  await expect(page.getByText("Test Asistanı", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "Şimdilik atla" }).click();
  await expect(
    page.getByRole("heading", { name: "İstediğinde başlayalım." }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Çalışma alanına git" }).click();
  await expect(
    page.getByRole("heading", { name: "İlk agentinle tanışmaya hazır mısın?" }),
  ).toBeVisible();
});

test("mobile navigation, controls and layout remain usable", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/giris");
  await page.screenshot({ path: "/evidence/login-mobile.png", fullPage: true });
  await login(page);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.getByRole("button", { name: "Menüyü aç" }).click();
  await page.getByRole("link", { name: "Numaralar", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Numaraların" }),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Menüyü aç" })).toBeVisible();
  await page.getByRole("button", { name: "Menüyü aç" }).click();
  await page.getByRole("link", { name: "Agentler", exact: true }).click();
  await page.getByRole("link").filter({ hasText: "Test Asistanı" }).click();
  await expect(page.getByLabel("Görevi", { exact: true })).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/evidence/editor-mobile.png",
    fullPage: true,
  });
});

test("connections are write-only and unverified numbers cannot route calls", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("link", { name: "Bağlantılar", exact: true }).click();
  await page.getByLabel("Bağlantı türü").selectOption("telegram");
  await page.getByLabel("Bağlantı adı", { exact: true }).fill("Test Telegram");
  await page.getByLabel("Telegram sohbet kimliği").fill("123456789");
  await page
    .getByLabel("Bot tokenı")
    .fill("123456789:synthetic_token_never_sent_123456");
  await page.getByRole("button", { name: "Bağlantıyı kaydet" }).click();
  await expect(page.getByText("Test Telegram", { exact: true })).toBeVisible();
  await expect(page.getByLabel("Bot tokenı")).toHaveValue("");
  const connections = await page.evaluate(
    async (scope) =>
      (await fetch(`/v1/workspaces/${scope}/telegram-connections`)).text(),
    fixture.scope,
  );
  expect(connections).not.toContain("synthetic_token");
  expect(connections).not.toContain("ciphertext");
  await page.getByRole("link", { name: "Numaralar", exact: true }).click();
  await page.getByLabel("0850 numaran").fill("+908500000012");
  await page.getByRole("button", { name: "Numara ekle" }).click();
  await expect(
    page.getByText("Sahiplik doğrulaması bekleniyor", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Agent bağla" }),
  ).toBeDisabled();
  const numbers = await page.evaluate(
    async (scope) => (await fetch(`/v1/workspaces/${scope}/numbers`)).json(),
    fixture.scope,
  );
  expect(numbers.numbers).toHaveLength(1);
  expect(numbers.numbers[0]).toMatchObject({
    enabled: false,
    release_id: null,
    status: "pending",
  });
});

test("prepared audio plays and dirty drafts invalidate playback", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("link").filter({ hasText: "Test Asistanı" }).click();
  await page.getByRole("button", { name: "Sesi dinle", exact: true }).click();
  const audio = page.getByLabel("Hazır agent sesi", { exact: true });
  await expect(audio).toBeVisible();
  await expect
    .poll(() => audio.evaluate((a: HTMLAudioElement) => a.readyState))
    .toBeGreaterThanOrEqual(2);
  expect(
    await audio.evaluate((a: HTMLAudioElement) => a.duration),
  ).toBeGreaterThan(0);
  await page.getByLabel("Görevi", { exact: true }).fill("Unsaved draft change");
  await expect(audio).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Sesi dinle", exact: true }),
  ).toBeDisabled();
});

test("Telegram review requires explicit permission and supports publication and revocation", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("link").filter({ hasText: "Test Asistanı" }).click();
  await page.getByRole("tab", { name: "Çağrı sonrası", exact: true }).click();
  await page.getByRole("button", { name: "Telegram bildirimi ekle" }).click();
  await page
    .getByLabel("Telegram bağlantısı", { exact: true })
    .selectOption({ label: "Browser Telegram" });
  await page.getByLabel("Ne zaman gönderilsin?").selectOption("summary_failed");
  await page.getByLabel("Arayan numara", { exact: true }).check();
  await expect(
    page.getByLabel("Arayan numaranın kaynağı", { exact: true }),
  ).toBeChecked();
  await expect(
    page.getByLabel("Arayan numaranın kaynağı", { exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByRole("button", { name: "Gönderim iznini incele" }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Taslak kaydedildi" }),
  ).toBeVisible();
  const grants = async () =>
    page.evaluate(
      async ({ scope, agent }) =>
        (
          await fetch(`/v1/workspaces/${scope}/agents/${agent}/action-grants`)
        ).json(),
      fixture,
    );
  expect((await grants()).grants).toHaveLength(0);
  await page.getByRole("button", { name: "Gönderim iznini incele" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("123456789");
  await expect(dialog).toContainText("Özet · Açıklama");
  await expect(dialog).toContainText(
    "Gönderim koşulu: Yalnızca özet oluşturulamadıysa",
  );
  expect((await grants()).grants).toHaveLength(0);
  await page.screenshot({
    path: "/evidence/telegram-review.png",
    fullPage: true,
  });
  await dialog
    .getByRole("button", { name: "Bu hedeflere gönderime izin ver" })
    .click();
  await expect(dialog).toHaveCount(0);
  expect(
    (await grants()).grants.filter((g: { enabled: boolean }) => g.enabled),
  ).toHaveLength(1);
  await page
    .getByRole("button", { name: "Sürümü yayınla", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Bu sürümü yayınla", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Yeni sürüm yayınlandı" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Gönderim iznini incele" }).click();
  await page
    .getByRole("button", { name: "Bu gönderim iznini kaldır", exact: true })
    .click();
  await expect(dialog).toContainText("yayındaki sürümler de etkilenir");
  await page.getByRole("button", { name: "İzni kaldırmayı onayla" }).click();
  await expect(dialog).toHaveCount(0);
  expect(
    (await grants()).grants.filter((g: { enabled: boolean }) => g.enabled),
  ).toHaveLength(0);
});

test("scoped call detail renders summary and untrusted note safely on mobile", async ({
  page,
}) => {
  await page.goto("/giris");
  await page.getByLabel("E-posta", { exact: true }).fill(fixture.call_login);
  await page.getByLabel("Şifre", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Agentlerin", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Aramalar", exact: true }).click();
  await expect(page.getByText("Özet hazır", { exact: true })).toBeVisible();
  await page.getByRole("link").filter({ hasText: "Çağrı Asistanı" }).click();
  await expect(
    page.getByRole("heading", { name: "Görüşme detayı" }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Görüşme özeti" }),
  ).toContainText("Sentetik özet.");
  const note = page.getByRole("region", { name: "Son alınan not" });
  await expect(note).toContainText(
    '<img src=x onerror="window.callInjected=true">',
  );
  await expect(note).toContainText("Arayan tarafından onaylandı");
  await expect(note.locator("img")).toHaveCount(0);
  expect(
    await page.evaluate(() => Reflect.get(window, "callInjected")),
  ).toBeUndefined();
  await expect(
    page.getByRole("region", { name: "Bildirim sonucu" }),
  ).toContainText("Sonuç doğrulanamadı");
  const transcript = page.getByRole("region", {
    name: "Görüşme dökümü",
    exact: true,
  });
  await transcript
    .getByRole("button", { name: "Dökümü göster", exact: true })
    .click();
  await expect(transcript).toContainText("Sentetik arayan metni.");
  await expect(transcript).toContainText("İletilmek üzere not aldım.");
  await expect(transcript).toContainText("doğrulanmış metin yok");
  await expect(transcript.locator("li")).toHaveCount(50);
  await expect(transcript.locator("script")).toHaveCount(0);
  expect(
    await page.evaluate(() => Reflect.get(window, "transcriptInjected")),
  ).toBeUndefined();
  await transcript
    .getByRole("button", { name: "Sonraki konuşmalar", exact: true })
    .click();
  await expect(transcript.locator("li")).toHaveCount(2);
  await expect(transcript).toContainText("Sentetik devam 48.");
  await transcript
    .getByRole("button", { name: "Başa dön", exact: true })
    .click();
  await expect(transcript.locator("li")).toHaveCount(50);
  await transcript
    .getByRole("button", { name: "Dökümü gizle", exact: true })
    .click();
  await page.screenshot({ path: "/evidence/call-detail.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await expect
    .poll(async () => {
      const box = await page.locator(".sidebar").boundingBox();
      return box ? box.x + box.width : 0;
    })
    .toBeLessThanOrEqual(0);
  await page.screenshot({
    path: "/evidence/call-detail-mobile.png",
    fullPage: true,
  });
  await page.reload();
  await expect(note).toContainText("Sentetik görüşme notu");
  const denied = await page.evaluate(
    async (f) =>
      (await fetch(`/v1/workspaces/${f.scope}/calls/${f.call_id}`)).status,
    fixture,
  );
  expect(denied).toBe(404);
  await page.getByRole("link", { name: "Aramalara dön" }).click();
  await expect(
    page.getByRole("heading", { name: "Aramalar", exact: true }),
  ).toBeVisible();
});

test("retry review requires consent, refreshes stale state and reuses a lost-response request", async ({
  page,
}) => {
  await page.goto("/giris");
  await page.getByLabel("E-posta", { exact: true }).fill(fixture.call_login);
  await page.getByLabel("Şifre", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Agentlerin", exact: true }),
  ).toBeVisible();
  await page.goto(`/aramalar/${fixture.call_id}`);
  const reviewButton = page.getByRole("button", {
    name: "Yeniden gönderimi incele",
    exact: true,
  });
  await reviewButton.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Call notification");
  await expect(dialog).toContainText("123456789");
  await expect(dialog).toContainText("Sentetik konu");
  const confirm = dialog.getByRole("button", {
    name: "Bu bildirimi yeniden gönder",
    exact: true,
  });
  await expect(confirm).toBeDisabled();
  const readJob = () =>
    page.evaluate(
      async (f) =>
        (
          await fetch(
            `/v1/workspaces/${f.call_scope}/agents/${f.call_agent}/deliveries/${f.call_job}`,
          )
        ).json(),
      fixture,
    );
  expect((await readJob()).retries).toHaveLength(0);
  await dialog.getByRole("button", { name: "Vazgeç", exact: true }).click();
  expect((await readJob()).retries).toHaveLength(0);
  await reviewButton.click();
  await expect(confirm).toBeDisabled();
  await dialog.getByRole("checkbox").check();
  const retryPath = `**/deliveries/${fixture.call_job}/retry`;
  await page.route(
    retryPath,
    (route) =>
      route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ error: "stale_retry_review" }),
      }),
    { times: 1 },
  );
  await confirm.click();
  await expect(dialog).toContainText("Gönderim durumu değişti");
  expect((await readJob()).retries).toHaveLength(0);
  await dialog
    .getByRole("button", { name: "Bilgileri yenile", exact: true })
    .click();
  await expect(confirm).toBeDisabled();
  await dialog.getByRole("checkbox").check();
  await page.screenshot({
    path: "/evidence/delivery-retry-review.png",
    fullPage: false,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(
    true,
  );
  await expect
    .poll(async () => {
      const b = await dialog.boundingBox();
      return b ? b.x : -1;
    })
    .toBeGreaterThanOrEqual(15);
  await expect
    .poll(async () => {
      const b = await dialog.boundingBox();
      return b ? b.x + b.width : 999;
    })
    .toBeLessThanOrEqual(375);
  await expect
    .poll(async () => {
      const b = await page.locator(".sidebar").boundingBox();
      return b ? b.x + b.width : 0;
    })
    .toBeLessThanOrEqual(0);
  await page.screenshot({
    path: "/evidence/delivery-retry-mobile.png",
    fullPage: false,
  });
  const requests: unknown[] = [];
  page.on("request", (r) => {
    if (r.url().endsWith(`/deliveries/${fixture.call_job}/retry`))
      requests.push(r.postDataJSON());
  });
  // The real API accepts once; deliberately discard only its response in the browser.
  await page.route(
    retryPath,
    async (route) => {
      const response = await route.fetch();
      expect(response.status()).toBe(202);
      await route.abort("failed");
    },
    { times: 1 },
  );
  await confirm.click();
  await expect(dialog).toContainText("İstek alınmış olabilir");
  expect((await readJob()).retries).toHaveLength(1);
  await dialog
    .getByRole("button", { name: "Aynı isteği tekrar dene", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Yeniden gönderim isteği sıraya alındı" }),
  ).toContainText("Yeniden gönderim isteği sıraya alındı");
  await expect(
    page.getByText("Onaylanan yeniden deneme sırada.", { exact: true }),
  ).toBeVisible();
  expect(requests).toHaveLength(2);
  expect(requests[0]).toEqual(requests[1]);
  const job = await readJob();
  expect(job.retries).toHaveLength(1);
  expect(job.status).toBe("delivery_unknown");
  expect(job.attempts).toBe(1);
  await expect(reviewButton).toHaveCount(0);
});

test("performance distinguishes measured, missing, excluded and foreign calls", async ({
  page,
}) => {
  await login(page);
  await page.getByRole("link", { name: "Performans", exact: true }).click();
  const panel = page.getByRole("region", {
    name: "Yanıt performansı",
    exact: true,
  });
  await expect(panel).toContainText("Henüz aktarılmış yanıt ölçümü yok");
  await expect(panel.getByRole("table")).toHaveCount(0);
  await page.getByRole("link", { name: /Hesap ayarları/ }).click();
  await page.getByRole("button", { name: "Çıkış yap", exact: true }).click();
  await expect(page).toHaveURL(/\/giris$/);
  await page.getByLabel("E-posta", { exact: true }).fill(fixture.call_login);
  await page.getByLabel("Şifre", { exact: true }).fill(fixture.password);
  await page.getByRole("button", { name: "Giriş yap", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Agentlerin", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Performans", exact: true }).click();
  await expect(panel).toContainText("5 kayıtlı konuşma turu");
  await expect(panel).toContainText(
    "2 başarısız, kesilmiş veya hatırlatma turu",
  );
  const row = panel
    .getByRole("row")
    .filter({ hasText: "Konuşma sonundan yanıta (tahmin)" });
  await expect(row).toContainText("200 ms");
  await expect(row).toContainText("300 ms");
  await expect(row).toContainText("2 / 1");
  await expect(panel).toContainText("50 geçerli yanıt ölçümünden az veri");
  await page
    .getByLabel("Agent filtresi", { exact: true })
    .selectOption(fixture.call_agent);
  await expect(row).toContainText("200 ms");
  await page.screenshot({ path: "/evidence/performance.png", fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect
    .poll(async () => {
      const b = await page.locator(".sidebar").boundingBox();
      return b ? b.x + b.width : 0;
    })
    .toBeLessThanOrEqual(0);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "/evidence/performance-mobile.png",
    fullPage: true,
  });
  await page.goto(`/aramalar/${fixture.call_id}`);
  await expect(panel.getByRole("table")).toHaveCount(0);
  await panel
    .getByRole("button", { name: "Ölçümleri göster", exact: true })
    .click();
  await expect(row).toContainText("200 ms");
  const denied = await page.evaluate(
    async (scope) =>
      (await fetch(`/v1/workspaces/${scope}/performance`)).status,
    fixture.scope,
  );
  expect(denied).toBe(404);
});

for (const failure of ["lost", "server-error"] as const)
  test(`uncertain agent creation (${failure}) requires checking the list instead of duplicate submission`, async ({
    page,
  }) => {
    await login(page, "other.owner@example.test", "Other private agent");
    const path = `/v1/workspaces/${fixture.other_scope}/agents`;
    let attempts = 0;
    await page.route("**" + path, async (route) => {
      if (route.request().method() !== "POST") return route.continue();
      attempts++;
      const response = await route.fetch();
      expect(response.status()).toBe(201);
      if (failure === "lost") return route.abort("failed");
      return route.fulfill({ status: 503, json: { error: "unavailable" } });
    });
    await page
      .getByRole("button", { name: "Agent oluştur", exact: true })
      .click();
    const dialog = page.getByRole("dialog");
    const name = `Uncertain agent ${failure}`;
    await dialog.getByLabel("Agent adı", { exact: true }).fill(name);
    await dialog.getByLabel("Görevi", { exact: true }).fill("Synthetic task");
    await dialog
      .getByRole("button", { name: "Agent oluştur", exact: true })
      .click();
    await expect(dialog).toContainText("Agent kaydedilmiş olabilir");
    await expect(
      dialog.getByRole("button", { name: "Agent oluştur", exact: true }),
    ).toBeDisabled();
    await dialog
      .locator("form")
      .evaluate((form: HTMLFormElement) => form.requestSubmit());
    await dialog
      .getByRole("button", { name: "Agent listesini kontrol et", exact: true })
      .click();
    await expect(page.getByRole("link").filter({ hasText: name })).toHaveCount(
      1,
    );
    const rows = await page.evaluate(
      async (path) => (await (await fetch(path)).json()).agents,
      path,
    );
    expect(rows.filter((a: { name: string }) => a.name === name)).toHaveLength(
      1,
    );
    expect(attempts).toBe(1);
  });

test("logout clears retained drafts before another login", async ({ page }) => {
  await login(page, "other.owner@example.test", "Other private agent");
  await page
    .getByRole("link")
    .filter({ hasText: "Other private agent" })
    .click();
  const saved = await page.getByLabel("Görevi", { exact: true }).inputValue();
  await page.getByLabel("Görevi", { exact: true }).fill("Private unsaved text");
  await page.goBack();
  await expect(page).toHaveURL(/\/agentler$/);
  await page.getByRole("link", { name: /Hesap ayarları/ }).click();
  await page.getByRole("button", { name: "Çıkış yap", exact: true }).click();
  await login(page, "other.owner@example.test", "Other private agent");
  await page
    .getByRole("link")
    .filter({ hasText: "Other private agent" })
    .click();
  await expect(page.getByLabel("Görevi", { exact: true })).toHaveValue(saved);
});
