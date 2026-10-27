import { test, expect, type Page } from "@playwright/test";

// UI contracts only. The separate mcp.spec.ts exercises actual API/RLS on Linux.
const scope = "11111111-1111-4111-8111-111111111111";
const agent = "22222222-2222-4222-8222-222222222222";
const ref = "33333333-3333-4333-8333-333333333333";
const reviewId = "44444444-4444-4444-8444-444444444444";
const outputSchema = {
  type: "object",
  properties: { answer: { type: "string", maxLength: 100 } },
  required: ["answer"],
  additionalProperties: false,
};
const inputSchema = {
  type: "object",
  properties: {
    project: { type: "integer", minimum: 1 },
    query: { type: "string", maxLength: 100 },
    options: {
      type: "object",
      additionalProperties: false,
      properties: {
        active: { type: "boolean" },
        labels: {
          type: "array",
          maxItems: 2,
          items: { type: "string", maxLength: 20 },
        },
      },
      required: ["active"],
    },
  },
  required: ["project", "query"],
  additionalProperties: false,
};
const tool = {
  name: "search",
  description: '<img src=x onerror="alert(1)"> Read only',
  inputSchema,
  outputSchema,
  digest: "a".repeat(64),
};
async function mock(page: Page, role = "owner") {
  const state = {
    draft: {
      agent_name: "MCP Asistanı",
      owner_display_name: "Test",
      owner_address: "Test",
      owner_dative: "Test",
      owner_genitive: "Test",
      instructions: "Bilgi al.",
      role_description: "",
      tone_description: "",
      business_context: "",
      model: "model",
      voice: "ema-default",
      greeting_text: "Merhaba",
      tools: [] as { tool: string; alias: string; guidance: string }[],
      mcp_tools: [] as any[],
    },
    version: 1,
    grants: [] as any[],
    connections: [
      {
        id: ref,
        label: "Test MCP",
        enabled: true,
        endpoint: new URL('/mcp', new URL("https:" + "//" + 'mcp.example.test')).href,
        auth_type: "none",
      },
    ],
    discoveries: 0,
    discoveryStatus: "missing",
    loseGrant: false,
    staleGrant: false,
    posts: [] as string[],
  };
  await page.route("**/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    const method = request.method();
    const body = method === "GET" ? null : request.postDataJSON();
    if (method !== "GET") state.posts.push(path);
    const send = (json: unknown, status = 200) =>
      route.fulfill({ status, json });
    if (path === "/v1/auth/session")
      return send({
        user: { id: "u", display_name: "Test" },
        csrf_token: "synthetic",
        workspaces: [{ id: scope, name: "Test", role }],
      });
    if (
      path.endsWith("/provider-connections") ||
      path.endsWith("/telegram-connections")
    )
      return send({ connections: [] });
    if (path.endsWith("/mcp-connections")) {
      if (method !== "GET")
        state.connections.push({
          ...body,
          id: "new",
          enabled: true,
          token: undefined,
        });
      return send({ connections: state.connections });
    }
    if (path.endsWith("/discovery")) {
      if (method !== "GET") {
        state.discoveries++;
        state.discoveryStatus = "queued";
      }
      return send({
        status: state.discoveryStatus,
        failure_code: null,
        manifest: null,
      });
    }
    if (path.endsWith("/tools"))
      return send({
        tools: [
          { tool, review_id: reviewId },
          { tool: { ...tool, name: "unreviewed" }, review_id: null },
        ],
      });
    if (path.endsWith("/mcp-review"))
      return send({
        draft_version: state.version,
        review_digest: "d".repeat(64),
        review: {
          tools: state.draft.mcp_tools.map((b) => ({
            ...b,
            tool,
            endpoint: state.connections[0].endpoint,
            runtime_schema: {
              ...inputSchema,
              properties: Object.fromEntries(
                Object.entries(inputSchema.properties).filter(
                  ([k]) => !Object.hasOwn(b.fixed_arguments, k),
                ),
              ),
            },
          })),
        },
      });
    if (path.endsWith("/mcp-grants")) {
      if (method !== "GET") {
        if (state.staleGrant) return send({ error: "stale_mcp_review" }, 409);
        state.grants = [
          {
            id: "55555555-5555-4555-8555-555555555555",
            enabled: true,
            review_digest: "d".repeat(64),
          },
        ];
        if (state.loseGrant) return route.abort();
      }
      return send({ grants: state.grants });
    }
    if (path.includes("/mcp-grants/") && path.endsWith("/revoke")) {
      state.grants[0].enabled = false;
      return send({ status: "revoked" });
    }
    if (path.includes("/mcp-connections/") && path.endsWith("/revoke")) {
      state.connections[0].enabled = false;
      return send({ status: "revoked" });
    }
    if (path.endsWith(`/agents/${agent}`)) {
      if (method === "PUT") {
        if (request.headers()["if-match"] !== `"${state.version}"`)
          return send({ error: "stale_version" }, 412);
        state.draft = body;
        state.version++;
      }
      return send({ id: agent, version: state.version, content: state.draft });
    }
    if (path.endsWith("/releases"))
      return send({ version: 0, current_release: null, releases: [] });
    if (path.endsWith("/models"))
      return send({ models: [{ id: "model", name: "Test model" }] });
    if (path.endsWith("/numbers")) return send({ numbers: [] });
    if (path.endsWith("/voice-preparation"))
      return send({ status: "missing", attempt: 0 });
    if (path.endsWith("/agents"))
      return send({ agents: [{ id: agent, name: "MCP Asistanı" }] });
    return send({});
  });
  return state;
}
async function selectTool(page: Page) {
  await page.goto(`/agentler/${agent}`);
  await page.getByRole("tab", { name: "Araçlar", exact: true }).click();
  await page.getByLabel("MCP bağlantısı", { exact: true }).selectOption(ref);
  await page.getByLabel("MCP aracı", { exact: true }).selectOption(reviewId);
  await page
    .getByRole("button", { name: "MCP aracı ekle", exact: true })
    .click();
}
async function save(page: Page) {
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(
    page.getByRole("status").filter({ hasText: "Taslak kaydedildi" }),
  ).toBeVisible();
}

