"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowRight, Phone, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, errorMessage } from "@/lib/api";
import { Loading, Notice, SelectField } from "./shared";
import { Performance } from "./performance";
import { CallTranscript } from "./call-transcript";
import { DeliveryRetry } from "./delivery-retry";
import type { WorkspaceProps } from "./workspace";

type Call = {
  id: string;
  profile_id: string;
  agent_name: string;
  owner_name: string;
  revision: number;
  status: string;
  summary_status: string;
  started_at: string;
  answered_at: string | null;
  ended_at: string | null;
  duration_ms: number | null;
  called_number: string;
  hangup_reason: string | null;
  failure_code: string | null;
};
type Detail = Call & {
  outputs?: Record<string, unknown> | null;
  output_status?: Record<string, string> | null;
  caller_number: string | null;
  caller_number_source: string;
  summary: {
    subject: string;
    summary: string;
    requested_action: string;
    urgency: string;
  } | null;
  note: {
    subject: string;
    message: string;
    caller_name: string | null;
    confirmed: boolean;
    version: number;
  } | null;
  deliveries: {
    id: string;
    alias: string;
    status: string;
    attempts: number;
    failure_code: string | null;
    retry_queued: boolean;
  }[];
};
const summaryLabels: Record<string, string> = {
  pending: "Özet sırada",
  processing: "Özet hazırlanıyor",
  done: "Özet hazır",
  failed: "Özet oluşturulamadı",
  not_requested: "Özet istenmedi",
};
const deliveryLabels: Record<string, string> = {
  pending: "Gönderim sırada",
  leased: "Hazırlanıyor",
  sending: "Gönderiliyor",
  sent: "Gönderildi",
  failed: "Gönderilemedi",
  paused: "Duraklatıldı",
  delivery_unknown: "Sonuç doğrulanamadı",
};
const failureLabels: Record<string, string> = {
  authority_revoked: "Gönderim izni veya bağlantı artık geçerli değil.",
  invalid_intent: "Bildirim ayarları doğrulanamadı.",
  credential_unavailable: "Bağlantı bilgilerine erişilemiyor.",
  connect_failed: "Bildirim servisine bağlanılamadı.",
  rate_limited: "Bildirim servisi beklemeyi istiyor.",
  rejected: "Bildirim servisi isteği kabul etmedi.",
  invalid_response: "Servis yanıtı doğrulanamadı.",
  send_uncertain: "Mesaj ulaşmış olabilir; gönderim sonucu kesinleştirilemedi.",
  attempts_exhausted: "Gönderim denemeleri tamamlandı.",
};
function date(value: string) {
  return new Intl.DateTimeFormat("tr-TR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}
function duration(ms: number | null) {
  if (ms === null) return "—";
  const seconds = Math.floor(ms / 1000);
  return `${Math.floor(seconds / 60)} dk ${seconds % 60} sn`;
}
function outcome(call: Call) {
  if (
    call.failure_code ||
    call.hangup_reason === "failed" ||
    call.status === "failed"
  )
    return "Başarısız çağrı";
  if (call.ended_at)
    return call.answered_at ? "Görüşme tamamlandı" : "Yanıtlanmadı";
  return call.answered_at ? "Görüşme sürüyor" : "Bağlanıyor";
}
export function Calls({ scope }: WorkspaceProps) {
  const base = `workspaces/${scope}`;
  const [agents, setAgents] = useState<{ id: string; name: string }[]>([]);
  const [agent, setAgent] = useState("");
  const [cursor, setCursor] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [data, setData] = useState<{
    calls: Call[];
    next_cursor: string | null;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    const c = new AbortController();
    api<{ agents: { id: string; name: string }[] }>(`${base}/agents`, {
      signal: c.signal,
    })
      .then((r) => {
        if (!c.signal.aborted) setAgents(r.agents);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      });
    return () => c.abort();
  }, [base]);
  useEffect(() => {
    const c = new AbortController();
    setLoading(true);
    setError("");
    setData(null);
    const query = new URLSearchParams();
    if (agent) query.set("agent", agent);
    if (cursor) query.set("after", cursor);
    api<{ calls: Call[]; next_cursor: string | null }>(
      `${base}/calls?${query}`,
      { signal: c.signal },
    )
      .then((r) => {
        if (!c.signal.aborted) setData(r);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [base, agent, cursor, refresh]);
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Aramalar</h1>
          <p className="subtitle">
            Agentlerinin karşıladığı görüşmeler ve bıraktıkları notlar.
          </p>
        </div>
        <Button
          variant="outline"
          disabled={loading}
          onClick={() => {
            setCursor("");
            setRefresh((r) => r + 1);
          }}
        >
          <RefreshCw size={16} />
          Yenile
        </Button>
      </div>
      <div className="max-w-sm mb-8">
        <SelectField
          label="Agent"
          value={agent}
          onChange={(v) => {
            setAgent(v);
            setCursor("");
          }}
        >
          <option value="">Tüm agentler</option>
          {agents.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </SelectField>
      </div>
      {error && <Notice error>{error}</Notice>}
      {loading ? (
        <Loading />
      ) : (
        data &&
        (data.calls.length ? (
          <>
            <div aria-label="Çağrı listesi">
              {data.calls.map((call) => (
                <Link
                  className="list-item"
                  href={`/aramalar/${call.id}`}
                  key={call.id}
                >
                  <div className="agent-identity">
                    <span className="avatar">
                      <Phone size={18} />
                    </span>
                    <div>
                      <strong className="agent-name">{call.agent_name}</strong>
                      <div className="muted">
                        {date(call.started_at)} · {duration(call.duration_ms)}
                      </div>
                    </div>
                  </div>
                  <div className="actions">
                    <Badge variant="outline">{outcome(call)}</Badge>
                    <span className="muted">
                      {summaryLabels[call.summary_status] ||
                        "Özet durumu bilinmiyor"}
                    </span>
                    <ArrowRight size={16} />
                  </div>
                </Link>
              ))}
            </div>
            <div className="actions mt-6">
              {cursor && (
                <Button variant="outline" onClick={() => setCursor("")}>
                  En yeni aramalar
                </Button>
              )}
              {data.next_cursor && (
                <Button
                  variant="outline"
                  onClick={() => setCursor(data.next_cursor!)}
                >
                  Daha eski aramalar
                  <ArrowRight size={16} />
                </Button>
              )}
            </div>
          </>
        ) : (
          <div className="empty">
            <Phone size={28} />
            <h2>Henüz arama yok</h2>
            <p className="muted">
              Bu çalışma alanındaki görüşmeler burada görünecek.
            </p>
          </div>
        ))
      )}
    </>
  );
}
export function CallDetail({
  scope,
  id,
  session,
  role,
}: WorkspaceProps & { id: string }) {
  const [notice, setNotice] = useState("");
  const [data, setData] = useState<Detail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const c = new AbortController();
    setLoading(true);
    setError("");
    setData(null);
    api<Detail>(`workspaces/${scope}/calls/${id}`, { signal: c.signal })
      .then((r) => {
        if (!c.signal.aborted) setData(r);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [scope, id, refresh]);
  return (
    <>
      <Link href="/aramalar" className="text-link mb-6">
        <ArrowLeft size={14} />
        Aramalara dön
      </Link>
      <div className="page-heading">
        <div>
          <h1>Görüşme detayı</h1>
          <p className="subtitle">
            {data
              ? `${data.agent_name} · ${date(data.started_at)}`
              : "Çağrı kaydı"}
          </p>
        </div>
        <Button
          variant="outline"
          disabled={loading}
          onClick={() => setRefresh((r) => r + 1)}
        >
          <RefreshCw size={16} />
          Yenile
        </Button>
      </div>
      {error && <Notice error>{error}</Notice>}
      {notice && <Notice>{notice}</Notice>}
      {loading ? (
        <Loading />
      ) : (
        data && (
          <div className="break-words [overflow-wrap:anywhere]">
            <div className="actions mb-6">
              <Badge variant="outline">{outcome(data)}</Badge>
              <span className="muted">
                {duration(data.duration_ms)} · Sürüm {data.revision}
              </span>
            </div>
            <dl className="field-pair mb-8">
              <div>
                <dt className="muted">Asistanı olduğu kişi</dt>
                <dd>{data.owner_name}</dd>
              </div>
              <div>
                <dt className="muted">Aranan numara</dt>
                <dd>{data.called_number}</dd>
              </div>
              <div>
                <dt className="muted">Arayan numara</dt>
                <dd>{data.caller_number || "Paylaşılmadı"}</dd>
                <p className="muted">
                  Operatörden gelen bilgi; kimlik doğrulaması değildir.
                </p>
              </div>
              <div>
                <dt className="muted">Yanıtlanma</dt>
                <dd>
                  {data.answered_at ? date(data.answered_at) : "Yanıtlanmadı"}
                </dd>
              </div>
            </dl>
            <section className="form-panel" aria-labelledby="call-summary">
              <h2 className="section-title" id="call-summary">
                Görüşme özeti
              </h2>
              {data.summary ? (
                <>
                  <h3 className="font-semibold">{data.summary.subject}</h3>
                  <p className="whitespace-pre-wrap">{data.summary.summary}</p>
                  <p className="muted">İstenen işlem</p>
                  <p className="whitespace-pre-wrap">
                    {data.summary.requested_action || "Belirtilmedi"}
                  </p>
                  <Badge variant="outline">
                    {{
                      low: "Normal öncelik",
                      medium: "Orta öncelik",
                      high: "Yüksek öncelik",
                    }[data.summary.urgency] || "Öncelik belirtilmedi"}
                  </Badge>
                </>
              ) : (
                <p className="muted">
                  {summaryLabels[data.summary_status] ||
                    "Özet durumu bilinmiyor"}
                  .{" "}
                  {data.summary_status === "failed" &&
                    "Görüşmenin notu aşağıda korunur."}
                </p>
              )}
            </section>
            {data.outputs && (
              <section
                className="form-panel"
                aria-label="Görüşmenin özel alanları"
              >
                <h2 className="section-title">Özel alanlar</h2>
                <dl className="fields">
                  {Object.entries(data.outputs).map(([name, value]) => (
                    <div key={name}>
                      <dt className="font-semibold">{name}</dt>
                      <dd className="whitespace-pre-wrap break-all">
                        {value === null
                          ? "—"
                          : typeof value === "string"
                            ? value
                            : JSON.stringify(value)}
                      </dd>
                      <p className="muted">
                        {(
                          {
                            done: "Hazır",
                            missing: "Bilgi bulunamadı",
                            failed: "Doğrulanamadı",
                            unavailable: "Başarılı araç sonucu yok",
                          } as Record<string, string>
                        )[data.output_status?.[name] || ""] ||
                          "Durum bilinmiyor"}
                      </p>
                    </div>
                  ))}
                </dl>
              </section>
            )}
            <section className="form-panel" aria-labelledby="call-note">
              <h2 className="section-title" id="call-note">
                Son alınan not
              </h2>
              {data.note ? (
                <>
                  <div className="actions mb-4">
                    <Badge variant="outline">
                      {data.note.confirmed
                        ? "Arayan tarafından onaylandı"
                        : "Arayan onayı alınmadı"}
                    </Badge>
                    <span className="muted">Not {data.note.version}</span>
                  </div>
                  {data.note.caller_name && <p>{data.note.caller_name}</p>}
                  <h3 className="font-semibold">{data.note.subject}</h3>
                  <p className="whitespace-pre-wrap">{data.note.message}</p>
                </>
              ) : (
                <p className="muted">Bu görüşmede kaydedilmiş bir not yok.</p>
              )}
            </section>
            <section className="form-panel" aria-labelledby="call-deliveries">
              <h2 className="section-title" id="call-deliveries">
                Bildirim sonucu
              </h2>
              {data.deliveries.length ? (
                data.deliveries.map((d) => (
                  <div className="list-item" key={d.id}>
                    <div>
                      <strong>{d.alias}</strong>
                      <p className="muted mb-0">
                        {d.attempts} gönderim denemesi
                      </p>
                      {d.failure_code && (
                        <p className="muted mt-2 mb-0">
                          {failureLabels[d.failure_code] ||
                            "Gönderim tamamlanamadı."}
                        </p>
                      )}
                      {d.retry_queued && (
                        <p className="muted mt-2 mb-0">
                          Onaylanan yeniden deneme sırada.
                        </p>
                      )}
                    </div>
                    <div className="actions">
                      <Badge variant="outline">
                        {deliveryLabels[d.status] || "Bilinmeyen durum"}
                      </Badge>
                      {role === "owner" &&
                        !d.retry_queued &&
                        ["failed", "paused", "delivery_unknown"].includes(
                          d.status,
                        ) && (
                          <DeliveryRetry
                            scope={scope}
                            profile={data.profile_id}
                            job={d.id}
                            csrf={session.csrf_token}
                            onAccepted={() => {
                              setNotice(
                                "Yeniden gönderim isteği sıraya alındı. Sonucu Yenile ile kontrol edebilirsiniz.",
                              );
                              setRefresh((r) => r + 1);
                            }}
                          />
                        )}
                    </div>
                  </div>
                ))
              ) : (
                <p className="muted">
                  {["pending", "processing", "not_requested"].includes(
                    data.summary_status,
                  )
                    ? "Henüz bir bildirim kaydı oluşmadı."
                    : "Bu görüşme için bildirim oluşturulmadı."}
                </p>
              )}
            </section>
            <Performance scope={scope} call={id} />
            <CallTranscript scope={scope} id={id} />
          </div>
        )
      )}
    </>
  );
}
