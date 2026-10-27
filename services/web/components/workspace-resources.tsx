"use client";
import { HTTPConnections } from "./http-connections";
import { useEffect, useRef, useState } from "react";
import { Phone, Plus, Unplug, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  api,
  errorMessage,
  maskNumber,
  type Phone as PhoneNumber,
  type Connection,
  type Releases,
} from "@/lib/api";
import { Field, SelectField, Loading, Notice } from "./shared";
import { MCPConnections } from "./mcp-connections";
import type { WorkspaceProps } from "./workspace";

type AgentOption = { id: string; name: string };
export function Numbers({ scope, session, role }: WorkspaceProps) {
  const base = `workspaces/${scope}`;
  const [numbers, setNumbers] = useState<PhoneNumber[]>([]);
  const [agents, setAgents] = useState<AgentOption[]>([]);
  const [releaseOptions, setReleaseOptions] = useState<
    { id: string; name: string }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [value, setValue] = useState("");
  const [target, setTarget] = useState("");
  const [release, setRelease] = useState("");
  const [agent, setAgent] = useState("");
  const [stopping, setStopping] = useState<PhoneNumber | null>(null);
  const submittingStop = useRef(false);
  useEffect(() => {
    const c = new AbortController();
    Promise.all([
      api<{ numbers: PhoneNumber[] }>(`${base}/numbers`, { signal: c.signal }),
      api<{ agents: AgentOption[] }>(`${base}/agents`, { signal: c.signal }),
    ])
      .then(([n, a]) => {
        setNumbers(n.numbers);
        setAgents(a.agents);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [base]);
  useEffect(() => {
    setRelease("");
    setReleaseOptions([]);
    if (!agent) return;
    const c = new AbortController();
    api<Releases>(`${base}/agents/${agent}/releases`, { signal: c.signal })
      .then((r) => {
        if (!c.signal.aborted)
          setReleaseOptions(
            r.releases.map((v) => ({
              id: v.id,
              name: `Sürüm ${v.revision}${v.id === r.current_release ? " · Son yayın" : ""}`,
            })),
          );
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      });
    return () => c.abort();
  }, [base, agent]);
  async function refresh() {
    setNumbers(
      (await api<{ numbers: PhoneNumber[] }>(`${base}/numbers`)).numbers,
    );
  }
  async function add(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(`${base}/numbers`, {
        body: { number: value.trim() },
        csrf: session.csrf_token,
      });
      setValue("");
      await refresh();
      setNotice(
        "Numara eklendi. Size ait olduğu doğrulandıktan sonra bir agent bağlayabilirsiniz.",
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function bind(e: React.FormEvent) {
    e.preventDefault();
    const number = numbers.find((n) => n.id === target);
    if (!number || !release) return;
    setBusy(true);
    setError("");
    try {
      await api(`${base}/numbers/${target}/binding`, {
        method: "PUT",
        body: { release_id: release },
        csrf: session.csrf_token,
        version: number.version,
      });
      await refresh();
      setTarget("");
      setNotice(
        "Numara eşlemesi güncellendi. Yeni aramalar seçtiğiniz sürüme yönlendirilecek.",
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function deactivate() {
    if (!stopping || submittingStop.current) return;
    submittingStop.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(`${base}/numbers/${stopping.id}/deactivate`, {
        body: {},
        csrf: session.csrf_token,
        version: stopping.version,
      });
      setNotice(
        "Bu numarada yeni çağrı karşılanması durduruldu. Yeniden başlatmak için hazır bir sürüm bağlayabilirsin.",
      );
    } catch (e) {
      setError(
        `${errorMessage(e)} Güncel durumu kontrol edip gerekirse yeniden incele.`,
      );
    } finally {
      // Close stale or uncertain reviews; never reuse a captured number version.
      setStopping(null);
      setTarget("");
      try {
        await refresh();
      } catch (e) {
        setError(errorMessage(e));
      }
      submittingStop.current = false;
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Numaraların</h1>
          <p className="subtitle">Her numara, doğru agente bağlansın.</p>
        </div>
      </div>
      {error && <Notice error>{error}</Notice>}
      {notice && <Notice>{notice}</Notice>}
      {loading ? (
        <Loading />
      ) : numbers.length ? (
        <div>
          {numbers.map((n) => (
            <div className="list-item" key={n.id}>
              <div className="agent-identity">
                <span className="avatar">
                  <Phone size={21} />
                </span>
                <div>
                  <strong>{maskNumber(n.number)}</strong>
                  <div className="muted">
                    {n.status === "verified"
                      ? "Sahiplik doğrulandı"
                      : "Sahiplik doğrulaması bekleniyor"}
                  </div>
                </div>
              </div>
              <div className="actions">
                <Badge variant="outline">
                  {n.enabled ? "Bağlı" : "Bağlı değil"}
                </Badge>
                {role === "owner" && (
                  <Button
                    variant="outline"
                    disabled={busy || n.status !== "verified"}
                    onClick={() => {
                      setTarget(n.id);
                      setAgent("");
                      setRelease("");
                    }}
                  >
                    Agent bağla
                  </Button>
                )}
                {role === "owner" && n.enabled && (
                  <Button
                    variant="outline"
                    disabled={busy}
                    onClick={() => {
                      setStopping(n);
                      setError("");
                    }}
                  >
                    Çağrı karşılamayı durdur
                  </Button>
                )}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty">
          <Phone size={30} />
          <h2 className="text-xl mb-2">İlk numaranı ekle</h2>
          <p className="muted">
            Sana ait 0850 numarasını bir agente bağlayabilirsin.
          </p>
        </div>
      )}
      {target && (
        <form className="form-panel fields max-w-xl" onSubmit={bind}>
          <h2 className="section-title">
            {maskNumber(numbers.find((n) => n.id === target)!.number)} · Agent
            seç
          </h2>
          <SelectField label="Agent" value={agent} onChange={setAgent}>
            <option value="">Agent seç</option>
            {agents.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </SelectField>
          <SelectField
            label="Yayınlanmış sürüm"
            value={release}
            onChange={setRelease}
          >
            <option value="">Sürüm seç</option>
            {releaseOptions.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}
              </option>
            ))}
          </SelectField>
          <p className="muted">
            Bu işlem sonraki aramaların agentini değiştirir. Yalnızca hazır
            sürümler bağlanabilir.
          </p>
          <div className="actions">
            <Button type="submit" disabled={busy || !release}>
              Numarayı bu sürüme bağla
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => setTarget("")}
            >
              Vazgeç
            </Button>
          </div>
        </form>
      )}
      {role === "owner" && (
        <form className="form-panel fields max-w-xl" onSubmit={add}>
          <h2 className="section-title mb-0">Yeni numara</h2>
          <Field
            label="0850 numaran"
            value={value}
            onChange={setValue}
            type="tel"
            required
            maxLength={13}
            placeholder="+90850…"
            hint="Numarayı eklemek tek başına çağrı yönlendirmesini açmaz."
          />
          <Button className="w-fit" type="submit" disabled={busy}>
            <Plus size={16} />
            Numara ekle
          </Button>
        </form>
      )}
      <Dialog
        open={!!stopping}
        onOpenChange={(open) => {
          if (!open && !busy) setStopping(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Çağrı karşılamayı durdur</DialogTitle>
            <DialogDescription>
              {stopping && maskNumber(stopping.number)} numarasına gelen yeni
              aramalar agentına yönlendirilmeyecek. Devam eden görüşmeler ve
              geçmiş kayıtlar korunur. Yeniden başlatmak için hazır bir sürümü
              numaraya bağlayabilirsin.
            </DialogDescription>
          </DialogHeader>
          <div className="actions">
            <Button disabled={busy} onClick={deactivate}>
              {busy ? "Durduruluyor…" : "Bu numarada karşılamayı durdur"}
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setStopping(null)}
            >
              Vazgeç
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

export function Connections({ scope, session, role }: WorkspaceProps) {
  const base = `workspaces/${scope}`;
  const [providers, setProviders] = useState<Connection[]>([]);
  const [telegram, setTelegram] = useState<Connection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [kind, setKind] = useState("provider");
  const [label, setLabel] = useState("");
  const [secret, setSecret] = useState("");
  const [chat, setChat] = useState("");
  const [closing, setClosing] = useState<Connection | null>(null);
  const submittingClose = useRef(false);
  useEffect(() => {
    const c = new AbortController();
    Promise.all([
      api<{ connections: Connection[] }>(`${base}/provider-connections`, {
        signal: c.signal,
      }),
      api<{ connections: Connection[] }>(`${base}/telegram-connections`, {
        signal: c.signal,
      }),
    ])
      .then(([p, t]) => {
        setProviders(p.connections);
        setTelegram(t.connections);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [base]);
  async function add(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const resource =
        kind === "provider" ? "provider-connections" : "telegram-connections";
      const c = await api<Connection>(`${base}/${resource}`, {
        csrf: session.csrf_token,
        body:
          kind === "provider"
            ? { provider: "openrouter", label, api_key: secret }
            : { label, chat_id: chat, bot_token: secret },
      });
      if (kind === "provider") setProviders((p) => [...p, c]);
      else setTelegram((t) => [...t, c]);
      setSecret("");
      setLabel("");
      setChat("");
      setNotice("Bağlantı kaydedildi. Agent ayarlarından seçebilirsin.");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function revoke() {
    if (!closing || submittingClose.current) return;
    submittingClose.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    const resource = closing.provider
      ? "provider-connections"
      : "telegram-connections";
    try {
      await api(`${base}/${resource}/${closing.id}/revoke`, {
        body: {},
        csrf: session.csrf_token,
      });
      setNotice(
        "Bağlantı kapatıldı. Yeniden kullanmak için yeni bir bağlantı oluşturup agent ayarlarından seçebilirsin.",
      );
    } catch (e) {
      setError(
        `${errorMessage(e)} Güncel durumu kontrol edip gerekirse yeniden incele.`,
      );
    } finally {
      try {
        const current = await api<{ connections: Connection[] }>(
          `${base}/${resource}`,
        );
        if (closing.provider) setProviders(current.connections);
        else setTelegram(current.connections);
      } catch (e) {
        setError(errorMessage(e));
      }
      setClosing(null);
      submittingClose.current = false;
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Bağlantıların</h1>
          <p className="subtitle">Agentlerinin dünyayla bağlantısı.</p>
        </div>
      </div>
      {error && <Notice error>{error}</Notice>}
      {notice && <Notice>{notice}</Notice>}
      {loading ? (
        <Loading />
      ) : (
        <>
          <h2 className="section-title">Model bağlantıları</h2>
          {providers.length ? (
            providers.map((c) => (
              <ConnectionRow
                key={c.id}
                item={c}
                onClose={
                  role === "owner"
                    ? () => {
                        setClosing(c);
                        setError("");
                      }
                    : undefined
                }
                busy={busy}
              />
            ))
          ) : (
            <p className="muted">Henüz model bağlantısı eklenmedi.</p>
          )}
          <h2 className="section-title mt-9">Telegram</h2>
          {telegram.length ? (
            telegram.map((c) => (
              <ConnectionRow
                key={c.id}
                item={c}
                onClose={
                  role === "owner"
                    ? () => {
                        setClosing(c);
                        setError("");
                      }
                    : undefined
                }
                busy={busy}
              />
            ))
          ) : (
            <p className="muted">Henüz Telegram bağlantısı eklenmedi.</p>
          )}
        </>
      )}
      {role === "owner" && (
        <form onSubmit={add} className="form-panel fields max-w-xl">
          <h2 className="section-title mb-0">Bağlantı ekle</h2>
          <SelectField
            label="Bağlantı türü"
            value={kind}
            onChange={(v) => {
              setKind(v);
              setSecret("");
              setChat("");
            }}
          >
            <option value="provider">OpenRouter · Model</option>
            <option value="telegram">Telegram · Bildirim</option>
          </SelectField>
          <Field
            label="Bağlantı adı"
            value={label}
            onChange={setLabel}
            required
            maxLength={80}
            placeholder="Örneğin, Kişisel Telegram"
          />
          {kind === "telegram" && (
            <Field
              label="Telegram sohbet kimliği"
              value={chat}
              onChange={setChat}
              required
              maxLength={17}
            />
          )}
          <Field
            label={kind === "provider" ? "API anahtarı" : "Bot tokenı"}
            value={secret}
            onChange={setSecret}
            type="password"
            required
            autoComplete="off"
            hint="Gizli bilgi kaydedildikten sonra tekrar gösterilmez."
          />
          <p className="muted">Bağlantıyı kaydetmek mesaj göndermez.</p>
          <Button className="w-fit" disabled={busy} type="submit">
            <Plus size={16} />
            {busy ? "Kaydediliyor…" : "Bağlantıyı kaydet"}
          </Button>
        </form>
      )}
      <HTTPConnections
        base={base}
        csrf={session.csrf_token}
        owner={role === "owner"}
      />
      <MCPConnections
        base={base}
        csrf={session.csrf_token}
        owner={role === "owner"}
      />
      <Dialog
        open={!!closing}
        onOpenChange={(open) => {
          if (!open && !busy) setClosing(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Bağlantıyı kapat</DialogTitle>
            <DialogDescription>
              Bu bağlantıyı kullanan agentlar ve bekleyen işlemler
              etkilenebilir. Başlamış işlemler tamamlanabilir. Kapalı bağlantı
              yeniden açılamaz; yeni bağlantı oluşturup ilgili agent ayarlarını
              güncellemen gerekir.
            </DialogDescription>
          </DialogHeader>
          <div>
            <strong>{closing?.label}</strong>
            <p className="muted">
              {closing?.provider
                ? "OpenRouter · Model"
                : `Telegram · Hedef ${closing?.chat_id}`}
            </p>
          </div>
          <div className="actions">
            <Button disabled={busy} onClick={revoke}>
              {busy ? "Kapatılıyor…" : "Bu bağlantıyı kapat"}
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setClosing(null)}
            >
              Vazgeç
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
function ConnectionRow({
  item,
  onClose,
  busy,
}: {
  item: Connection;
  onClose?: () => void;
  busy: boolean;
}) {
  return (
    <div className="list-item">
      <div className="agent-identity">
        <span className="avatar">
          {item.provider ? <Unplug size={20} /> : <Send size={20} />}
        </span>
        <div>
          <strong>{item.label}</strong>
          <div className="muted">
            {item.provider ? "OpenRouter" : "Telegram"}
          </div>
        </div>
      </div>
      <div className="actions">
        <Badge variant="outline">{item.enabled ? "Hazır" : "Devre dışı"}</Badge>
        {onClose && item.enabled && (
          <Button
            variant="outline"
            disabled={busy}
            onClick={onClose}
            aria-label={`${item.label} bağlantısını kapat`}
          >
            Bağlantıyı kapat
          </Button>
        )}
      </div>
    </div>
  );
}
