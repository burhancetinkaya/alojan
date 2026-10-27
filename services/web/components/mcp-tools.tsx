"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { api, errorMessage } from "@/lib/api";
import {
  hasUnsafeNumber,
  initialValue,
  type Catalog,
  type MCPBinding,
  type MCPConnection,
  type MCPTool,
} from "@/lib/mcp";
import { Field, Notice, SelectField } from "./shared";
import { MCPValue } from "./mcp-parameters";
import { MCPConsent } from "./mcp-consent";

export function MCPTools({
  base,
  path,
  csrf,
  version,
  bindings,
  owner,
  editable,
  disabled,
  dirty,
  onChange,
}: {
  base: string;
  path: string;
  csrf: string;
  version: number;
  bindings: MCPBinding[];
  owner: boolean;
  editable: boolean;
  disabled: boolean;
  dirty: boolean;
  onChange: (bindings: MCPBinding[]) => void;
}) {
  const [connections, setConnections] = useState<MCPConnection[]>([]);
  const [connection, setConnection] = useState("");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [choice, setChoice] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<{
    binding: MCPBinding;
    tool: MCPTool;
    index: number;
  } | null>(null);
  const locked = disabled || busy || !editable;
  useEffect(() => {
    const c = new AbortController();
    api<{ connections: MCPConnection[] }>(`${base}/mcp-connections`, {
      signal: c.signal,
    })
      .then((v) => {
        if (!c.signal.aborted) setConnections(v.connections);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      });
    return () => c.abort();
  }, [base]);
  useEffect(() => {
    setCatalog(null);
    setChoice("");
    setError("");
    if (!connection) return;
    const c = new AbortController();
    setBusy(true);
    api<Catalog>(`${base}/mcp-connections/${connection}/tools`, {
      signal: c.signal,
    })
      .then((v) => {
        if (!c.signal.aborted) setCatalog(v);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      })
      .finally(() => {
        if (!c.signal.aborted) setBusy(false);
      });
    return () => c.abort();
  }, [base, connection]);
  function add() {
    const item = catalog?.tools.find((t) => t.review_id === choice);
    if (!item?.review_id || locked || bindings.length >= 8) return;
    let n = 1;
    while (bindings.some((t) => t.alias === `mcp_tool_${n}`)) n++;
    setEditing({
      binding: {
        alias: `mcp_tool_${n}`,
        connection_id: connection,
        review_id: item.review_id,
        guidance: "",
        fixed_arguments: {},
      },
      tool: {
        ...item.tool,
        inputSchema: item.input_schema ?? item.tool.inputSchema,
      },
      index: -1,
    });
  }
  async function edit(binding: MCPBinding, index: number) {
    setError("");
    setBusy(true);
    try {
      const current = await api<Catalog>(
        `${base}/mcp-connections/${binding.connection_id}/tools`,
      );
      const item = current.tools.find((t) => t.review_id === binding.review_id);
      if (!item) {
        setError(
          "Bu araç artık incelemeden geçmiş güncel listede yok. Eski seçimi kaldırıp yeni incelenen aracı seç.",
        );
        return;
      }
      setEditing({
        binding: structuredClone(binding),
        tool: {
          ...item.tool,
          inputSchema: item.input_schema ?? item.tool.inputSchema,
        },
        index,
      });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  function apply(e: React.FormEvent) {
    e.preventDefault();
    if (!editing || locked) return;
    if (!(e.currentTarget as HTMLFormElement).reportValidity()) return;
    if (hasUnsafeNumber(editing.binding.fixed_arguments)) {
      setError(
        "Sabit parametrelerde güvenli sayı sınırı aşılıyor. Tam sayı büyüklüğü 9007199254740991 değerini aşamaz.",
      );
      return;
    }
    if (
      bindings.some(
        (t, i) => i !== editing.index && t.alias === editing.binding.alias,
      )
    ) {
      setError("Her araç için farklı bir ad kullan.");
      return;
    }
    onChange(
      editing.index < 0
        ? [...bindings, editing.binding]
        : bindings.map((t, i) => (i === editing.index ? editing.binding : t)),
    );
    setEditing(null);
    setError("");
  }
  return (
    <section className="mt-8 fields" aria-label="MCP araçları">
      <h2 className="section-title mb-0">Dış kaynaklardan bilgi al</h2>
      <p className="muted">
        Bağlantındaki incelenmiş okuma araçlarını seç. Hangi durumda
        kullanacağını talimatlarında anlat.
      </p>
      {error && !editing && <Notice error>{error}</Notice>}
      {bindings.map((b, i) => (
        <article
          key={`${b.connection_id}:${i}`}
          className="form-panel fields"
          aria-label={`MCP aracı ${i + 1}`}
        >
          <strong>{b.alias}</strong>
          <p className="muted">
            {connections.find((c) => c.id === b.connection_id)?.label ||
              "Kayıtlı bağlantı"}{" "}
            · {Object.keys(b.fixed_arguments).length} sabit alan
          </p>
          {b.guidance && (
            <p className="text-sm whitespace-pre-wrap break-words">
              {b.guidance}
            </p>
          )}
          <div className="actions">
            <Button
              type="button"
              variant="outline"
              disabled={locked}
              onClick={() => edit(b, i)}
            >
              Aracı düzenle
            </Button>
            <Button
              type="button"
              variant="ghost"
              disabled={locked}
              onClick={() => onChange(bindings.filter((_, j) => i !== j))}
            >
              Aracı kaldır
            </Button>
          </div>
        </article>
      ))}
      {editable && (
        <div className="form-panel fields">
          <SelectField
            label="MCP bağlantısı"
            value={connection}
            disabled={disabled}
            onChange={(v) => {
              setBusy(false);
              setConnection(v);
            }}
          >
            <option value="">Bağlantı seç</option>
            {connections.map((c) => (
              <option key={c.id} value={c.id} disabled={!c.enabled}>
                {c.label}
                {c.enabled ? "" : " · Kapalı"}
              </option>
            ))}
          </SelectField>
          {catalog && (
            <>
              <SelectField
                label="MCP aracı"
                value={choice}
                onChange={setChoice}
                disabled={locked}
              >
                <option value="">Araç seç</option>
                {catalog.tools.map((t) => (
                  <option
                    key={t.tool.name}
                    value={t.review_id || `unreviewed:${t.tool.name}`}
                    disabled={!t.review_id}
                  >
                    {t.tool.name}
                    {t.review_id ? "" : " · İnceleme bekliyor"}
                  </option>
                ))}
              </SelectField>
              {!catalog.tools.length && (
                <p className="muted">Bu bağlantıda araç bulunamadı.</p>
              )}
              <p className="muted">
                Yalnızca Alojan tarafından incelenen araçlar seçilebilir.
              </p>
            </>
          )}
          <Button
            type="button"
            className="w-fit"
            disabled={locked || !choice || bindings.length >= 8}
            onClick={add}
          >
            MCP aracı ekle
          </Button>
          <p className="muted">
            {bindings.length} / 8 araç ·{" "}
            <Link href="/baglantilar" className="text-link">
              MCP bağlantılarını yönet
            </Link>
          </p>
        </div>
      )}
      <MCPConsent
        path={path}
        csrf={csrf}
        version={version}
        dirty={dirty}
        owner={owner}
        selected={bindings.length > 0}
        disabled={disabled || busy}
      />
      <Dialog
        open={!!editing}
        onOpenChange={(open) => {
          if (!open) {
            setEditing(null);
            setError("");
          }
        }}
      >
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>MCP aracını ayarla</DialogTitle>
            <DialogDescription>
              Sabitlediğin değerler her çağrıda aynı kalır. Diğer alanları agent
              konuşmaya göre doldurur. Buraya şifre veya erişim anahtarı yazma.
            </DialogDescription>
          </DialogHeader>
          {editing && (
            <form onSubmit={apply} className="fields">
              <fieldset className="fields" disabled={locked}>
                <strong>{editing.tool.name}</strong>
                <p className="text-sm whitespace-pre-wrap break-words">
                  {editing.tool.description}
                </p>
                {error && <Notice error>{error}</Notice>}
                <div className="field">
                  <label className="font-medium text-sm" htmlFor="mcp-alias">
                    Talimatlarda kullanılacak araç adı
                  </label>
                  <input
                    id="mcp-alias"
                    className="select"
                    required
                    pattern="mcp_[a-z][a-z0-9_]{0,35}"
                    maxLength={40}
                    value={editing.binding.alias}
                    onChange={(e) =>
                      setEditing({
                        ...editing,
                        binding: { ...editing.binding, alias: e.target.value },
                      })
                    }
                  />
                  <p className="muted">
                    mcp_ ile başlamalı; küçük harf, rakam ve alt çizgi kullan.
                  </p>
                </div>
                <Field
                  label="Bu araç ne zaman kullanılmalı?"
                  area
                  maxLength={1000}
                  value={editing.binding.guidance}
                  onChange={(v) =>
                    setEditing({
                      ...editing,
                      binding: { ...editing.binding, guidance: v },
                    })
                  }
                />
                <h3 className="font-semibold">Sabit parametreler</h3>
                {Object.entries(editing.tool.inputSchema.properties || {}).map(
                  ([key, schema]) => (
                    <div className="fields border-b pb-4" key={key}>
                      <label className="flex items-center gap-2">
                        <input
                          type="checkbox"
                          checked={Object.hasOwn(
                            editing.binding.fixed_arguments,
                            key,
                          )}
                          onChange={(e) => {
                            const fixed = {
                              ...editing.binding.fixed_arguments,
                            };
                            if (e.target.checked)
                              fixed[key] = initialValue(schema);
                            else delete fixed[key];
                            setEditing({
                              ...editing,
                              binding: {
                                ...editing.binding,
                                fixed_arguments: fixed,
                              },
                            });
                          }}
                        />
                        {key} değerini sabitle
                      </label>
                      {Object.hasOwn(editing.binding.fixed_arguments, key) ? (
                        <MCPValue
                          name={key}
                          schema={schema}
                          value={editing.binding.fixed_arguments[key]}
                          onChange={(v) =>
                            setEditing({
                              ...editing,
                              binding: {
                                ...editing.binding,
                                fixed_arguments: {
                                  ...editing.binding.fixed_arguments,
                                  [key]: v,
                                },
                              },
                            })
                          }
                        />
                      ) : (
                        <p className="muted">
                          Konuşmadan alınır
                          {editing.tool.inputSchema.required?.includes(key)
                            ? " · Zorunlu"
                            : " · İsteğe bağlı"}
                        </p>
                      )}
                    </div>
                  ),
                )}
                <div className="actions">
                  <Button type="submit">Araç ayarlarını uygula</Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setEditing(null);
                      setError("");
                    }}
                  >
                    Vazgeç
                  </Button>
                </div>
              </fieldset>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}
