"use client";
import { PromptVariables } from "./prompt-variables";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AudioLines,
  Phone,
  FileText,
  Send,
  ArrowRight,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Field, Loading, Notice, SelectField } from "./shared";
import {
  api,
  errorMessage,
  maskNumber,
  type Agent,
  type Draft,
  type Releases,
  type Phone as PhoneNumber,
  type Connection,
  type Model,
} from "@/lib/api";
import { VoicePreview } from "./voice-preview";
import { ResponseExperience } from "./response-experience";
import { MCPTools } from "./mcp-tools";
import { useDraftMemory } from "./draft-memory";
import { hasUnsafeNumber } from "@/lib/mcp";
import { PostCallActions } from "./post-call-actions";
import { ReleaseHistory } from "./release-history";
import type { WorkspaceProps } from "./workspace";

const speechFields: [string, string, number][] = [
  ["greeting_text", "Karşılama cümlesi", 400],
  ["unavailable_text", "Hizmet verilemediğinde", 400],
  ["further_help_text", "Ek yardım sorusu", 400],
  ["clarification_text", "Anlaşılmayan konuşma", 400],
  ["silence_reminder_text", "Sessizlik hatırlatması", 400],
  ["silence_timeout_text", "Sessizlikte kapanış", 400],
  ["farewell_text", "Vedalaşma", 400],
  ["explicit_stop_text", "Görüşmeyi bitirme", 400],
  ["note_ack_template", "Not alındı bildirimi", 400],
  ["callback_unknown_template", "Dönüş zamanı bilinmediğinde", 400],
  ["summary_role_template", "Özet talimatı", 2000],
];
export function AgentEditor({
  scope,
  session,
  role,
  id,
}: WorkspaceProps & { id: string }) {
  const base = `workspaces/${scope}`;
  const path = `${base}/agents/${id}`;
  const memory = useDraftMemory();
  const editable = role !== "viewer";
  const [agent, setAgent] = useState<Agent | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [releases, setReleases] = useState<Releases | null>(null);
  const [numbers, setNumbers] = useState<PhoneNumber[]>([]);
  const [providers, setProviders] = useState<Connection[]>([]);
  const [telegram, setTelegram] = useState<Connection[]>([]);
  const [models, setModels] = useState<Model[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [preview, setPreview] = useState("");
  const [tab, setTab] = useState("general");
  const [publishOpen, setPublishOpen] = useState(false);
  const [preparation, setPreparation] = useState<{
    id: string;
    readiness: string;
  } | null>(null);
  const dirty =
    !!agent && JSON.stringify(draft) !== JSON.stringify(agent.content);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const [a, r, n, p, t, m] = await Promise.all([
          api<Agent>(path, { signal: controller.signal }),
          api<Releases>(`${path}/releases`, { signal: controller.signal }),
          api<{ numbers: PhoneNumber[] }>(`${base}/numbers`, {
            signal: controller.signal,
          }),
          api<{ connections: Connection[] }>(`${base}/provider-connections`, {
            signal: controller.signal,
          }),
          api<{ connections: Connection[] }>(`${base}/telegram-connections`, {
            signal: controller.signal,
          }),
          api<{ models: Model[] }>(`${base}/models`, {
            signal: controller.signal,
          }),
        ]);
        if (!controller.signal.aborted) {
          const retained = memory.drafts.get(path);
          setAgent(retained?.saved ?? a);
          setDraft(retained?.draft ?? a.content);
          if (retained) {
            setNotice("Kaydedilmemiş değişikliklerin bu oturumda korundu.");
            if (retained.saved.version !== a.version)
              setError(
                "Kaydedilmiş taslak başka bir yerde değişti. Korunan değişikliklerini güncel sürümle karşılaştırmadan kaydetme.",
              );
          }
          setReleases(r);
          setNumbers(n.numbers);
          setProviders(p.connections);
          setTelegram(t.connections);
          setModels(m.models);
        }
      } catch (e) {
        if (!controller.signal.aborted) setError(errorMessage(e));
      }
    }
    void load();
    return () => controller.abort();
  }, [base, path, memory]);
  useEffect(() => {
    if (!agent || !draft || memory.session !== session.csrf_token) return;
    if (dirty) memory.drafts.set(path, { saved: agent, draft });
    else memory.drafts.delete(path);
  }, [agent, draft, dirty, memory, path, session.csrf_token]);
  useEffect(() => {
    if (!dirty) return;
    const navigate = (event: MouseEvent) => {
      const link = (event.target as Element).closest("a[href]");
      if (
        link &&
        !window.confirm(
          "Kaydedilmemiş değişikliklerin var. Bu sayfadan ayrılmak istiyor musun?",
        )
      ) {
        event.preventDefault();
        event.stopPropagation();
      }
    };
    document.addEventListener("click", navigate, true);
    return () => {
      document.removeEventListener("click", navigate, true);
    };
  }, [dirty]);
  function patch(key: string, value: unknown) {
    setDraft((d) => (d ? ({ ...d, [key]: value } as Draft) : null));
    setNotice("");
    setPreview("");
    setPreparation(null);
  }
  async function save() {
    if (!agent || !draft) return;
    if (hasUnsafeNumber(draft.mcp_tools)) {
      setError(
        "MCP parametrelerinde güvenli sayı sınırı aşılıyor. Araç ayarlarını kontrol et; tam sayı büyüklüğü 9007199254740991 değerini aşamaz.",
      );
      return;
    }
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const a = await api<Agent>(path, {
        method: "PUT",
        body: draft,
        csrf: session.csrf_token,
        version: agent.version,
      });
      setAgent(a);
      setDraft(a.content);
      setPreparation(null);
      setNotice("Taslak kaydedildi. Telefonda çalışan sürüm değişmedi.");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function previewGreeting() {
    setBusy(true);
    setError("");
    try {
      const p = await api<{ greeting: string }>(`${path}/preview`, {
        body: {},
        csrf: session.csrf_token,
      });
      setPreview(p.greeting);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function prepare() {
    if (!agent) return;
    setBusy(true);
    setError("");
    try {
      const p = await api<{ id: string; readiness: string }>(
        `${path}/prepare`,
        { body: {}, csrf: session.csrf_token, version: agent.version },
      );
      setPreparation(p);
      setPublishOpen(true);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  async function publish() {
    if (!preparation || !releases) return;
    setBusy(true);
    setError("");
    try {
      await api(`${path}/publish`, {
        body: { preparation_id: preparation.id },
        csrf: session.csrf_token,
        version: releases.version,
      });
      setReleases(await api<Releases>(`${path}/releases`));
      setPublishOpen(false);
      setPreparation(null);
      setNotice(
        "Yeni sürüm yayınlandı. Çağrılarda kullanmak için Numaralar ekranından bağlayabilirsin.",
      );
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  if (!draft || !agent || !releases)
    return error ? <Notice error>{error}</Notice> : <Loading />;
  const bound = numbers.filter(
    (n) => n.enabled && releases.releases.some((r) => r.id === n.release_id),
  );
  const actions = draft.post_call_actions || [];
  return (
    <>
      <div className="page-heading">
        <div>
          <div className="flex items-center gap-4 mb-2">
            <h1 className="mb-0">{draft.agent_name}</h1>
            <Badge variant="outline">
              {dirty
                ? "Kaydedilmedi"
                : bound.length
                  ? "Numaraya bağlı"
                  : releases.current_release
                    ? "Sürüm hazır"
                    : "Taslak"}
            </Badge>
          </div>
          <p className="subtitle">
            {draft.owner_display_name} · Kişisel asistan
          </p>
          <p className="muted mt-2">
            Düzenlemeler yayındaki agenti değiştirmez.
          </p>
        </div>
        <div className="actions">
          <ReleaseHistory
            path={path}
            csrf={session.csrf_token}
            owner={role === "owner"}
            dirty={dirty}
            disabled={busy}
            onChanged={setReleases}
          />
          {editable && (
            <Button variant="outline" onClick={save} disabled={busy || !dirty}>
              {busy ? "İşleniyor…" : "Taslağı kaydet"}
            </Button>
          )}
          {role === "owner" && (
            <Button onClick={prepare} disabled={busy || dirty}>
              Sürümü yayınla
            </Button>
          )}
        </div>
      </div>
      {error && <Notice error>{error}</Notice>}
      {notice && <Notice>{notice}</Notice>}
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList
          variant="line"
          className="editor-tabs w-full justify-start bg-transparent border-b rounded-none h-12 gap-5 p-0"
        >
          <TabsTrigger value="general">Genel</TabsTrigger>
          <TabsTrigger value="instructions">Talimatlar</TabsTrigger>
          <TabsTrigger value="tools">Araçlar</TabsTrigger>
          <TabsTrigger value="after">Çağrı sonrası</TabsTrigger>
        </TabsList>
        <div className="editor-grid">
          <fieldset className="min-w-0" disabled={!editable || busy}>
            <TabsContent value="general" className="mt-0">
              <div className="fields">
                <h2 className="section-title mb-0">Kimlik</h2>
                <div className="field-pair">
                  <Field
                    label="Agent adı"
                    value={draft.agent_name}
                    onChange={(v) => patch("agent_name", v)}
                    maxLength={100}
                    required
                  />
                  <Field
                    label="Kimin asistanı?"
                    value={draft.owner_display_name}
                    onChange={(v) => patch("owner_display_name", v)}
                    maxLength={100}
                    required
                  />
                </div>
                <details>
                  <summary className="text-link cursor-pointer">
                    Hitap biçimleri
                  </summary>
                  <div className="fields mt-4">
                    <p className="muted">
                      İsim değiştiğinde konuşmada kullanılacak bu biçimleri de
                      güncelle.
                    </p>
                    {(
                      [
                        ["owner_address", "Hitap · ör. Burhan Bey"],
                        ["owner_dative", "Kime · ör. Burhan Bey’e"],
                        ["owner_genitive", "Kimin · ör. Burhan Bey’in"],
                      ] as const
                    ).map(([key, label]) => (
                      <Field
                        key={key}
                        label={label}
                        value={draft[key]}
                        onChange={(v) => patch(key, v)}
                        maxLength={120}
                        required
                      />
                    ))}
                  </div>
                </details>
                <ResponseExperience value={draft.response_experience}
                  onChange={(value) => patch("response_experience", value)} />
                <Field
                  label="Görevi"
                  value={draft.instructions}
                  onChange={(v) => patch("instructions", v)}
                  area
                  rows={7}
                  maxLength={20000}
                  required
                  hint={`${draft.instructions.length.toLocaleString("tr-TR")} / 20.000 karakter`}
                />
                <button
                  className="text-link w-fit"
                  type="button"
                  onClick={() => setTab("instructions")}
                >
                  Diğer talimatları düzenle <ArrowRight size={15} />
                </button>
                <div className="field-pair">
                  <SelectField
                    label="Model"
                    value={draft.model}
                    onChange={(v) => patch("model", v)}
                  >
                    {!models.some((m) => m.id === draft.model) && (
                      <option value={draft.model}>
                        {draft.model} · Kullanılamıyor
                      </option>
                    )}
                    {models.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.name}
                      </option>
                    ))}
                  </SelectField>
                  <SelectField
                    label="Ses"
                    value={draft.voice}
                    onChange={(v) => patch("voice", v)}
                  >
                    <option value="ema-default">EMA · Türkçe</option>
                  </SelectField>
                </div>
                <SelectField
                  label="Model bağlantısı"
                  value={draft.model_connection || ""}
                  onChange={(v) => patch("model_connection", v || null)}
                >
                  <option value="">Bağlantı seç</option>
                  {providers.map((c) => (
                    <option key={c.id} value={c.id} disabled={!c.enabled}>
                      {c.label}
                      {!c.enabled ? " · Devre dışı" : ""}
                    </option>
                  ))}
                </SelectField>
                <p className="muted">
                  Konuşma ayarlarını Alojan optimize eder.{" "}
                  <Link href="/baglantilar" className="text-link">
                    Bağlantıları yönet
                  </Link>
                </p>
                <hr className="divider m-0" />
                <div>
                  <h2 className="section-title mb-3">Bağlı numara</h2>
                  <div className="flex gap-4 items-center justify-between">
                    <span>
                      {bound.length
                        ? bound.map((n) => maskNumber(n.number)).join(", ")
                        : "Henüz numara bağlanmadı"}
                    </span>
                    <Link href="/numaralar" className="text-link">
                      Yönet <ArrowRight size={15} />
                    </Link>
                  </div>
                </div>
              </div>
            </TabsContent>
            <TabsContent value="instructions" className="mt-0">
              <div className="fields">
                <Field
                  label="Agent talimatları"
                  value={draft.instructions}
                  onChange={(v) => patch("instructions", v)}
                  area
                  rows={14}
                  maxLength={20000}
                  required
                />
                <PromptVariables
                  value={draft.prompt_template ?? null}
                  onChange={(value) => patch("prompt_template", value)}
                  onInsert={(name) => patch("instructions", draft.instructions + " {{" + name + "}}")}
                />
                <Field
                  label="Rolü"
                  value={draft.role_description}
                  onChange={(v) => patch("role_description", v)}
                  maxLength={2000}
                />
                <Field
                  label="Konuşma tarzı"
                  value={draft.tone_description}
                  onChange={(v) => patch("tone_description", v)}
                  area
                  maxLength={2000}
                />
                <Field
                  label="İşin hakkında"
                  value={draft.business_context}
                  onChange={(v) => patch("business_context", v)}
                  area
                  maxLength={6000}
                />
                <details>
                  <summary className="text-link cursor-pointer">
                    Konuşma ifadelerini düzenle
                  </summary>
                  <div className="fields mt-5">
                    <p className="muted">
                      Yapay zekâ kimliği karşılamaya otomatik eklenir.
                      Metinlerde {"{owner_address}"}, {"{owner_dative}"} ve{" "}
                      {"{owner_genitive}"} kullanılabilir.
                    </p>
                    {speechFields.map(([key, label, max]) => (
                      <Field
                        key={key}
                        label={label}
                        value={String(draft[key] || "")}
                        onChange={(v) => patch(key, v)}
                        area
                        maxLength={max}
                        required
                      />
                    ))}
                    <label className="flex gap-3 items-center">
                      <input
                        type="checkbox"
                        checked={draft.offer_further_help === true}
                        onChange={(e) =>
                          patch("offer_further_help", e.target.checked)
                        }
                      />
                      Ek yardım sorusu sor
                    </label>
                  </div>
                </details>
              </div>
            </TabsContent>
            <TabsContent value="tools" className="mt-0">
              <h2 className="section-title">Konuşurken kullanabilecekleri</h2>
              <p className="muted">
                Araçları seç, hangi durumda kullanılacağını talimatlarda anlat.
              </p>
              <div className="form-panel">
                <label className="flex items-center gap-3 font-semibold">
                  <input
                    type="checkbox"
                    checked={draft.tools.length > 0}
                    onChange={(e) =>
                      patch(
                        "tools",
                        e.target.checked
                          ? [
                              {
                                tool: "take_note",
                                alias: "take_note",
                                guidance:
                                  "Arayanın iletmek istediği somut mesajı kaydet.",
                              },
                            ]
                          : [],
                      )
                    }
                  />
                  Mesajı not al
                </label>
                <p className="muted mt-3">
                  Arayanın isteğini bu görüşmeye ait bir not olarak saklar.
                </p>
                {draft.tools[0] && (
                  <div className="fields mt-5">
                    <Field
                      label="Araç adı"
                      value={draft.tools[0].alias}
                      onChange={(v) =>
                        patch("tools", [{ ...draft.tools[0], alias: v }])
                      }
                      maxLength={40}
                    />
                    <Field
                      label="Ne zaman kullanmalı?"
                      value={draft.tools[0].guidance}
                      onChange={(v) =>
                        patch("tools", [{ ...draft.tools[0], guidance: v }])
                      }
                      area
                      maxLength={1000}
                    />
                  </div>
                )}
              </div>
              <MCPTools
                base={base}
                path={path}
                csrf={session.csrf_token}
                version={agent.version}
                bindings={draft.mcp_tools || []}
                owner={role === "owner"}
                editable={editable}
                disabled={busy}
                dirty={dirty}
                onChange={(v) => patch("mcp_tools", v)}
              />
              <p className="muted mt-6">
                Konuşma ve görüşmeyi bitirme işlevleri her agentte hazırdır.
              </p>
            </TabsContent>
            <TabsContent value="after" className="mt-0">
              <PostCallActions
                base={base}
                path={path}
                version={agent.version}
                actions={actions}
                outputs={draft.outputs || []}
                tools={draft.mcp_tools || []}
                onOutputsChange={(outputs) => patch("outputs", outputs)}
                connections={telegram}
                csrf={session.csrf_token}
                owner={role === "owner"}
                dirty={dirty}
                onChange={(a) => patch("post_call_actions", a)}
              />
            </TabsContent>
          </fieldset>
          <aside className="preview">
            <h2>Karşılama</h2>
            <AudioLines size={31} className="text-primary" />
            <blockquote>
              {preview ||
                "Kaydedilmiş karşılama metnini buradan kontrol edebilirsin."}
            </blockquote>
            <Button
              variant="outline"
              onClick={previewGreeting}
              disabled={busy || dirty}
            >
              Metni önizle
            </Button>
            {dirty && (
              <p className="muted mt-3">Önizleme için önce taslağını kaydet.</p>
            )}
            <VoicePreview
              csrf={session.csrf_token}
              editable={editable}
              key={`${agent.version}:${dirty}`}
              path={path}
              version={agent.version}
              dirty={dirty}
              waiting={agent.content.response_experience?.enabled === true}
            />
            <hr className="divider" />
            <h2>Çağrı akışı</h2>
            <ol className="flow">
              <li>
                <Phone />
                Aramayı karşıla
              </li>
              {draft.tools.length > 0 && (
                <li>
                  <FileText />
                  Mesajı not al
                </li>
              )}
              {actions.length > 0 && (
                <li>
                  <Send />
                  Özeti Telegram’a gönder
                </li>
              )}
            </ol>
            <hr className="divider" />
            <p className="muted">
              İsim veya karşılama değişirse ses yeniden hazırlanır. Hazır
              olmadan yayınlanamaz.
            </p>
          </aside>
        </div>
      </Tabs>
      <Dialog
        open={publishOpen}
        onOpenChange={(v) => {
          if (!busy) setPublishOpen(v);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Sürümü yayınla</DialogTitle>
            <DialogDescription>
              {preparation?.readiness === "ready_to_publish"
                ? "Kaydedilmiş taslağın yeni bir sürüm olarak yayınlanacak. Numara eşlemesi ayrı yapılır; devam eden görüşmeler etkilenmez."
                : "Bu değişiklik için yeni ses dosyalarının hazırlanması gerekiyor. Mevcut sürüm çalışmaya devam ediyor."}
            </DialogDescription>
          </DialogHeader>
          {error && <Notice error>{error}</Notice>}
          {preparation?.readiness === "ready_to_publish" ? (
            <Button onClick={publish} disabled={busy}>
              <Check size={16} />
              {busy ? "Yayınlanıyor…" : "Bu sürümü yayınla"}
            </Button>
          ) : (
            <Button variant="outline" onClick={() => setPublishOpen(false)}>
              Düzenlemeye dön
            </Button>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
