"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { Notice, SelectField } from "./shared";

export function VoicePreview({
  path,
  version,
  dirty,
  csrf,
  editable,
  waiting = false,
}: {
  path: string;
  version: number;
  dirty: boolean;
  csrf: string;
  editable: boolean;
  waiting?: boolean;
}) {
  const [preparation, setPreparation] = useState<{
    status: string;
    attempt: number;
    failure_code: string | null;
  } | null>(null);
  const [preparing, setPreparing] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    if (dirty) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const state = await api<{
          status: string;
          attempt: number;
          failure_code: string | null;
        }>(`${path}/voice-preparation`, { version, signal: controller.signal });
        if (controller.signal.aborted) return;
        setPreparation(state);
        if (state.status === "queued" || state.status === "preparing")
          timer = setTimeout(poll, 5000);
      } catch (e) {
        if (!controller.signal.aborted) setError(errorMessage(e));
      }
    }
    poll();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [path, version, dirty, refresh]);
  async function prepare() {
    setPreparing(true);
    setError("");
    try {
      await api(`${path}/voice-preparation`, { body: {}, csrf, version });
      setRefresh((v) => v + 1);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setPreparing(false);
    }
  }
  const labels: Record<string, string> = {
    missing: "Ses hazırlığı bekleniyor",
    queued: "Hazırlık kuyruğunda",
    preparing: "Ses hazırlanıyor",
    ready: "Ses hazır",
    failed: "Ses hazırlanamadı",
  };
  const [clip, setClip] = useState("greeting");
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const current = useRef("");
  const request = useRef<AbortController | null>(null);
  useEffect(
    () => () => {
      request.current?.abort();
      if (current.current) URL.revokeObjectURL(current.current);
    },
    [],
  );
  async function load() {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError("");
    setUrl("");
    if (current.current) {
      URL.revokeObjectURL(current.current);
      current.current = "";
    }
    try {
      const blob = await api<Blob>(`${path}/voice-preview/${clip}`, {
        version,
        responseType: "blob",
        signal: controller.signal,
      });
      if (!controller.signal.aborted) {
        current.current = URL.createObjectURL(blob);
        setUrl(current.current);
      }
    } catch (e) {
      if (!controller.signal.aborted) setError(errorMessage(e));
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  return (
    <div className="fields mt-6">
      {preparation && <p aria-live="polite">{labels[preparation.status]}</p>}
      {editable &&
        preparation &&
        ["missing", "failed"].includes(preparation.status) && (
          <Button
            variant="outline"
            disabled={dirty || preparing || preparation.attempt >= 3}
            onClick={prepare}
          >
            {preparing
              ? "Kuyruğa ekleniyor…"
              : preparation.status === "failed"
                ? "Sesi yeniden hazırla"
                : "Sesi hazırla"}
          </Button>
        )}
      {preparation?.status === "failed" && (
        <Notice error>
          {preparation.attempt >= 3
            ? "Deneme sınırına ulaşıldı. Destek ekibinin kontrol etmesi gerekiyor."
            : "Ses hazırlanamadı. Metin uzunluğunu kontrol edip tekrar deneyebilirsin."}
        </Notice>
      )}
      <p className="muted">
        Ses hazırlığı devam eden çağrının bitmesini bekler. Hazırlık sırasında
        yeni çağrı kabulü kısa süreli durur.
      </p>
      <SelectField
        label="Dinlenecek ses"
        value={clip}
        disabled={dirty || busy}
        onChange={(v) => {
          setClip(v);
          setUrl("");
          setError("");
          if (current.current) {
            URL.revokeObjectURL(current.current);
            current.current = "";
          }
        }}
      >
        <option value="greeting">Karşılama</option>
        <option value="unavailable">Hizmet verilemediğinde</option>
        {waiting && <option value="waiting">Bekleme ifadesi</option>}
      </SelectField>
      <Button variant="outline" disabled={dirty || busy} onClick={load}>
        {busy ? "Ses yükleniyor…" : "Sesi dinle"}
      </Button>
      {url && (
        <audio
          className="w-full min-w-0"
          aria-label="Hazır agent sesi"
          controls
          preload="metadata"
          src={url}
          onError={() =>
            setError("Tarayıcı bu sesi oynatamadı. Yeniden yüklemeyi deneyin.")
          }
        />
      )}
      {error && <Notice error>{error}</Notice>}
      <p className="muted">
        Kaydedilmiş ayarlarınla eşleşen hazır ses çalınır. Yeni ses gerekiyorsa
        hazırlık tamamlanana kadar dinlenemez.
      </p>
    </div>
  );
}
