import { test, expect } from "@playwright/test";

test("outbound form uses the selected release and shows scoped history", async ({
  page,
}) => {
  const scope = "57ad92e0-bb85-4335-8232-1232b541ab5a";
  const call = "3d13a837-73d4-43d9-a2b3-bcac8faab705";
  let submitted = false;
  const row = {
    id: call,
    agent_name: "Deneme",
    queued_at: new Date().toISOString(),
    status: "queued",
    destination: "***0000",
  };
  await page.route("**/v1/auth/session", (r) =>
    r.fulfill({
      json: {
        user: { display_name: "Test" },
        csrf_token: "test",
        workspaces: [{ id: scope, display_name: "Test", role: "owner" }],
      },
    }),
  );
  await page.route("**/outbound-calls/eligible", (r) =>
    r.fulfill({
      json: {
        agents: [
          {
            agent_id: scope,
            name: "Deneme",
            caller: "+908500000000",
            voice: "ema-default",
            settings: {
              enabled: true,
              ring_timeout_seconds: 30,
              post_playback_seconds: 2,
            },
          },
        ],
      },
    }),
  );
  await page.route("**/outbound-calls", async (r) => {
    if (r.request().method() === "POST") {
      expect(r.request().headers()["idempotency-key"]).toMatch(
        /^[\da-f-]{36}$/,
      );
      expect(r.request().postDataJSON()).toMatchObject({
        to: "05320000000",
        text: "Merhaba.",
        post_playback_seconds: 3,
      });
      submitted = true;
      await r.fulfill({ status: 202, json: { id: call, status: "queued" } });
    } else
      await r.fulfill({
        json: { calls: submitted ? [row] : [], next_cursor: null },
      });
  });
  await page.route("**/outbound-calls/" + call, (r) =>
    r.fulfill({
      json: {
        ...row,
        message: "Merhaba.",
        destination: "+905320000000",
        ring_timeout_seconds: 30,
        post_playback_seconds: 3,
      },
    }),
  );
  await page.goto("/outbound");
  await expect(page.getByLabel("Anons sonrası bekleme (sn)")).toHaveValue("2");
  await page.getByLabel("Aranacak telefon").fill("05320000000");
  await page.getByLabel("Okunacak metin").fill("Merhaba.");
  await page.getByLabel("Anons sonrası bekleme (sn)").fill("3");
  await page.getByRole("button", { name: "Aramayı başlat" }).click();
  await expect(page.getByRole("status")).toContainText(call);
  await expect(page.getByRole("button", { name: "***0000" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Arama detayı" }),
  ).toBeVisible();
});
