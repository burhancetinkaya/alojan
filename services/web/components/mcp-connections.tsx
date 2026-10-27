"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { api, errorMessage } from "@/lib/api";
import type { MCPConnection } from "@/lib/mcp";
import { MCPOAuth } from "./mcp-oauth";
import { Field, Notice, SelectField } from "./shared";

type Discovery = {
  status: string;
  failure_code: string | null;
  manifest: { tools: { name: string }[] } | null;
};
const states: Record<string, string> = {
  missing: "Henüz taranmadı",
  queued: "Sırada",
  running: "Taranıyor",
  ready: "Araç listesi hazır",
  failed: "Tarama tamamlanamadı",
};
export function MCPConnections({
  base,
  csrf,
  owner,
}: {
  base: string;
  csrf: string;
  owner: boolean;
}) {
  const path = `${base}/mcp-connections`;
  const [connections, setConnections] = useState<MCPConnection[]>([]);
  const [label, setLabel] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [auth, setAuth] = useState("none");
  const [secret, setSecret] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const [statesById, setStates] = useState<Record<string, Discovery>>({});
  const [action, setAction] = useState<{
    connection: MCPConnection;
    kind: "discovery" | "revoke";
  } | null>(null);
  useEffect(() => {
    const c = new AbortController();
    api<{ connections: MCPConnection[] }>(path, { signal: c.signal })
      .then((v) => {
        if (!c.signal.aborted) setConnections(v.connections);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      });
    return () => c.abort();
  }, [path]);
  async function refresh(id: string) {
    setError("");
    setBusy(true);
    try {
      const state = await api<Discovery>(`${path}/${id}/discovery`);
      setStates((v) => ({ ...v, [id]: state }));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function add(e: React.FormEvent) {
    e.preventDefault();
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(path, {
        csrf,
        body: {
          label,
          endpoint,
          auth_type: auth,
          token: auth === "bearer" ? secret : null,
        },
      });
      setLabel("");
      setEndpoint("");
      setNotice(
        "MCP bağlantısı kaydedildi. Araç listesini istediğinde ayrıca tara.",
      );
    } catch (e) {
      setError(
        `${errorMessage(e)} Yeniden eklemeden önce bağlantı listesini kontrol et.`,
      );
    } finally {
      setSecret("");
      try {
        setConnections(
          (await api<{ connections: MCPConnection[] }>(path)).connections,
        );
      } catch (e) {
        setError(errorMessage(e));
      }
      setBusy(false);
      submitting.current = false;
    }
  }
  async function confirm() {
    if (!action || submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    const { connection, kind } = action;
    try {
      await api(`${path}/${connection.id}/${kind}`, { csrf, body: {} });
      setNotice(
        kind === "discovery"
          ? "Tarama istendi. Sonucu Durumu yenile ile kontrol edebilirsin."
          : "MCP bağlantısı kapatıldı. Bu bağlantıyı kullanan sürümler yeniden hazırlanmalı.",
      );
    } catch (e) {
      setError(
        `${errorMessage(e)} İşlemi tekrarlamadan önce güncel durumu kontrol et.`,
      );
    } finally {
      setAction(null);
      try {
        setConnections(
          (await api<{ connections: MCPConnection[] }>(path)).connections,
        );
        const status = await api<Discovery>(
          `${path}/${connection.id}/discovery`,
        );
        setStates((v) => ({ ...v, [connection.id]: status }));
      } catch (e) {
        setError(errorMessage(e));
      }
      setBusy(false);
      submitting.current = false;
    }
  }
  return (
    <section className="mt-10" aria-label="MCP bağlantıları">
      <h2 className="section-title">MCP · Bilgi kaynakları</h2>
      <p className="muted">
        Agentına başka sistemlerden bilgi okuma araçları ekle. Kaydetmek
        sunucuya istek göndermez.
      </p>
      {error && <Notice error>{error}</Notice>}
      {notice && <Notice>{notice}</Notice>}
      {!connections.length && (
        <p className="muted mt-4">Henüz MCP bağlantısı eklenmedi.</p>
      )}
      {connections.map((c) => (
        <article className="form-panel fields" key={c.id} aria-label={c.label}>
          <div className="flex justify-between gap-3">
            <strong>{c.label}</strong>
            <Badge variant="outline">{c.enabled ? "Açık" : "Kapalı"}</Badge>
          </div>
          <p className="break-all text-sm">{c.endpoint}</p>
          {c.auth_type === "oauth" && (
            <p className="muted">
              {c.auth_status === "reauth_required"
                ? "Hesap erişimi sona erdi. Yeni bir bağlantı oluşturup agentını güncelle."
                : "OAuth ile bağlı · Erişim arka planda yenilenir."}
            </p>
          )}
          {statesById[c.id] && (
            <p role="status">
              {states[statesById[c.id].status] || "Durum bekleniyor"}
              {statesById[c.id].manifest
                ? ` · ${statesById[c.id].manifest!.tools.length} araç`
                : ""}
            </p>
          )}
          {statesById[c.id]?.status === "failed" && (
            <p className="muted">
              Sunucuya erişim veya araç listesi doğrulanamadı. Adresi ve erişim
              iznini Alojan yöneticisiyle kontrol et.
            </p>
          )}
          <div className="actions">
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => refresh(c.id)}
            >
              Durumu yenile
            </Button>
            {owner && c.enabled && (
              <>
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() => {
                    setError("");
                    setAction({ connection: c, kind: "discovery" });
                  }}
                >
                  Araçları tara
                </Button>
                <Button
                  variant="ghost"
                  disabled={busy}
                  onClick={() => {
                    setError("");
                    setAction({ connection: c, kind: "revoke" });
                  }}
                >
                  MCP bağlantısını kapat
                </Button>
              </>
            )}
          </div>
        </article>
      ))}
      {owner && (
        <form onSubmit={add} className="form-panel fields max-w-xl">
          <h3 className="font-semibold">MCP bağlantısı ekle</h3>
          <fieldset disabled={busy} className="fields">
            <Field
              label="MCP bağlantı adı"
              value={label}
              onChange={setLabel}
              required
              maxLength={80}
            />
            <Field
              label="MCP sunucu adresi"
              value={endpoint}
              onChange={setEndpoint}
              type="url"
              required
              maxLength={2048}
              placeholder="MCP sunucusunun HTTPS adresi"
              hint="HTTPS adresi Alojan yöneticisi tarafından erişime açılmış olmalı."
            />
            <SelectField
              label="MCP kimlik doğrulama"
              value={auth}
              onChange={(v) => {
                setAuth(v);
                setSecret("");
              }}
            >
              <option value="none">Anahtar gerektirmiyor</option>
              <option value="bearer">Erişim anahtarı (Bearer)</option>
            </SelectField>
            {auth === "bearer" && (
              <Field
                label="MCP erişim anahtarı"
                value={secret}
                onChange={setSecret}
                type="password"
                minLength={16}
                maxLength={512}
                required
                autoComplete="off"
                hint="Kaydedildikten sonra tekrar gösterilmez."
              />
            )}
            <Button type="submit" className="w-fit">
              MCP bağlantısını kaydet
            </Button>
          </fieldset>
        </form>
      )}
      {owner && <MCPOAuth base={base} csrf={csrf} />}
      <Dialog
        open={!!action}
        onOpenChange={(open) => {
          if (!open && !busy) setAction(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {action?.kind === "discovery"
                ? "Araç listesini tara"
                : "MCP bağlantısını kapat"}
            </DialogTitle>
            <DialogDescription>
              {action?.kind === "discovery"
                ? "Bu sunucuya kayıtlı erişim bilgisiyle bağlanıp araç listesi istenecek. Araçlar çalıştırılmaz. Yeni liste, seçili araçlar değişmişse mevcut izinlerin kullanımını durdurabilir."
                : "Bu bağlantıyı kullanan agent sürümleri yeni çağrı alamayabilir. Başlamış istekler geri alınamaz. Yeniden kullanmak için yeni bir bağlantı gerekir."}
            </DialogDescription>
          </DialogHeader>
          <strong>{action?.connection.label}</strong>
          <p className="break-all text-sm">{action?.connection.endpoint}</p>
          <div className="actions">
            <Button onClick={confirm} disabled={busy}>
              {action?.kind === "discovery"
                ? "Bu sunucuyu tara"
                : "Bu MCP bağlantısını kapat"}
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setAction(null)}
            >
              Vazgeç
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
