"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { api, ApiError, errorMessage } from "@/lib/api";
import { Field, Notice, SelectField } from "./shared";
import type { WorkspaceProps } from "./workspace";

const permissions: Record<string, string> = {
  "agents:read": "Agent ve numaraları görüntüle",
  "agents:write": "Agent oluştur, düzenle ve seslerini hazırla",
  "connections:read": "Bağlantıları ve araçları görüntüle",
  "connections:write": "Bağlantıları yönet ve araçları tara",
  "calls:read": "Aramaları, özetleri ve gönderimleri oku",
  "transcripts:read": "Konuşma dökümlerini oku",
  "releases:publish": "Agent yayınla ve sürümü geri al",
  "numbers:manage": "Numaraya agent bağla veya devre dışı bırak",
  "grants:manage": "Dış araç ve bildirim işlemlerine izin ver",
  "deliveries:retry": "Başarısız gönderimleri yeniden dene",
};
const read = ["agents:read", "connections:read", "calls:read"];
const edit = [...read, "agents:write", "connections:write"];
type Token = {
  id: string;
  name: string;
  permissions: string[];
  expires_at: string;
  revoked_at: string | null;
  last_used_at: string | null;
};

export function PersonalTokens({ session, scope, role }: WorkspaceProps) {
  const [tokens, setTokens] = useState<Token[]>([]);
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [days, setDays] = useState("30");
  const [selected, setSelected] = useState(read);
  const [secret, setSecret] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [client, setClient] = useState("codex");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const submitting = useRef(false);
  const path = `workspaces/${scope}/personal-tokens`;
  const allowed =
    role === "owner"
      ? Object.keys(permissions)
      : role === "editor"
        ? [...read, "agents:write", "transcripts:read"]
        : [...read, "transcripts:read"];
  async function refresh() {
    const data = await api<{ tokens: Token[]; mcp_url?: string }>(path);
    setTokens(data.tokens);
    setEndpoint(data.mcp_url || "");
  }
  useEffect(() => {
    const controller = new AbortController();
    api<{ tokens: Token[]; mcp_url?: string }>(path, {
      signal: controller.signal,
    })
      .then((data) => {
        if (!controller.signal.aborted) {
          setTokens(data.tokens);
          setEndpoint(data.mcp_url || "");
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorMessage(e));
      });
    return () => controller.abort();
  }, [path]);
  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (submitting.current || uncertain) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    setSecret("");
    setPassword("");
    try {
      const result = await api<{ token: string }>(path, {
        body: {
          name,
          permissions: selected,
          expires_in_days: Number(days),
          current_password: password,
        },
        csrf: session.csrf_token,
      });
      setSecret(result.token);
      setName("");
      setNotice(
        "Token yalnızca şimdi gösterilir. Güvenli bir yerde sakla; konuşmaya yapıştırma.",
      );
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
      // An interrupted response may already have created a credential.
      setUncertain(
        !(
          e instanceof ApiError &&
          e.status < 500 &&
          e.code !== "request_failed"
        ),
      );
    } finally {
      setPassword("");
      setBusy(false);
      submitting.current = false;
    }
  }
  async function revoke(token: Token) {
    if (!window.confirm(`“${token.name}” erişimini iptal etmek istiyor musun?`))
      return;
    setBusy(true);
    setError("");
    try {
      await api(`${path}/${token.id}/revoke`, {
        body: {},
        csrf: session.csrf_token,
      });
      setSecret("");
      await refresh();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function copy(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setNotice("Kopyalandı.");
    } catch {
      setError("Kopyalanamadı. Alanı seçerek elle kopyalayabilirsin.");
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>MCP erişimi</h1>
          <p className="subtitle">
            Codex veya Claude Code ile agentlarını yönet.
          </p>
        </div>
      </div>
      {error && <Notice error>{error}</Notice>}
      {notice && <Notice>{notice}</Notice>}
      {endpoint ? (
        <section className="fields max-w-2xl mb-8">
          <h2 className="section-title">Bağlantı bilgileri</h2>
          <p>
            Sunucu: <code>{endpoint}</code>
          </p>
          <SelectField
            label="Bağlanacağın uygulama"
            value={client}
            onChange={setClient}
          >
            <option value="codex">Codex</option>
            <option value="claude-code">Claude Code</option>
          </SelectField>
          <>
            <p>
              Tokenını uygulamanın çalıştığı ortamda ALOJAN_MCP_TOKEN adıyla
              sakla. Aşağıdaki ayar tokenın kendisini içermez.
            </p>
            <pre
              aria-label="İstemci bağlantı ayarı"
              className="overflow-x-auto whitespace-pre-wrap"
            >
              {client === "codex"
                ? `[mcp_servers.alojan]\nurl = "${endpoint}"\nbearer_token_env_var = "ALOJAN_MCP_TOKEN"`
                : JSON.stringify(
                    {
                      mcpServers: {
                        alojan: {
                          type: "http",
                          url: endpoint,
                          headers: {
                            Authorization: "Bearer ${ALOJAN_MCP_TOKEN}",
                          },
                        },
                      },
                    },
                    null,
                    2,
                  )}
            </pre>
            <p className="muted">
              {client === "codex"
                ? "Codex MCP ayarlarına ekle; değişkeni tanımladıktan sonra uygulamayı yeniden aç."
                : "Claude Code .mcp.json ayarına ekle; değişkeni tanımladıktan sonra Claude Code’u yeniden aç."}
            </p>
          </>
          <Button variant="outline" onClick={() => copy(endpoint)}>
            Sunucu adresini kopyala
          </Button>
        </section>
      ) : (
        <Notice>
          Sunucunun dış bağlantı adresi henüz yapılandırılmadı. Tokenlarını
          hazırlayabilirsin.
        </Notice>
      )}
      {secret && (
        <section className="fields max-w-2xl my-6">
          <label htmlFor="new-personal-token">
            Yeni token — bir kez gösterilir
          </label>
          <textarea
            id="new-personal-token"
            readOnly
            value={secret}
            rows={3}
            className="w-full font-mono"
          />
          <div className="flex gap-3">
            <Button onClick={() => copy(secret)}>Tokenı kopyala</Button>
            <Button variant="outline" onClick={() => setSecret("")}>
              Gizle
            </Button>
          </div>
        </section>
      )}
      <form className="fields max-w-2xl my-8" onSubmit={create}>
        <h2 className="section-title">Yeni erişim oluştur</h2>
        <Field
          label="Token adı"
          value={name}
          onChange={setName}
          required
          maxLength={80}
          placeholder="Kişisel Codex"
        />
        <SelectField
          label="Yetki seçimi"
          value=""
          onChange={(value) =>
            setSelected(
              value === "edit"
                ? edit.filter((p) => allowed.includes(p))
                : value === "manage"
                  ? Object.keys(permissions).filter(
                      (p) => p !== "transcripts:read" && p !== "grants:manage",
                    )
                  : read,
            )
          }
        >
          <option value="" disabled>
            Bir başlangıç seç
          </option>
          <option value="read">Sadece oku</option>
          {role !== "viewer" && <option value="edit">Agent düzenle</option>}
          {role === "owner" && <option value="manage">Yayınla ve yönet</option>}
        </SelectField>
        <fieldset className="fields">
          <legend>Bu tokenın izinleri</legend>
          {allowed.map((permission) => (
            <label key={permission} className="flex gap-3 items-start">
              <input
                type="checkbox"
                checked={selected.includes(permission)}
                onChange={(e) =>
                  setSelected((current) =>
                    e.target.checked
                      ? [...current, permission]
                      : current.filter((p) => p !== permission),
                  )
                }
              />
              {permissions[permission]}
            </label>
          ))}
        </fieldset>
        <p className="muted">
          Dış işlem izni, bağlı istemcinin senin adına araç ve bildirim izinleri
          oluşturabilmesini sağlar. Yalnızca güvendiğin istemciye ver.
        </p>
        <SelectField label="Geçerlilik" value={days} onChange={setDays}>
          <option value="7">7 gün</option>
          <option value="30">30 gün</option>
          <option value="90">90 gün</option>
        </SelectField>
        <Field
          label="Mevcut şifren"
          value={password}
          onChange={setPassword}
          type="password"
          autoComplete="current-password"
          required
          hint="Yeni erişim oluşturduğunu doğrulamak için."
        />
        <Button
          type="submit"
          disabled={busy || uncertain || selected.length === 0}
        >
          {busy ? "İşleniyor…" : "Token oluştur"}
        </Button>
        {uncertain && (
          <Notice>
            Yeni token oluşmuş olabilir. Listeyi kontrol et; erişim anahtarını
            alamadıysan kaydı iptal edip yeniden oluştur.{" "}
            <Button
              type="button"
              variant="outline"
              onClick={async () => {
                try {
                  await refresh();
                  setUncertain(false);
                  setError("");
                } catch (e) {
                  setError(errorMessage(e));
                }
              }}
            >
              Token listesini kontrol et
            </Button>
          </Notice>
        )}
      </form>
      <section className="fields">
        <h2 className="section-title">Erişimlerin</h2>
        {tokens.length === 0 ? (
          <p className="muted">Henüz token oluşturmadın.</p>
        ) : (
          tokens.map((token) => (
            <article key={token.id} className="border rounded-lg p-4">
              <div className="flex justify-between gap-4">
                <strong>{token.name}</strong>
                <Button
                  variant="outline"
                  disabled={busy || !!token.revoked_at}
                  onClick={() => revoke(token)}
                >
                  {token.revoked_at ? "İptal edildi" : "Erişimi iptal et"}
                </Button>
              </div>
              <p className="muted">
                Bitiş: {new Date(token.expires_at).toLocaleString("tr-TR")} ·
                Son kullanım:{" "}
                {token.last_used_at
                  ? new Date(token.last_used_at).toLocaleString("tr-TR")
                  : "Henüz kullanılmadı"}
              </p>
              <p className="muted">
                {token.permissions.map((p) => permissions[p] || p).join(" · ")}
              </p>
            </article>
          ))
        )}
      </section>
    </>
  );
}
