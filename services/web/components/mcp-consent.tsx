"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { api, ApiError, errorMessage } from "@/lib/api";
import type { MCPGrant, MCPReview } from "@/lib/mcp";
import { Notice } from "./shared";

export function MCPConsent({
  path,
  csrf,
  version,
  dirty,
  owner,
  selected,
  disabled,
}: {
  path: string;
  csrf: string;
  version: number;
  dirty: boolean;
  owner: boolean;
  selected: boolean;
  disabled: boolean;
}) {
  const [grants, setGrants] = useState<MCPGrant[]>([]);
  const [review, setReview] = useState<MCPReview | null>(null);
  const [revoking, setRevoking] = useState<MCPGrant | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [count, setCount] = useState(10);
  const submitting = useRef(false);
  useEffect(() => {
    setReview(null);
    setNotice("");
    const c = new AbortController();
    api<{ grants: MCPGrant[] }>(`${path}/mcp-grants`, { signal: c.signal })
      .then((v) => {
        if (!c.signal.aborted) setGrants(v.grants);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      });
    return () => c.abort();
  }, [path, version, dirty]);
  async function inspect() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const [r, g] = await Promise.all([
        api<MCPReview>(`${path}/mcp-review`),
        api<{ grants: MCPGrant[] }>(`${path}/mcp-grants`),
      ]);
      if (r.draft_version !== version) throw new ApiError(412, "stale_version");
      setReview(r);
      setGrants(g.grants);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function submit() {
    if ((!review && !revoking) || !owner || dirty || submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      if (revoking)
        await api(`${path}/mcp-grants/${revoking.id}/revoke`, {
          body: {},
          csrf,
        });
      else
        await api(`${path}/mcp-grants`, {
          body: {
            draft_version: review!.draft_version,
            review_digest: review!.review_digest,
          },
          csrf,
        });
      setNotice(
        revoking
          ? "Araç izni kaldırıldı. Bu izni kullanan sürümlerin yeni araç istekleri durdurulur; gönderilmiş istekler geri alınamaz."
          : "Seçili araçlara izin verildi. Kullanmak için sürümü yayınla ve hazır olduğunda numarana bağla.",
      );
    } catch (e) {
      setError(`${errorMessage(e)} Güncel durumu yeniden incele.`);
    } finally {
      setReview(null);
      setRevoking(null);
      try {
        setGrants(
          (await api<{ grants: MCPGrant[] }>(`${path}/mcp-grants`)).grants,
        );
      } catch (e) {
        setError(errorMessage(e));
      }
      setBusy(false);
      submitting.current = false;
    }
  }
  const current =
    review &&
    grants.some((g) => g.enabled && g.review_digest === review.review_digest);
  const enabled = grants.filter((g) => g.enabled);
  return (
    <section className="fields mt-6" aria-label="MCP araç izinleri">
      {error && <Notice error>{error}</Notice>}
      {notice && <Notice>{notice}</Notice>}
      {selected && (
        <Button
          type="button"
          variant="outline"
          disabled={disabled || busy || dirty}
          onClick={inspect}
        >
          Araç iznini incele
        </Button>
      )}
      {dirty && (
        <p className="muted">İzinleri incelemeden önce taslağı kaydet.</p>
      )}
      <p className="muted">
        Araç seçimi tek başına çalıştırma izni vermez. İzin, incelenen araçlara
        ve sabit değerlere özeldir.
      </p>
      {!!enabled.length && (
        <details>
          <summary className="text-link cursor-pointer">
            Verilmiş izinler ({enabled.length})
          </summary>
          <p className="muted mt-3">
            Eski yayınların izinleri taslaktan bağımsızdır. Kaldırmak bu izni
            kullanan sürümleri de etkiler.
          </p>
          {enabled.slice(0, count).map((g) => (
            <div
              className="flex items-center justify-between gap-3 py-3"
              key={g.id}
            >
              <span>İzin {g.id.slice(0, 8)}</span>
              {owner && (
                <Button
                  type="button"
                  variant="ghost"
                  disabled={disabled || busy || dirty}
                  onClick={() => {
                    setError("");
                    setRevoking(g);
                  }}
                >
                  İzni kaldır · {g.id.slice(0, 8)}
                </Button>
              )}
            </div>
          ))}
          {count < enabled.length && (
            <Button variant="outline" onClick={() => setCount((c) => c + 10)}>
              Diğer izinleri göster
            </Button>
          )}
        </details>
      )}
      <Dialog
        open={!!review || !!revoking}
        onOpenChange={(open) => {
          if (!open && !busy) {
            setReview(null);
            setRevoking(null);
          }
        }}
      >
        <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>
              {revoking ? "Araç iznini kaldır" : "MCP araç izni"}
            </DialogTitle>
            <DialogDescription>
              {revoking
                ? "Bu agentın seçilen izni kaldırılacak. Bu izne bağlı yayınlar yeni çağrı alamayabilir. Gönderilmiş bir istek geri alınamaz."
                : "Agent yalnızca aşağıdaki araçları kullanabilir. Konuşmadan alınan değişken bilgiler belirtilen sunucuya gönderilir. Sabit değerleri model değiştiremez. Bu izin henüz bir aracı çalıştırmaz."}
            </DialogDescription>
          </DialogHeader>
          {revoking && <p className="break-all">İzin {revoking.id}</p>}
          {review?.review.tools.map((t) => (
            <section className="fields border-b pb-5" key={t.alias}>
              <strong>
                {t.alias} · {t.tool.name}
              </strong>
              <p className="break-all text-sm">{t.endpoint}</p>
              <p className="text-sm whitespace-pre-wrap break-words">
                {t.tool.description}
              </p>
              {t.guidance && (
                <p className="text-sm whitespace-pre-wrap">
                  Kullanım talimatı: {t.guidance}
                </p>
              )}
              {t.schema_policy && (
                <p className="muted">
                  Yalnızca tanımlı alanlar kullanılır. Metinler en fazla 4096
                  karakter, listeler 100 öğedir; aracın daha küçük sınırları
                  korunur. Sabitlenmeyen isteğe bağlı alanları agent boş
                  bırakabilir; sunucu varsayılanları geçerli olabilir.
                </p>
              )}
              <div>
                <h3 className="font-medium">Sabit bilgiler</h3>
                {Object.entries(t.fixed_arguments).length ? (
                  <dl>
                    {Object.entries(t.fixed_arguments).map(([k, v]) => (
                      <div key={k} className="mt-2">
                        <dt>{k}</dt>
                        <dd className="text-sm whitespace-pre-wrap break-all">
                          {typeof v === "string" ? v : JSON.stringify(v)}
                        </dd>
                      </div>
                    ))}
                  </dl>
                ) : (
                  <p className="muted">Sabit değer yok.</p>
                )}
              </div>
              <p className="text-sm">
                Konuşmadan alınabilecek alanlar:{" "}
                {Object.keys(t.runtime_schema.properties || {}).join(", ") ||
                  "Yok"}
              </p>
              <p className="text-sm">
                Yanıtta kabul edilen alanlar:{" "}
                {Object.keys(
                  (t.output_schema ?? t.tool.outputSchema)?.properties || {},
                ).join(", ") || (t.schema_policy === "bounded.v2" && !t.output_schema ? "Sunucu çıktı alanlarını tanımlamıyor. Yanıt boyutu sınırlıdır; sonuç alanlarına bağlanamaz." : "Yok")}
              </p>
            </section>
          ))}
          {current && (
            <Notice>Bu araçlara ve değerlere daha önce izin verildi.</Notice>
          )}
          <div className="actions">
            {owner && (!current || revoking) && (
              <Button disabled={disabled || busy || dirty} onClick={submit}>
                {busy
                  ? "İşleniyor…"
                  : revoking
                    ? "Bu araç iznini kaldır"
                    : "Bu araçlara izin ver"}
              </Button>
            )}
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => {
                setReview(null);
                setRevoking(null);
              }}
            >
              Kapat
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
