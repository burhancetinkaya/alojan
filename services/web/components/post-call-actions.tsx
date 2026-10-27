"use client";
import type { MCPBinding } from "@/lib/mcp";
import { ActionConditionField, conditionLabels } from "./action-condition";
import { OutputEditor } from "./output-editor";
import type { OutputDefinition } from "@/lib/api";
import { HTTPActionEditor } from "./http-action-editor";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  api,
  ApiError,
  errorMessage,
  type Action,
  type Connection,
  type HTTPConnection,
} from "@/lib/api";
import { Field, Notice, SelectField } from "./shared";

export const fieldLabels: Record<string, string> = {
  "transcript.text": "Konuşma dökümü · Metin",
  "transcript.status": "Konuşma dökümü · Durum",
  call_id: "Görüşme kimliği",
  agent_name: "Agent adı",
  owner_name: "Numara sahibi",
  called_number: "Aranan numara",
  called_number_source: "Aranan numaranın kaynağı",
  caller_number: "Arayan numara",
  caller_number_source: "Arayan numaranın kaynağı",
  started_at: "Başlangıç zamanı",
  answered_at: "Yanıtlama zamanı",
  ended_at: "Bitiş zamanı",
  duration_ms: "Görüşme süresi (ms)",
  outcome: "Görüşme sonucu",
  summary_status: "Özet durumu",
  "summary.caller_name": "Özet · Arayanın adı",
  "summary.subject": "Özet · Konu",
  "summary.summary": "Özet · Açıklama",
  "summary.requested_action": "Özet · İstenen işlem",
  "summary.urgency": "Özet · Aciliyet",
  "summary.confirmation_status": "Özet · Teyit durumu",
  "last_note.caller_name": "Son not · Arayanın adı",
  "last_note.subject": "Son not · Konu",
  "last_note.message": "Son not · Mesaj",
  "last_note.confirmed": "Son not · Teyit edildi mi?",
};
type Review = {
  synthetic_previews?: Record<string, unknown>;
  draft_version: number;
  review_digest: string;
  review: {
    actions: (Action & {
      connection_label: string;
      chat_id?: string;
      endpoint?: string;
      auth_type?: string;
      event: string;
      condition: string;
      on_missing: string;
    })[];
  };
};
type Grant = { id: string; review_digest: string; enabled: boolean };
type Schema = {
  $defs: {
    TelegramAction: { properties: { fields: { items: { enum: string[] } } } };
  };
  properties: { post_call_actions: { maxItems: number } };
};
export function PostCallActions({
  base,
  path,
  version,
  actions,
  outputs,
  tools,
  onOutputsChange,
  connections,
  csrf,
  owner,
  dirty,
  onChange,
}: {
  base: string;
  path: string;
  version: number;
  actions: Action[];
  outputs: OutputDefinition[];
  tools: MCPBinding[];
  onOutputsChange: (outputs: OutputDefinition[]) => void;
  connections: Connection[];
  csrf: string;
  owner: boolean;
  dirty: boolean;
  onChange: (actions: Action[]) => void;
}) {
  const declaredFields = outputs.flatMap((d) => [
    `outputs.${d.name}`,
    `output_status.${d.name}`,
  ]);
  const labels = {
    ...fieldLabels,
    ...Object.fromEntries(
      outputs.flatMap((d) => [
        [`outputs.${d.name}`, `Özel alan · ${d.name}`],
        [`output_status.${d.name}`, `Özel alan durumu · ${d.name}`],
      ]),
    ),
  };
  const used = actions.flatMap((a) =>
    [...Object.values(a.body || {}), ...Object.values(a.query || {})]
      .filter(
        (v) =>
          v.kind === "source" && /^(outputs|output_status)\./.test(v.source),
      )
      .map((v) => (v.kind === "source" ? v.source.split(".")[1] : "")),
  );
  const [httpConnections, setHTTPConnections] = useState<HTTPConnection[]>([]);
  const [fields, setFields] = useState<string[]>([]);
  const [limit, setLimit] = useState(0);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [review, setReview] = useState<Review | null>(null);
  const [grant, setGrant] = useState<Grant | null>(null);
  const [open, setOpen] = useState(false);
  const [revoke, setRevoke] = useState(false);
  useEffect(() => {
    const c = new AbortController();
    api<Schema>(`${base}/agent-schema`, { signal: c.signal })
      .then((s) => {
        setFields(s.$defs.TelegramAction.properties.fields.items.enum);
        setLimit(s.properties.post_call_actions.maxItems);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      });
    return () => c.abort();
  }, [base]);
  useEffect(() => {
    const c = new AbortController();
    api<{ connections: HTTPConnection[] }>(`${base}/http-connections`, {
      signal: c.signal,
    })
      .then((v) => {
        if (!c.signal.aborted) setHTTPConnections(v.connections || []);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      });
    return () => c.abort();
  }, [base]);
  function addHTTP() {
    let n = 1;
    while (actions.some((a) => a.alias === `http_${n}`)) n++;
    change([
      ...actions,
      {
        alias: `http_${n}`,
        adapter: "http_request.v1",
        connection_id: httpConnections.find((c) => c.enabled)?.id || "",
        method: "POST",
        body: {
          call_id: { kind: "source", source: "call_id", on_missing: "fail" },
        },
        query: {},
        headers: {},
      },
    ]);
  }
  function change(next: Action[]) {
    setError("");
    setNotice("");
    setReview(null);
    setGrant(null);
    onChange(next);
  }
  function update(index: number, patch: Partial<Action>) {
    change(actions.map((a, i) => (i === index ? { ...a, ...patch } : a)));
  }
  function add() {
    let n = 1;
    while (actions.some((a) => a.alias === `telegram_${n}`)) n++;
    change([
      ...actions,
      {
        alias: `telegram_${n}`,
        adapter: "telegram.send_message.v1",
        event: "call.finalized.v1",
        condition: "answered",
        on_missing: "null",
        connection_id: connections.find((c) => c.enabled)?.id || "",
        fields: [
          "agent_name",
          "summary_status",
          "summary.subject",
          "summary.summary",
        ],
      },
    ]);
  }
  function required(field: string, selected: string[]) {
    return (
      (field === "summary_status" &&
        selected.some((f) => f.startsWith("summary."))) ||
      (field === "caller_number_source" &&
        selected.includes("caller_number")) ||
      (field === "called_number_source" && selected.includes("called_number"))
    );
  }
  function select(index: number, field: string, checked: boolean) {
    let selected = (actions[index].fields || []).filter((f) => f !== field);
    if (checked) selected.push(field);
    if (
      checked &&
      field.startsWith("summary.") &&
      !selected.includes("summary_status")
    )
      selected.push("summary_status");
    if (
      checked &&
      ["caller_number", "called_number"].includes(field) &&
      !selected.includes(field + "_source")
    )
      selected.push(field + "_source");
    update(index, { fields: fields.filter((f) => selected.includes(f)) });
  }
  async function inspect() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const [r, g] = await Promise.all([
        api<Review>(`${path}/action-review`),
        api<{ grants: Grant[] }>(`${path}/action-grants`),
      ]);
      if (r.draft_version !== version) throw new ApiError(412, "stale_version");
      setReview(r);
      setGrant(
        g.grants.find(
          (x) => x.enabled && x.review_digest === r.review_digest,
        ) || null,
      );
      setRevoke(false);
      setOpen(true);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function authorize() {
    if (!review) return;
    setBusy(true);
    setError("");
    try {
      await api(`${path}/action-grants`, {
        body: {
          draft_version: review.draft_version,
          review_digest: review.review_digest,
        },
        csrf,
      });
      setOpen(false);
      setNotice(
        "Bu hedeflere seçili bilgilerin gönderilmesine izin verildi. Etkinleştirmek için sürümü yayınlayıp numarana bağla.",
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function withdraw() {
    if (!grant) return;
    setBusy(true);
    setError("");
    try {
      await api(`${path}/action-grants/${grant.id}/revoke`, { body: {}, csrf });
      setOpen(false);
      setGrant(null);
      setNotice(
        "Gönderim izni kaldırıldı. Bu izne bağlı sürümlerin yeni bildirimleri gönderilmez; başlamış bir gönderim tamamlanabilir.",
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <h2 className="section-title">Görüşme bittiğinde</h2>
      <p className="muted">
        Cevaplanan görüşmenin ardından seçtiğin bilgiler, belirlediğin koşullar
        sağlandığında hedeflerine gönderilir. Taslağı kaydetmek mesaj göndermez.
      </p>
      <OutputEditor
        base={base}
        outputs={outputs}
        tools={tools}
        used={used}
        onChange={onOutputsChange}
      />
      {actions.map((action, index) =>
        action.adapter === "http_request.v1" ? (
          <HTTPActionEditor
            key={index}
            action={action}
            connections={httpConnections}
            fields={[...fields, ...declaredFields]}
            labels={labels}
            index={index}
            onChange={(a) =>
              change(actions.map((old, i) => (i === index ? a : old)))
            }
            onRemove={() => change(actions.filter((_, i) => i !== index))}
          />
        ) : (
          <section
            className="form-panel fields"
            key={index}
            aria-label={`Telegram işlemi ${index + 1}`}
          >
            <div className="flex items-center justify-between gap-3">
              <strong>Telegram bildirimi {index + 1}</strong>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                aria-label={`Telegram işlemi ${index + 1} kaldır`}
                onClick={() => change(actions.filter((_, i) => i !== index))}
              >
                <Trash2 size={17} />
              </Button>
            </div>
            <Field
              label="İşlem adı"
              value={action.alias}
              onChange={(alias) => update(index, { alias })}
              maxLength={40}
              hint="Küçük harf, rakam ve alt çizgi; örneğin ekip_ozeti."
            />
            <SelectField
              label="Telegram bağlantısı"
              value={action.connection_id}
              onChange={(connection_id) => update(index, { connection_id })}
            >
              <option value="">Bağlantı seç</option>
              {connections.map((c) => (
                <option key={c.id} value={c.id} disabled={!c.enabled}>
                  {c.label}
                  {c.enabled ? "" : " · Devre dışı"}
                </option>
              ))}
            </SelectField>
            <ActionConditionField
              value={action.condition}
              onChange={(condition) => update(index, { condition })}
            />
            <fieldset>
              <legend className="text-sm font-semibold mb-3">
                Gönderilecek bilgiler
              </legend>
              <div className="field-pair">
                {fields.map((field) => (
                  <label key={field} className="flex gap-2 items-start text-sm">
                    <input
                      className="mt-1"
                      type="checkbox"
                      checked={(action.fields || []).includes(field)}
                      disabled={required(field, action.fields || [])}
                      onChange={(e) => select(index, field, e.target.checked)}
                    />
                    {fieldLabels[field] || field}
                  </label>
                ))}
              </div>
            </fieldset>
            <p className="muted">
              Özet ve telefon bilgileri seçildiğinde durum/kaynak bilgileri de
              eklenir. Bulunamayan bilgiler boş gösterilir.
            </p>
          </section>
        ),
      )}
      <div className="actions mt-6">
        <Button
          variant="outline"
          disabled={
            busy ||
            !limit ||
            actions.length >= limit ||
            !connections.some((c) => c.enabled)
          }
          onClick={add}
        >
          <Plus size={16} />
          Telegram bildirimi ekle
        </Button>
        <Button
          variant="outline"
          disabled={
            busy ||
            !limit ||
            actions.length >= limit ||
            !httpConnections.some((c) => c.enabled)
          }
          onClick={addHTTP}
        >
          <Plus size={16} />
          HTTP isteği ekle
        </Button>
        {owner && actions.length > 0 && (
          <Button disabled={busy || dirty} onClick={inspect}>
            Gönderim iznini incele
          </Button>
        )}
      </div>
      {!connections.some((c) => c.enabled) && (
        <p className="muted mt-4">
          Önce{" "}
          <Link className="text-link" href="/baglantilar">
            Telegram bağlantısı ekle
          </Link>
          .
        </p>
      )}
      {dirty && actions.length > 0 && (
        <p className="muted mt-4">İzin incelemesi için önce taslağı kaydet.</p>
      )}
      {error && !open && <Notice error>{error}</Notice>}
      {notice && <Notice>{notice}</Notice>}
      <Dialog
        open={open}
        onOpenChange={(v) => {
          if (!busy) setOpen(v);
        }}
      >
        <DialogContent className="max-h-[85dvh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {revoke
                ? "Gönderim iznini kaldır"
                : actions.some((a) => a.adapter === "http_request.v1")
                  ? "Çağrı sonu gönderim izni"
                  : "Telegram gönderim izni"}
            </DialogTitle>
            <DialogDescription>
              {revoke
                ? "Aşağıdaki işlemlerin mevcut izni kaldırılacak. Bu izni kullanan yayındaki sürümler de etkilenir. Başlamış gönderimler geri alınamaz."
                : "Bu agente yönlendirilmiş çağrı sona erdikten sonra her işlemin aşağıdaki koşulu kontrol edilir. Yalnızca koşul sağlanırsa seçili bilgiler belirtilen hedefe gönderilir. Kaydetmek veya bu ekranı açmak gönderim yapmaz."}
            </DialogDescription>
          </DialogHeader>
          {review?.review.actions.map((a) => (
            <div key={a.alias} className="border-t pt-4">
              <strong>{a.connection_label}</strong>
              <p className="text-sm break-all">
                {a.adapter === "http_request.v1"
                  ? `Hedef: ${a.method} ${a.endpoint}`
                  : `Sohbet: ${a.chat_id}`}
              </p>
              <p className="muted">
                İşlem: {a.alias} ·{" "}
                {a.adapter === "http_request.v1"
                  ? `HTTP · ${a.auth_type === "bearer" ? "Kayıtlı erişim anahtarı" : "Kimlik doğrulama yok"}`
                  : "Telegram mesajı"}
              </p>
              <p className="text-sm mt-3">
                Gönderim koşulu: {conditionLabels[a.condition || "answered"]}
              </p>
              {a.transcript_policy && (
                <Notice>
                  Bu hedefe konuşma dökümü gönderilecek: ilk 100 kayıtlı satır,
                  en fazla 8 KB; ses veya model düşünceleri dahil değildir.
                  Döküm kişisel/hassas bilgiler içerebilir; otomatik sansür
                  uygulanmaz. Kısaltılma durumu ayrıca gönderilir. Karşılamada
                  paylaşım bilgilendirmesi zorunludur.
                </Notice>
              )}
              {a.adapter === "http_request.v1" && (
                <pre className="whitespace-pre-wrap break-all text-sm mt-3">
                  {JSON.stringify(
                    {
                      transcript_policy: a.transcript_policy,
                      headers: a.headers,
                      body: a.body,
                      query: a.query,
                      outputs: a.outputs,
                      output_tools: a.output_tools,
                    },
                    null,
                    2,
                  )}
                </pre>
              )}
              {!!review.synthetic_previews?.[a.alias] && (
                <details className="mt-3">
                  <summary className="text-link">
                    Örnek istek · gerçek çağrı verisi içermez
                  </summary>
                  <pre className="whitespace-pre-wrap break-all text-sm mt-2">
                    {JSON.stringify(
                      review.synthetic_previews[a.alias],
                      null,
                      2,
                    )}
                  </pre>
                </details>
              )}
              <ul className="mt-3 text-sm list-disc pl-5">
                {(a.fields || []).map((f) => (
                  <li key={f}>{fieldLabels[f] || f}</li>
                ))}
              </ul>
            </div>
          ))}
          {error && <Notice error>{error}</Notice>}
          {grant && !revoke ? (
            <>
              <Notice>
                Bu yapılandırma için daha önce izin verilmiş. Hedefin
                erişilebilirliği gönderim sırasında ayrıca kontrol edilir.
              </Notice>
              <Button variant="outline" onClick={() => setRevoke(true)}>
                Bu gönderim iznini kaldır
              </Button>
            </>
          ) : (
            <Button disabled={busy} onClick={revoke ? withdraw : authorize}>
              {busy
                ? "İşleniyor…"
                : revoke
                  ? "İzni kaldırmayı onayla"
                  : "Bu hedeflere gönderime izin ver"}
            </Button>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
