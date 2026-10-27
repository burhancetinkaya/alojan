"use client";
import { useEffect, useRef, useState } from "react";
import { api, errorMessage, type HTTPConnection } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Field, SelectField, Notice } from "./shared";

export function HTTPConnections({
  base,
  csrf,
  owner,
}: {
  base: string;
  csrf: string;
  owner: boolean;
}) {
  const [items, setItems] = useState<HTTPConnection[]>([]);
  const [label, setLabel] = useState("");
  const [endpoint, setEndpoint] = useState("");
  const [auth, setAuth] = useState("none");
  const [token, setToken] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [closing, setClosing] = useState<HTTPConnection | null>(null);
  const submitting = useRef(false);
  const path = `${base}/http-connections`;
  useEffect(() => {
    const c = new AbortController();
    api<{ connections: HTTPConnection[] }>(path, { signal: c.signal })
      .then((v) => {
        if (!c.signal.aborted) setItems(v.connections || []);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      });
    return () => c.abort();
  }, [path]);
  async function refresh() {
    setItems((await api<{ connections: HTTPConnection[] }>(path)).connections);
  }
  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      const created = await api<HTTPConnection>(path, {
        csrf,
        body: {
          label,
          endpoint,
          auth_type: auth,
          token: auth === "bearer" ? token : null,
        },
      });
      setItems((v) => [...v, created]);
      setLabel("");
      setEndpoint("");
    } catch (e) {
      setError(
        `${errorMessage(e)} Bağlantı listeni yenileyerek sonucu kontrol et.`,
      );
      setUncertain(true);
    } finally {
      setToken("");
      setBusy(false);
      submitting.current = false;
    }
  }
  async function revoke() {
    if (!closing || submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      await api(`${path}/${closing.id}/revoke`, { csrf, body: {} });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      try {
        await refresh();
      } catch (e) {
        setError(errorMessage(e));
      }
      setClosing(null);
      setBusy(false);
      submitting.current = false;
    }
  }
  return (
    <section className="mt-10" aria-label="HTTP bağlantıları">
      <h2 className="section-title">HTTP · Çağrı sonu hedefleri</h2>
      <p className="muted">
        Görüşme sonucunu kendi sistemine gönder. Bağlantı oluşturmak istek
        göndermez.
      </p>
      {error && <Notice error>{error}</Notice>}
      {!items.length && (
        <p className="muted mt-4">Henüz HTTP bağlantısı eklenmedi.</p>
      )}
      {items.map((item) => (
        <article key={item.id} className="form-panel fields">
          <strong>{item.label}</strong>
          <p className="text-sm break-all">{item.endpoint}</p>
          <p className="muted">
            {item.enabled ? "Açık" : "Kapalı"} ·{" "}
            {item.auth_type === "bearer"
              ? "Kayıtlı erişim anahtarı"
              : "Kimlik doğrulama yok"}
          </p>
          {owner && item.enabled && (
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setClosing(item)}
            >
              HTTP bağlantısını kapat
            </Button>
          )}
        </article>
      ))}
      {owner && (
        <form className="form-panel fields max-w-xl" onSubmit={save}>
          <h3 className="font-semibold">HTTP bağlantısı ekle</h3>
          <Field
            label="HTTP bağlantı adı"
            value={label}
            onChange={setLabel}
            required
            maxLength={80}
          />
          <Field
            label="HTTPS hedef adresi"
            value={endpoint}
            onChange={setEndpoint}
            required
            maxLength={2048}
            placeholder="https://crm.example.com/call-results"
            hint="Sabit adres. Sorgu parametrelerini agentın çağrı sonu ayarlarında seç."
          />
          <SelectField
            label="HTTP kimlik doğrulama"
            value={auth}
            onChange={(v) => {
              setAuth(v);
              setToken("");
            }}
          >
            <option value="none">Yok</option>
            <option value="bearer">Erişim anahtarı (Bearer)</option>
          </SelectField>
          {auth === "bearer" && (
            <Field
              label="HTTP erişim anahtarı"
              type="password"
              value={token}
              onChange={setToken}
              required
              maxLength={512}
              autoComplete="off"
              hint="Kaydedildikten sonra tekrar gösterilmez."
            />
          )}
          <Button type="submit" disabled={busy || uncertain}>
            HTTP bağlantısını kaydet
          </Button>
          {uncertain && (
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={() => {
                void refresh()
                  .then(() => setUncertain(false))
                  .catch((e) => setError(errorMessage(e)));
              }}
            >
              Bağlantı listesini yenile
            </Button>
          )}
        </form>
      )}
      <Dialog
        open={!!closing}
        onOpenChange={(v) => {
          if (!v && !busy) setClosing(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>HTTP bağlantısını kapat</DialogTitle>
            <DialogDescription>
              Bu hedefe bekleyen gönderimler durur. Başlamış istekler geri
              alınamaz. Yeniden kullanmak için yeni bağlantı ve gönderim izni
              gerekir.
            </DialogDescription>
          </DialogHeader>
          <strong>{closing?.label}</strong>
          <p className="break-all text-sm">{closing?.endpoint}</p>
          <Button disabled={busy} onClick={revoke}>
            Bu HTTP bağlantısını kapat
          </Button>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => setClosing(null)}
          >
            Vazgeç
          </Button>
        </DialogContent>
      </Dialog>
    </section>
  );
}
