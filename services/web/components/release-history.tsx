"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { api, errorMessage, type Releases } from "@/lib/api";
import { Notice } from "./shared";

export function ReleaseHistory({
  path,
  csrf,
  owner,
  dirty,
  disabled,
  onChanged,
}: {
  path: string;
  csrf: string;
  owner: boolean;
  dirty: boolean;
  disabled: boolean;
  onChanged: (releases: Releases) => void;
}) {
  const [open, setOpen] = useState(false);
  const [history, setHistory] = useState<Releases | null>(null);
  const [selected, setSelected] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [reload, setReload] = useState(0);
  const submitting = useRef(false);
  useEffect(() => {
    if (!open) return;
    const controller = new AbortController();
    setLoading(true);
    setHistory(null);
    setSelected("");
    setError("");
    setNotice("");
    setInvalid(false);
    api<Releases>(`${path}/releases`, { signal: controller.signal })
      .then((r) => {
        if (!controller.signal.aborted) setHistory(r);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorMessage(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [open, path, reload]);
  const source = history?.releases.find((r) => r.id === selected);
  async function restore() {
    if (
      submitting.current ||
      !source ||
      !history ||
      invalid ||
      dirty ||
      !owner ||
      source.id === history.current_release
    )
      return;
    submitting.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const result = await api<{
        id: string;
        revision: number;
        version: number;
        digest: string;
      }>(`${path}/rollback`, {
        body: { release_id: source.id },
        csrf,
        version: history.version,
      });
      const updated: Releases = {
        version: result.version,
        current_release: result.id,
        releases: [
          {
            id: result.id,
            revision: result.revision,
            digest: result.digest,
            rollback_of: source.id,
          },
          ...history.releases,
        ].slice(0, 100),
      };
      setHistory(updated);
      onChanged(updated);
      setSelected("");
      setNotice(
        `Sürüm ${source.revision}, yeni sürüm ${result.revision} olarak yayınlandı. Telefonda kullanmak için Numaralar ekranından bağlayabilirsin.`,
      );
    } catch (e) {
      setError(errorMessage(e));
      // A lost response may hide a completed publication. Never retry with a fresh version automatically.
      setInvalid(true);
      setSelected("");
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!submitting.current) setOpen(v);
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" disabled={disabled}>
          Sürüm geçmişi
        </Button>
      </DialogTrigger>
      <DialogContent
        className="w-[calc(100vw_-_2rem)] max-h-[90dvh] overflow-y-auto [overflow-wrap:anywhere]"
        showCloseButton={!busy}
      >
        <DialogHeader>
          <DialogTitle>Sürüm geçmişi</DialogTitle>
          <DialogDescription>
            Önceki bir sürümü yeni yayın olarak oluşturabilirsin. Taslağın,
            numara eşlemeleri ve devam eden görüşmeler değişmez.
          </DialogDescription>
        </DialogHeader>
        {loading && <p role="status">Sürümler yükleniyor…</p>}
        {error && <Notice error>{error}</Notice>}
        {notice && (
          <Notice>
            {notice}{" "}
            <Link className="text-link" href="/numaralar">
              Numaraları yönet
            </Link>
          </Notice>
        )}
        {invalid && (
          <Notice>
            İşlem tamamlanmış olabilir. Tekrar denemeden önce geçmişi yenile ve
            son yayını kontrol et.
          </Notice>
        )}
        {dirty && (
          <Notice>
            Geri dönüş için önce taslağındaki değişiklikleri kaydet.
          </Notice>
        )}
        {!owner && (
          <p className="muted">
            Geri dönüşü yalnızca çalışma alanı sahibi yapabilir.
          </p>
        )}
        {history && (
          <>
            <p className="muted">
              En son 100 sürüm gösterilir. “Son yayın”, telefonda kullanılan
              sürüm anlamına gelmez; numara eşlemesini Numaralar ekranında
              görebilirsin.
            </p>
            {history.releases.length === 0 ? (
              <p>Henüz yayınlanmış sürüm yok.</p>
            ) : (
              <ul
                className="max-h-64 overflow-y-auto divide-y border rounded-md"
                aria-label="Yayınlanmış sürümler"
              >
                {history.releases.map((r) => {
                  const previous = history.releases.find(
                    (p) => p.id === r.rollback_of,
                  );
                  return (
                    <li key={r.id} className="p-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-semibold">
                          Sürüm {r.revision}
                          {r.id === history.current_release
                            ? " · Son yayın"
                            : ""}
                        </span>
                        {owner && r.id !== history.current_release && (
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={busy || invalid || dirty}
                            onClick={() => {
                              setSelected(r.id);
                              setNotice("");
                            }}
                          >
                            Sürüm {r.revision} seç
                          </Button>
                        )}
                      </div>
                      {r.rollback_of && (
                        <p className="muted mt-1">
                          {previous
                            ? `Sürüm ${previous.revision} üzerinden geri dönüş`
                            : "Önceki bir sürüm üzerinden geri dönüş"}
                        </p>
                      )}
                      <details className="mt-1 text-sm">
                        <summary className="cursor-pointer muted">
                          Sürüm kimliği
                        </summary>
                        <p>{r.id}</p>
                        <p className="font-mono text-xs">{r.digest}</p>
                      </details>
                    </li>
                  );
                })}
              </ul>
            )}
          </>
        )}
        {source && (
          <section
            aria-label="Geri dönüş onayı"
            className="border rounded-md p-4 space-y-3"
          >
            <h3 className="font-semibold">
              Sürüm {source.revision} yeniden yayınlanacak
            </h3>
            <p className="text-sm">
              Bu sürümün kayıtlı talimatları, araçları, modeli ve sesi
              kullanılacak. Bağlantı ve gönderim izinleri yeniden kontrol
              edilir; kaldırılmış izinler geri açılmaz. Telefon eşlemesi ayrıca
              yapılır.
            </p>
            <Button disabled={busy || invalid || dirty} onClick={restore}>
              {busy ? "Yayınlanıyor…" : "Seçilen sürümü yeniden yayınla"}
            </Button>
          </section>
        )}
        <div className="flex justify-end gap-3">
          <Button
            variant="outline"
            disabled={busy || loading}
            onClick={() => setReload((r) => r + 1)}
          >
            Geçmişi yenile
          </Button>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => setOpen(false)}
          >
            Kapat
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