test("connection credentials are write-only; discovery and revocation need explicit review", async ({
  page,
}) => {
  const state = await mock(page);
  await page.goto("/baglantilar");
  const region = page.getByRole("region", { name: "MCP bağlantıları" });
  await page.getByLabel("MCP bağlantı adı").fill("Yeni MCP");
  await page
    .getByLabel("MCP sunucu adresi")
    .fill(new URL('/mcp', new URL("https:" + "//" + 'another.example.test')).href);
  await page.getByLabel("MCP kimlik doğrulama").selectOption("bearer");
  await page
    .getByLabel("MCP erişim anahtarı")
    .fill("synthetic-secret-never-sent");
  await page
    .getByRole("button", { name: "MCP bağlantısını kaydet", exact: true })
    .click();
  await expect(page.getByLabel("MCP erişim anahtarı")).toHaveValue("");
  expect(state.discoveries).toBe(0);
  const card = region.getByRole("article", { name: "Test MCP", exact: true });
  await card.getByRole("button", { name: "Araçları tara" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Vazgeç" })
    .click();
  expect(state.discoveries).toBe(0);
  await card.getByRole("button", { name: "Araçları tara" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Bu sunucuyu tara" })
    .click();
  await expect(card.getByRole("status")).toHaveText("Sırada");
  expect(state.discoveries).toBe(1);
  await card.getByRole("button", { name: "MCP bağlantısını kapat" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Bu MCP bağlantısını kapat" })
    .click();
  await expect(card.getByText("Kapalı", { exact: true })).toBeVisible();
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});

test("nested fixed parameters preserve types and metadata stays escaped", async ({
  page,
}) => {
  const state = await mock(page);
  await selectTool(page);
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByText(tool.description, { exact: true }),
  ).toBeVisible();
  await expect(dialog.locator("img")).toHaveCount(0);
  await dialog.getByLabel("project değerini sabitle").check();
  await dialog.getByLabel("project", { exact: true }).fill("7");
  await dialog.getByLabel("options değerini sabitle").check();
  await dialog
    .getByLabel("options · active", { exact: true })
    .selectOption("true");
  await dialog.getByLabel("labels alanını ekle").check();
  await dialog
    .getByRole("button", { name: "options · labels · Öğe ekle" })
    .click();
  await dialog
    .getByLabel("options · labels · 1", { exact: true })
    .fill("customer");
  await dialog.getByRole("button", { name: "Araç ayarlarını uygula" }).click();
  await save(page);
  expect(state.draft.mcp_tools[0].fixed_arguments).toEqual({
    project: 7,
    options: { active: true, labels: ["customer"] },
  });
  await page.getByRole("button", { name: "Araç iznini incele" }).click();
  await expect(
    dialog.getByText("Konuşmadan alınabilecek alanlar: query", { exact: true }),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Bu araçlara izin ver" }).click();
  await expect(
    page
      .getByRole("status")
      .filter({ hasText: "Seçili araçlara izin verildi" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Aracı kaldır", exact: true }).click();
  await save(page);
  await page.getByText("Verilmiş izinler (1)", { exact: true }).click();
  await page.getByRole("button", { name: /İzni kaldır ·/ }).click();
  await dialog.getByRole("button", { name: "Bu araç iznini kaldır" }).click();
  await expect(
    page.getByRole("status").filter({ hasText: "Araç izni kaldırıldı" }),
  ).toBeVisible();
  expect(state.grants[0].enabled).toBe(false);
});

for (const kind of ["stale", "lost"] as const)
  test(`${kind} consent response requires a fresh review`, async ({ page }) => {
    const state = await mock(page);
    await selectTool(page);
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Araç ayarlarını uygula" })
      .click();
    await save(page);
    await page.getByRole("button", { name: "Araç iznini incele" }).click();
    state.staleGrant = kind === "stale";
    state.loseGrant = kind === "lost";
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "Bu araçlara izin ver" })
      .click();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(
      page
        .getByRole("alert")
        .filter({ hasText: "Güncel durumu yeniden incele" }),
    ).toBeVisible();
    await page.getByRole("button", { name: "Araç iznini incele" }).click();
    if (kind === "lost") {
      await expect(
        page
          .getByRole("dialog")
          .getByText("Bu araçlara ve değerlere daha önce izin verildi."),
      ).toBeVisible();
      await expect(
        page.getByRole("button", { name: "Bu araçlara izin ver" }),
      ).toHaveCount(0);
    }
  });

test("editor can configure but cannot grant and viewer has no mutation controls", async ({
  page,
}) => {
  await mock(page, "editor");
  await selectTool(page);
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Araç ayarlarını uygula" })
    .click();
  await save(page);
  await page.getByRole("button", { name: "Araç iznini incele" }).click();
  await expect(
    page.getByRole("button", { name: "Bu araçlara izin ver" }),
  ).toHaveCount(0);
  await page.unroute("**/v1/**");
  await mock(page, "viewer");
  await page.goto("/baglantilar");
  await expect(
    page.getByRole("button", { name: "MCP bağlantısını kaydet" }),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Araçları tara" })).toHaveCount(
    0,
  );
});

test("MCP editor remains usable at mobile width", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await mock(page);
  await selectTool(page);
  await expect(page.getByRole("dialog")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: info.outputPath("mcp-mobile.png"),
    animations: "disabled",
  });
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Araç ayarlarını uygula" })
    .click();
  await expect(
    page.getByRole("article", { name: "MCP aracı 1" }),
  ).toBeVisible();
});

test("browser history retains unsaved tool edits and preserves the original version", async ({
  page,
}) => {
  const state = await mock(page);
  await page.goto("/agentler");
  await page.getByRole("link").filter({ hasText: "MCP Asistanı" }).click();
  await page.getByRole("tab", { name: "Araçlar", exact: true }).click();
  await page.getByLabel("Mesajı not al", { exact: true }).check();
  await page
    .getByLabel("Ne zaman kullanmalı?", { exact: true })
    .fill("Retained local tool guidance");
  await page.goBack();
  await expect(page).toHaveURL(/\/agentler$/);
  expect(
    await page.evaluate(
      () =>
        !window.dispatchEvent(new Event("beforeunload", { cancelable: true })),
    ),
  ).toBe(true);
  await page.goForward();
  await page.getByRole("tab", { name: "Araçlar", exact: true }).click();
  await expect(page.getByLabel("Mesajı not al", { exact: true })).toBeChecked();
  await expect(
    page.getByLabel("Ne zaman kullanmalı?", { exact: true }),
  ).toHaveValue("Retained local tool guidance");
  await save(page);
  expect(state.draft.tools).toEqual([
    {
      tool: "take_note",
      alias: "take_note",
      guidance: "Retained local tool guidance",
    },
  ]);
  expect(
    await page.evaluate(
      () =>
        !window.dispatchEvent(new Event("beforeunload", { cancelable: true })),
    ),
  ).toBe(false);
  await page
    .getByLabel("Ne zaman kullanmalı?", { exact: true })
    .fill("Conflicting local guidance");
  await page.goBack();
  await expect(page).toHaveURL(/\/agentler$/);
  state.version++;
  state.draft = structuredClone(state.draft);
  state.draft.tools[0].guidance = "Other editor guidance";
  await page.goForward();
  await page.getByRole("tab", { name: "Araçlar", exact: true }).click();
  await expect(
    page.getByLabel("Ne zaman kullanmalı?", { exact: true }),
  ).toHaveValue("Conflicting local guidance");
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "başka bir yerde değişti" }),
  ).toBeVisible();
  expect(state.draft.tools[0].guidance).toBe("Other editor guidance");
  expect(
    await page.evaluate(() => [localStorage.length, sessionStorage.length]),
  ).toEqual([0, 0]);
});

for (const raw of ["9007199254740993", "-9007199254740993", "9e20"])
  test(`MCP rejects unsafe number ${raw} without replacing the user's input`, async ({
    page,
  }) => {
    const state = await mock(page);
    await selectTool(page);
    await page.getByLabel("project değerini sabitle", { exact: true }).check();
    const input = page.getByLabel("project", { exact: true });
    await input.fill(raw);
    await expect(input).toHaveValue(raw);
    await expect(input).toHaveAttribute("aria-invalid", "true");
    await page
      .getByRole("button", { name: "Araç ayarlarını uygula", exact: true })
      .click();
    await expect(page.getByRole("dialog")).toBeVisible();
    expect(state.draft.mcp_tools).toEqual([]);
    await input.fill("9007199254740991");
    await expect(input).toHaveAttribute("aria-invalid", "false");
    await page
      .getByRole("button", { name: "Araç ayarlarını uygula", exact: true })
      .click();
    await save(page);
    expect(String(state.draft.mcp_tools[0].fixed_arguments.project)).toBe(
      "9007199254740991",
    );
  });

test("unsafe existing MCP parameters cannot be resaved with unrelated draft edits", async ({
  page,
}) => {
  const state = await mock(page);
  state.draft.mcp_tools = [
    {
      alias: "mcp_large",
      connection_id: ref,
      review_id: reviewId,
      guidance: "",
      fixed_arguments: { options: { large: 9007199254740992 } },
    },
  ];
  await page.goto(`/agentler/${agent}`);
  await page.getByLabel("Görevi", { exact: true }).fill("Changed instruction");
  await page
    .getByRole("button", { name: "Taslağı kaydet", exact: true })
    .click();
  await expect(
    page.getByRole("alert").filter({ hasText: "güvenli sayı sınırı" }),
  ).toBeVisible();
  expect(state.posts).toEqual([]);
});
