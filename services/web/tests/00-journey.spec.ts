import { test, expect, type Page } from "@playwright/test";
import { existsSync, readFileSync, renameSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

const directory = dirname(process.env.ALOJAN_WEB_TEST_FIXTURE!);
const fixture = JSON.parse(
  readFileSync(process.env.ALOJAN_WEB_TEST_FIXTURE!, "utf8"),
);

async function operatorStep(stage: string, data: object) {
  // File bridge to the disposable-schema harness; no application bypass endpoint.
  const request = join(directory, `journey-${stage}.request.json`);
  const response = join(directory, `journey-${stage}.response.json`);
  writeFileSync(`${request}.tmp`, JSON.stringify(data));
  renameSync(`${request}.tmp`, request);
  await expect.poll(() => existsSync(response), { timeout: 15000 }).toBe(true);
  expect(JSON.parse(readFileSync(response, "utf8"))).toMatchObject({
    stage,
    synthetic: true,
  });
}
async function read(page: Page, path: string) {
  return page.evaluate(
    async (path) => (await fetch(`/v1/${path}`)).json(),
    path,
  );
}
async function save(page: Page) {
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Taslak kaydedildi" }),
  ).toBeVisible();
}

test("new owner configures, prepares, publishes and binds only after separate readiness gates", async ({
  page,
}) => {
  test.setTimeout(90000);
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/kayit");
  await page.getByLabel("Adın soyadın", { exact: true }).fill("Journey Owner");
  await page
    .getByLabel("E-posta", { exact: true })
    .fill("journey.owner@example.test");
  await page
    .getByLabel("Şifre", { exact: true })
    .fill("Synthetic journey password 123!");
  await page
    .getByRole("button", { name: "Hesap oluştur", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Ona bir isim ver." }),
  ).toBeVisible();
  await page.getByLabel("Agentının adı").fill("Yolculuk Asistanı");
  await page.getByRole("button", { name: "Agent taslağımı oluştur" }).click();
  await page.getByRole("link", { name: "Agentımı düzenle" }).click();
  await expect(page.getByLabel("Görevi", { exact: true })).toBeVisible();
  const agent = new URL(page.url()).pathname.split("/").pop()!;
  const session = await read(page, "auth/session");
  const scope = session.workspaces[0].id;
  const path = `workspaces/${scope}/agents/${agent}`;
  const identity = { scope, agent };
  expect(scope).not.toBe(fixture.scope);
  expect(
    await page.evaluate(
      async (scope) => (await fetch(`/v1/workspaces/${scope}/agents`)).status,
      fixture.scope,
    ),
  ).toBe(404);

  await page.getByRole("link", { name: "Bağlantılar", exact: true }).click();
  await page.getByLabel("Bağlantı adı", { exact: true }).fill("Journey Model");
  await page
    .getByLabel("API anahtarı")
    .fill("synthetic-journey-provider-key-never-used");
  await page.getByRole("button", { name: "Bağlantıyı kaydet" }).click();
  await expect(page.getByText("Journey Model", { exact: true })).toBeVisible();
  await expect(page.getByLabel("API anahtarı")).toHaveValue("");
  const connections = await read(
    page,
    `workspaces/${scope}/provider-connections`,
  );
  expect(JSON.stringify(connections)).not.toContain(
    "synthetic-journey-provider-key",
  );
  await page.getByLabel("Bağlantı türü").selectOption("telegram");
  await page
    .getByLabel("Bağlantı adı", { exact: true })
    .fill("Journey Telegram");
  await page.getByLabel("Telegram sohbet kimliği").fill("123456780");
  await page
    .getByLabel("Bot tokenı")
    .fill("123456780:synthetic_journey_never_sent_123456");
  await page.getByRole("button", { name: "Bağlantıyı kaydet" }).click();
  await expect(
    page.getByText("Journey Telegram", { exact: true }),
  ).toBeVisible();
  await page.goto(`/agentler/${agent}`);
  await page
    .getByLabel("Model bağlantısı")
    .selectOption({ label: "Journey Model" });
  await save(page);

  await page
    .getByRole("button", { name: "Sürümü yayınla", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toContainText(
    "yeni ses dosyalarının hazırlanması gerekiyor",
  );
  await expect(
    page.getByRole("button", { name: "Bu sürümü yayınla", exact: true }),
  ).toHaveCount(0);
  expect((await read(page, `${path}/releases`)).releases).toEqual([]);
  await page.getByRole("button", { name: "Düzenlemeye dön" }).click();
  await page.getByRole("button", { name: "Sesi hazırla", exact: true }).click();
  await expect(
    page.getByText("Hazırlık kuyruğunda", { exact: true }),
  ).toBeVisible();
  await operatorStep("audio", identity);
  await expect(page.getByText("Ses hazır", { exact: true })).toBeVisible({
    timeout: 15000,
  });
  await page.getByRole("button", { name: "Sesi dinle", exact: true }).click();
  await expect
    .poll(() =>
      page
        .getByLabel("Hazır agent sesi")
        .evaluate((a: HTMLAudioElement) => a.readyState),
    )
    .toBeGreaterThanOrEqual(2);

  await page.getByRole("tab", { name: "Çağrı sonrası", exact: true }).click();
  await page.getByRole("button", { name: "Telegram bildirimi ekle" }).click();
  await page
    .getByLabel("Telegram bağlantısı", { exact: true })
    .selectOption({ label: "Journey Telegram" });
  await save(page);
  expect((await read(page, `${path}/action-grants`)).grants).toEqual([]);
  await page
    .getByRole("button", { name: "Sürümü yayınla", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Bu sürümü yayınla", exact: true })
    .click();
  await expect(page.getByRole("dialog").locator(".notice.error")).toContainText(
    "yayın izni gerekiyor",
  );
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Close", exact: true })
    .click();
  expect((await read(page, `${path}/releases`)).releases).toEqual([]);
  await page.getByRole("button", { name: "Gönderim iznini incele" }).click();
  await expect(page.getByRole("dialog")).toContainText("123456780");
  await page
    .getByRole("button", { name: "Bu hedeflere gönderime izin ver" })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page
    .getByRole("button", { name: "Sürümü yayınla", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Bu sürümü yayınla", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Yeni sürüm yayınlandı" }),
  ).toBeVisible();
  const releases = await read(page, `${path}/releases`);
  expect(releases.releases).toHaveLength(1);
  const release = releases.current_release;
  expect((await read(page, `workspaces/${scope}/numbers`)).numbers).toEqual([]);

  await page.getByRole("link", { name: "Numaralar", exact: true }).click();
  await page.getByLabel("0850 numaran").fill("+908500000099");
  await page.getByRole("button", { name: "Numara ekle" }).click();
  await expect(
    page.getByRole("button", { name: "Agent bağla", exact: true }),
  ).toBeDisabled();
  const number = (await read(page, `workspaces/${scope}/numbers`)).numbers[0];
  const denied = await page.evaluate(
    async ({ scope, number, release, csrf }) => {
      const response = await fetch(
        `/v1/workspaces/${scope}/numbers/${number.id}/binding`,
        {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
            "If-Match": `"${number.version}"`,
          },
          body: JSON.stringify({ release_id: release }),
        },
      );
      return { status: response.status, body: await response.json() };
    },
    { scope, number, release, csrf: session.csrf_token },
  );
  expect(denied).toMatchObject({
    status: 409,
    body: { error: "number_not_verified" },
  });
  await operatorStep("verify", identity);
  await page.reload();
  await page.getByRole("button", { name: "Agent bağla", exact: true }).click();
  await page.getByLabel("Agent", { exact: true }).selectOption(agent);
  await page.getByLabel("Yayınlanmış sürüm").selectOption(release);
  await page.getByRole("button", { name: "Numarayı bu sürüme bağla" }).click();
  await expect(page.locator(".notice.error")).toContainText(
    "Ses sunucusu bu sürümü henüz hazır olarak doğrulamadı",
  );
  expect(
    (await read(page, `workspaces/${scope}/numbers`)).numbers[0].enabled,
  ).toBe(false);
  await operatorStep("ready", { ...identity, release });
  await page.getByRole("button", { name: "Numarayı bu sürüme bağla" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Numara eşlemesi güncellendi" }),
  ).toBeVisible();
  expect(
    (await read(page, `workspaces/${scope}/numbers`)).numbers[0],
  ).toMatchObject({ enabled: true, status: "verified", release_id: release });
  await operatorStep("pin", { ...identity, release });
  await page.goto(`/agentler/${agent}`);
  await page
    .getByLabel("Görevi", { exact: true })
    .fill("Sonraki sürüm için değiştirilen talimat.");
  await save(page);
  expect((await read(page, `${path}/releases`)).current_release).toBe(release);
  expect(
    (await read(page, `workspaces/${scope}/numbers`)).numbers[0].release_id,
  ).toBe(release);
  await page.getByRole("link", { name: "Numaralar", exact: true }).click();
  const stopButton = page.getByRole("button", {
    name: "Çağrı karşılamayı durdur",
    exact: true,
  });
  await stopButton.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText(
    "Devam eden görüşmeler ve geçmiş kayıtlar korunur",
  );
  await page.setViewportSize({ width: 390, height: 844 });
  expect(await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth)).toBe(
    true,
  );
  await page.screenshot({
    path: "/evidence/journey-stop-mobile.png",
    animations: "disabled",
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await dialog.getByRole("button", { name: "Vazgeç" }).click();
  expect(
    (await read(page, `workspaces/${scope}/numbers`)).numbers[0].enabled,
  ).toBe(true);
  await stopButton.click();
  // Concurrent binding changes the version after this confirmation was opened.
  const currentNumber = (await read(page, `workspaces/${scope}/numbers`))
    .numbers[0];
  const concurrent = await page.evaluate(
    async ({ scope, number, release, csrf }) =>
      (
        await fetch(`/v1/workspaces/${scope}/numbers/${number.id}/binding`, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
            "If-Match": `"${number.version}"`,
          },
          body: JSON.stringify({ release_id: release }),
        })
      ).status,
    { scope, number: currentNumber, release, csrf: session.csrf_token },
  );
  expect(concurrent).toBe(200);
  await dialog
    .getByRole("button", { name: "Bu numarada karşılamayı durdur" })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(page.locator(".notice.error")).toContainText(
    "başka bir yerde değişti",
  );
  expect(
    (await read(page, `workspaces/${scope}/numbers`)).numbers[0].enabled,
  ).toBe(true);
  let stops = 0;
  await page.route("**/numbers/*/deactivate", async (route) => {
    stops++;
    const result = await route.fetch();
    expect(result.status()).toBe(200);
    await route.abort("failed");
  });
  await stopButton.click();
  await dialog
    .getByRole("button", { name: "Bu numarada karşılamayı durdur" })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(stopButton).toHaveCount(0);
  expect(stops).toBe(1);
  expect(
    (await read(page, `workspaces/${scope}/numbers`)).numbers[0].enabled,
  ).toBe(false);
  await operatorStep("stopped", { ...identity, release });

  await page.getByRole("link", { name: "Bağlantılar", exact: true }).click();
  for (const [label, resource] of [
    ["Journey Model", "provider-connections"],
    ["Journey Telegram", "telegram-connections"],
  ]) {
    const closeButton = page.getByRole("button", {
      name: `${label} bağlantısını kapat`,
      exact: true,
    });
    await closeButton.click();
    await expect(dialog).toContainText(label);
    await expect(dialog).toContainText("Kapalı bağlantı yeniden açılamaz");
    await page.setViewportSize({ width: 390, height: 844 });
    expect(
      await dialog.evaluate((el) => el.scrollWidth <= el.clientWidth),
    ).toBe(true);
    await page.screenshot({
      path: `/evidence/journey-close-${resource}-mobile.png`,
      animations: "disabled",
    });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await dialog.getByRole("button", { name: "Vazgeç" }).click();
    expect(
      (await read(page, `workspaces/${scope}/${resource}`)).connections[0]
        .enabled,
    ).toBe(true);
    if (resource === "telegram-connections") {
      await page.route("**/telegram-connections/*/revoke", async (route) => {
        const response = await route.fetch();
        expect(response.status()).toBe(200);
        await route.abort("failed");
      });
    }
    await closeButton.click();
    await dialog
      .getByRole("button", { name: "Bu bağlantıyı kapat", exact: true })
      .click();
    await expect(dialog).toHaveCount(0);
    await expect(closeButton).toHaveCount(0);
    expect(
      (await read(page, `workspaces/${scope}/${resource}`)).connections[0]
        .enabled,
    ).toBe(false);
  }
  await page.setViewportSize({ width: 390, height: 844 });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
  expect(errors).toEqual([]);
  await page.screenshot({
    path: "/evidence/journey-connections-mobile.png",
    fullPage: true,
    animations: "disabled",
  });
});
