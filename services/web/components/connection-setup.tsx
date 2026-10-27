"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { Field, Loading, Notice } from "./shared";
import type { WorkspaceProps } from "./workspace";
type Setup = {
  kind: string;
  configuration: Record<string, string>;
  status: string;
  connection_id: string | null;
};
export function ConnectionSetup({
  scope,
  session,
  id,
}: WorkspaceProps & { id: string }) {
  const [setup, setSetup] = useState<Setup | null>(null);
  const [secret, setSecret] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const path = `workspaces/${scope}/connection-setups/${id}`;
  useEffect(() => {
    const controller = new AbortController();
    api<Setup>(path, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setSetup(data);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorMessage(e));
      });
    return () => controller.abort();
  }, [path]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      await api(`${path}/complete`, {
        body: { secret },
        csrf: session.csrf_token,
      });
      setSetup(await api<Setup>(path));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSecret("");
      setBusy(false);
      submitting.current = false;
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Bağlantıyı tamamla</h1>
          <p className="subtitle">
            Anahtarın sohbetle paylaşılmadan Alojan'da saklanır.
          </p>
        </div>
      </div>
      {error && <Notice error>{error}</Notice>}
      {!setup ? (
        !error && <Loading />
      ) : setup.status === "complete" ? (
        <Notice>
          Bağlantı hazır. Codex veya Claude konuşmana dönüp devam edebilirsin.
        </Notice>
      ) : setup.status === "expired" ? (
        <Notice error>
          Bu kurulumun süresi doldu. İstemciden yeni bir kurulum başlat.
        </Notice>
      ) : (
        <form onSubmit={submit} className="fields max-w-xl">
          <h2 className="section-title">{setup.configuration.label}</h2>
          <p>Tür: {setup.kind}</p>
          {setup.configuration.endpoint && (
            <p className="break-all">Adres: {setup.configuration.endpoint}</p>
          )}
          {setup.configuration.chat_id && (
            <p>Telegram hedefi: {setup.configuration.chat_id}</p>
          )}
          <Field
            label="Erişim anahtarı"
            type="password"
            autoComplete="off"
            value={secret}
            onChange={setSecret}
            required
            maxLength={4096}
            hint="Anahtarı yalnızca bu alana gir. Sohbete yapıştırma."
          />
          <Button type="submit" disabled={busy}>
            {busy ? "Kaydediliyor…" : "Bağlantıyı oluştur"}
          </Button>
          <p className="muted">
            Bağlantı oluşturmak agentına bu aracı çalıştırma izni vermez. Araç
            ve bildirim izinleri ayrıca yönetilir.
          </p>
        </form>
      )}
    </>
  );
}
