"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { Loading, Notice, SelectField } from "./shared";

type Metric = {
  samples: number;
  missing: number;
  p50_ms: number | null;
  p95_ms: number | null;
  max_ms: number | null;
};
type Report = {
  calls_considered: number;
  call_limit: number;
  has_older_calls: boolean;
  sample_limit: number;
  truncated: boolean;
  observed_turns: number;
  eligible_turns: number;
  excluded_turns: number;
  latest_import_at: string | null;
  metrics: Record<string, Metric>;
};
const labels: Record<string, string> = {
  vad_end_to_audio_estimate_ms: "Konuşma sonundan yanıta (tahmin)",
  endpoint_to_audio_ms: "Konuşma bitişi kararından yanıta",
  endpoint_silence_audio_ms: "Bitiş kararındaki sessizlik",
  asr_finalize_ms: "Konuşmayı metne çevirme",
  agent_first_phrase_ms: "Agent'ın ilk yanıtı",
  tts_first_chunk_ms: "İlk sesin üretilmesi",
  pcm_to_output_ms: "Hazır sesin çıkışa aktarılması",
};
function ms(value: number | null) {
  return value === null
    ? "—"
    : `${new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 }).format(value)} ms`;
}
export function Performance({ scope, call }: { scope: string; call?: string }) {
  const [agent, setAgent] = useState("");
  const [agents, setAgents] = useState<{ id: string; name: string }[]>([]);
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  const [open, setOpen] = useState(!call);
  useEffect(() => {
    if (call) return;
    const c = new AbortController();
    api<{ agents: { id: string; name: string }[] }>(
      `workspaces/${scope}/agents`,
      { signal: c.signal },
    )
      .then((r) => {
        if (!c.signal.aborted) setAgents(r.agents);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      });
    return () => c.abort();
  }, [scope, call]);
  useEffect(() => {
    if (!open) return;
    const c = new AbortController();
    setLoading(true);
    setError("");
    setReport(null);
    const query = new URLSearchParams();
    if (agent) query.set("agent", agent);
    if (call) query.set("call", call);
    api<Report>(`workspaces/${scope}/performance?${query}`, {
      signal: c.signal,
    })
      .then((r) => {
        if (!c.signal.aborted) setReport(r);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [scope, agent, call, refresh, open]);
  return (
    <section
      aria-label="Yanıt performansı"
      className={call ? "form-panel" : ""}
    >
      <div className="page-heading">
        <div>
          {call ? (
            <h2 className="section-title">Yanıt süreleri</h2>
          ) : (
            <h1>Performans</h1>
          )}
          <p className="subtitle">Sunucunun yanıt üretme süreleri.</p>
        </div>
        <Button
          variant="outline"
          disabled={open && loading}
          onClick={() => {
            setOpen(true);
            setRefresh((r) => r + 1);
          }}
        >
          {open ? "Ölçümleri yenile" : "Ölçümleri göster"}
        </Button>
      </div>
      {open && (
        <>
          {!call && (
            <SelectField
              label="Agent filtresi"
              value={agent}
              onChange={setAgent}
            >
              <option value="">Tüm agentler</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </SelectField>
          )}
          <p className="muted my-4">
            Bu ölçümler telefonun sesi duyduğu anı göstermez. Şebeke ve cihaz
            gecikmesi dahil değildir. Veriler arka planda aktarılır; eksik ölçüm
            sıfır kabul edilmez.
          </p>
          {error && <Notice error>{error}</Notice>}
          {loading && <Loading />}
          {report && (
            <>
              <p className="muted mb-4">
                {report.calls_considered} çağrı · {report.observed_turns}{" "}
                kayıtlı konuşma turu · {report.excluded_turns} başarısız,
                kesilmiş veya hatırlatma turu hesaplama dışında.
              </p>
              {!call && (
                <p className="muted mb-4">
                  Seçilen agentlerin en son {report.call_limit} çağrısı
                  incelenir.{" "}
                  {report.has_older_calls
                    ? "Daha eski çağrılar bu görünüme dahil değil."
                    : ""}
                </p>
              )}
              {report.truncated && (
                <Notice>
                  Görünüm {report.sample_limit} konuşma turuyla sınırlı. Daha
                  dar bir agent filtresi veya tek çağrı seçebilirsin.
                </Notice>
              )}
              {report.observed_turns === 0 ? (
                <Notice>
                  Henüz aktarılmış yanıt ölçümü yok. Eski veya ölçümü
                  kaydedilmemiş çağrılar için süre hesaplanamaz.
                </Notice>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <table
                      className="w-full text-sm text-left"
                      aria-label="Yanıt süresi dağılımı"
                    >
                      <thead>
                        <tr className="border-b">
                          <th className="p-3">Ölçüm</th>
                          <th className="p-3">Ortanca (P50)</th>
                          <th className="p-3">P95</th>
                          <th className="p-3">Örnek / Eksik</th>
                        </tr>
                      </thead>
                      <tbody>
                        {Object.entries(labels).map(([key, label]) => {
                          const m = report.metrics[key];
                          return (
                            <tr key={key} className="border-b">
                              <th className="p-3 font-medium">{label}</th>
                              <td className="p-3 whitespace-nowrap">
                                {ms(m.p50_ms)}
                              </td>
                              <td className="p-3 whitespace-nowrap">
                                {ms(m.p95_ms)}
                              </td>
                              <td className="p-3">
                                {m.samples} / {m.missing}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <p className="muted mt-4">
                    Ortanca: ölçümlerin ortasındaki değer. P95: ölçümlerin
                    %95'inin altında kaldığı süre. Yalnızca tamamlanmış normal
                    yanıtlar hesaplanır; aşamalar birbiriyle örtüşebileceği için
                    toplanmaz.
                  </p>
                  {report.metrics.vad_end_to_audio_estimate_ms.samples < 50 && (
                    <Notice>
                      50 geçerli yanıt ölçümünden az veri var. Bu görünüm
                      performans hedeflerinin sağlandığını kanıtlamaz.
                    </Notice>
                  )}
                </>
              )}
              {report.latest_import_at && (
                <p className="muted mt-4">
                  Son ölçüm aktarımı:{" "}
                  {new Date(report.latest_import_at).toLocaleString("tr-TR")}
                </p>
              )}
            </>
          )}
        </>
      )}
    </section>
  );
}
