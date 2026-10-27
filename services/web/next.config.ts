import type { NextConfig } from "next";

const backend = process.env.ALOJAN_MANAGEMENT_URL || "http://127.0.0.1:18081";
const address = new URL(backend);
if (
  !["http:", "https:"].includes(address.protocol) ||
  address.username ||
  address.password ||
  address.search ||
  address.hash ||
  address.pathname !== "/"
) {
  throw new Error(
    "Configure a management service origin without credentials or a path",
  );
}

const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  experimental: { cpus: 2 },
  async rewrites() {
    return [
      { source: "/v1/:path*", destination: `${address.origin}/v1/:path*` },
    ];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Cache-Control", value: "no-store" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "same-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
          {
            key: "Content-Security-Policy",
            value:
              "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; media-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'",
          },
        ],
      },
      {
        source: "/mcp-donus",
        headers: [{ key: "Referrer-Policy", value: "no-referrer" }],
      },
    ];
  },
};
export default config;
