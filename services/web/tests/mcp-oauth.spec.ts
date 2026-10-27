import { test, expect, type Page } from "@playwright/test";

// Synthetic OAuth peers: these browser contracts never contact a provider.
const scope = "11111111-1111-4111-8111-111111111111";
const state = `${scope}.22222222-2222-4222-8222-222222222222.${"s".repeat(43)}`;
const issuer = "https://auth.example.test";
const provider = {
  id: "synthetic",
  label: "Synthetic MCP",
  issuer,
  authorization_endpoint: `${issuer}/authorize`,
  resource: new URL('/tools', new URL("https:" + "//" + 'mcp.example.test')).href,
  scopes: ["records:read"],
};
async function mock(
  page: Page,
  options: { lost?: boolean; role?: string; badRedirect?: boolean } = {},
) {
  const posts: { path: string; body: unknown; csrf: string | undefined }[] = [];
  await page.route("https://auth.example.test/**", (route) =>
    route.fulfill({
      contentType: "text/html",
      body: "<h1>Synthetic provider</h1>",
    }),
  );
  await page.route("**/v1/**", async (route) => {
    const req = route.request(),
      path = new URL(req.url()).pathname;
    if (req.method() !== "GET")
      posts.push({
        path,
        body: req.postDataJSON(),
        csrf: req.headers()["x-csrf-token"],
      });
    if (path === "/v1/auth/session")
      return route.fulfill({
        json: {
          user: { id: "u", display_name: "Test" },
          csrf_token: "synthetic",
          workspaces: [
            { id: scope, name: "Test", role: options.role || "owner" },
          ],
        },
      });
    if (path.endsWith("/mcp-oauth/complete")) {
      if (options.lost) return route.abort("failed");
      return route.fulfill({ json: { connection_id: "connected" } });
    }
    if (path.endsWith("/mcp-oauth"))
      return route.fulfill({
        json:
          req.method() === "GET"
            ? { providers: [provider] }
            : {
                authorization_url: `${options.badRedirect ? "https://wrong.example.test" : issuer}/authorize?state=${state}`,
              },
      });
    if (path.endsWith("-connections"))
      return route.fulfill({ json: { connections: [] } });
    if (path.endsWith("/agents"))
      return route.fulfill({ json: { agents: [] } });
    return route.fulfill({ json: {} });
  });
  return posts;
}
const callback = () =>
  `/mcp-donus?${new URLSearchParams({ state, code: "synthetic-code", iss: issuer })}`;

test("OAuth review cancels without writes, then redirects only after explicit approval", async ({
  page,
}) => {
  const posts = await mock(page);
  await page.goto("/baglantilar");
  await page.getByLabel("OAuth sağlayıcısı").selectOption("synthetic");
  await page.getByLabel("OAuth bağlantı adı").fill("My account");
  await page
    .getByRole("button", { name: "Bağlantıyı incele", exact: true })
    .click();
  const dialog = page.getByRole("dialog");
  await expect(
    dialog.getByText(`İstenen erişimler: records:read`),
  ).toBeVisible();
  await dialog.getByRole("button", { name: "Vazgeç", exact: true }).click();
  expect(posts).toEqual([]);
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("button", { name: "Bağlantıyı incele", exact: true })
    .click();
  await expect(dialog).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await dialog
    .getByRole("button", { name: "Sağlayıcıya git ve bağla" })
    .click();
  await expect(
    page.getByRole("heading", { name: "Synthetic provider" }),
  ).toBeVisible();
  expect(posts).toEqual([
    {
      path: `/v1/workspaces/${scope}/mcp-oauth`,
      body: { provider_id: "synthetic", label: "My account" },
      csrf: "synthetic",
    },
  ]);
});

test("OAuth callback strips secrets from URL and completes once with session CSRF", async ({
  page,
}) => {
  const posts = await mock(page);
  const response = await page.goto(callback());
  expect(response?.headers()["referrer-policy"]).toBe("no-referrer");
  await expect(page.getByText(/Hesabın bağlandı/)).toBeVisible();
  expect(new URL(page.url()).search).toBe("");
  expect(posts).toEqual([
    {
      path: `/v1/workspaces/${scope}/mcp-oauth/complete`,
      body: { state, code: "synthetic-code", issuer },
      csrf: "synthetic",
    },
  ]);
  await page.reload();
  await expect(page.getByText(/Bağlantı tamamlanamadı/)).toBeVisible();
  expect(posts).toHaveLength(1);
});

test("OAuth malformed, denied and non-owner returns never exchange codes", async ({
  page,
}) => {
  const posts = await mock(page, { role: "viewer" });
  for (const path of [
    callback() + "&code=duplicate",
    callback().replace(/&iss=.*/, ""),
    callback() + "&error=access_denied",
    callback(),
  ]) {
    await page.goto(path);
    await expect(page.getByText(/Bağlantı tamamlanamadı/)).toBeVisible();
    expect(new URL(page.url()).search).toBe("");
  }
  expect(posts).toEqual([]);
});

test("Lost OAuth result tells the owner to check connections without automatic retry", async ({
  page,
}) => {
  const posts = await mock(page, { lost: true });
  await page.goto(callback());
  await expect(page.getByText(/Bağlantılarını kontrol et/)).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Bağlantılarıma dön" }),
  ).toHaveAttribute("href", "/baglantilar");
  expect(posts).toHaveLength(1);
  expect(new URL(page.url()).search).toBe("");
});

test("OAuth rejects an authorization destination outside the displayed provider", async ({
  page,
}) => {
  const posts = await mock(page, { badRedirect: true });
  await page.goto("/baglantilar");
  await page.getByLabel("OAuth sağlayıcısı").selectOption("synthetic");
  await page.getByLabel("OAuth bağlantı adı").fill("My account");
  await page
    .getByRole("button", { name: "Bağlantıyı incele", exact: true })
    .click();
  await page.getByRole("button", { name: "Sağlayıcıya git ve bağla" }).click();
  await expect(page.getByRole("dialog")).not.toBeVisible();
  expect(new URL(page.url()).pathname).toBe("/baglantilar");
  expect(posts).toHaveLength(1);
});
