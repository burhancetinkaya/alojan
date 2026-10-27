"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Plus,
  ArrowRight,
  AudioLines,
  FileText,
  Phone,
  Play,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Field, Loading, Notice } from "./shared";
import {
  api,
  ApiError,
  errorMessage,
  maskNumber,
  type Agent,
  type Releases,
  type Phone as PhoneNumber,
} from "@/lib/api";
import type { WorkspaceProps } from "./workspace";

type Row = {
  id: string;
  name: string;
  version: number;
  agent?: Agent;
  releases?: Releases;
};
export function AgentList({ scope, session, role }: WorkspaceProps) {
  const router = useRouter();
  const base = `workspaces/${scope}`;
  const [rows, setRows] = useState<Row[]>([]);
  const [numbers, setNumbers] = useState<PhoneNumber[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(0);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");
  const [owner, setOwner] = useState(session.user.display_name);
  const [instructions, setInstructions] = useState("");
  const [createError, setCreateError] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const submitting = useRef(false);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    async function load() {
      try {
        const [list, phones] = await Promise.all([
          api<{ agents: Row[] }>(`${base}/agents`, {
            signal: controller.signal,
          }),
          api<{ numbers: PhoneNumber[] }>(`${base}/numbers`, {
            signal: controller.signal,
          }),
        ]);
        const result = list.agents.slice(page * 20, (page + 1) * 20);
        for (let i = 0; i < result.length; i += 4)
          await Promise.all(
            result.slice(i, i + 4).map(async (row) => {
              const [agent, releases] = await Promise.all([
                api<Agent>(`${base}/agents/${row.id}`, {
                  signal: controller.signal,
                }),
                api<Releases>(`${base}/agents/${row.id}/releases`, {
                  signal: controller.signal,
                }),
              ]);
              row.agent = agent;
              row.releases = releases;
            }),
          );
        if (!controller.signal.aborted) {
          setRows(list.agents);
          setNumbers(phones.numbers);
        }
      } catch (e) {
        if (!controller.signal.aborted) setError(errorMessage(e));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [base, page]);
  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (submitting.current || uncertain) return;
    submitting.current = true;
    setBusy(true);
    setCreateError("");
    try {
      const result = await api<Agent>(`${base}/agents`, {
        csrf: session.csrf_token,
        body: {
          agent_name: name.trim(),
          owner_display_name: owner.trim(),
          owner_address: owner.trim(),
          owner_dative: owner.trim(),
          owner_genitive: owner.trim(),
          instructions,
        },
      });
      setOpen(false);
      router.push(`/agentler/${result.id}`);
    } catch (e) {
      if (!(e instanceof ApiError) || e.status >= 500) {
        setUncertain(true);
        setCreateError(
          "Oluşturma sonucunu doğrulayamadık. Agent kaydedilmiş olabilir. Yeniden oluşturmadan önce agent listesini kontrol et.",
        );
      } else {
        submitting.current = false;
        setCreateError(errorMessage(e));
      }
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Agentlerin</h1>
          <p className="subtitle">
            Sen işine odaklan. Onlar seni temsil etsin.
          </p>
        </div>
        {role !== "viewer" && (
          <Button onClick={() => setOpen(true)} className="h-11">
            <Plus size={17} />
            Agent oluştur
          </Button>
        )}
      </div>
      {error && <Notice error>{error}</Notice>}
      {loading ? (
        <Loading />
      ) : !rows.length ? (
        <div className="empty">
          <AudioLines size={36} />
          <h2 className="text-xl font-semibold mb-2">
            İlk agentinle tanışmaya hazır mısın?
          </h2>
          <p className="muted mb-6">
            Bir isim ve bir görev. Başlamak için bu kadar yeter.
          </p>
          {role !== "viewer" && (
            <Button onClick={() => setOpen(true)}>
              <Plus size={16} />
              İlk agentini oluştur
            </Button>
          )}
        </div>
      ) : (
        <>
          <div className="agent-table">
            <div className="agent-table-header" aria-hidden="true">
              <span>AGENT</span>
              <span className="task-column">GÖREV</span>
              <span>DURUM</span>
              <span>NUMARA</span>
              <span />
            </div>
            {rows.slice(page * 20, (page + 1) * 20).map((row) => {
              const bound = numbers.filter(
                (n) =>
                  n.enabled &&
                  n.status === "verified" &&
                  row.releases?.releases.some((r) => r.id === n.release_id),
              );
              return (
                <Link
                  href={`/agentler/${row.id}`}
                  key={row.id}
                  className="agent-row"
                >
                  <div className="agent-identity">
                    <span className="avatar">{row.name[0]}</span>
                    <div>
                      <div className="agent-name">{row.name}</div>
                      <div className="muted">
                        {row.agent?.content.owner_display_name} · Asistan
                      </div>
                    </div>
                  </div>
                  <span className="task-column muted">
                    {row.agent?.content.role_description ||
                      "Kişisel ses asistanı"}
                  </span>
                  <span>
                    {bound.length ? (
                      <span className="status">
                        <i className="status-dot" />
                        Numaraya bağlı
                      </span>
                    ) : (
                      <Badge variant="outline">
                        {row.releases?.current_release
                          ? "Sürüm hazır"
                          : "Taslak"}
                      </Badge>
                    )}
                  </span>
                  <span className="number-column muted">
                    {bound.length
                      ? bound.map((n) => maskNumber(n.number)).join(", ")
                      : "Numara bağlanmadı"}
                  </span>
                  <ArrowRight size={17} className="row-arrow" />
                </Link>
              );
            })}
          </div>
          {rows.length > 20 && (
            <div className="actions mt-5">
              <Button
                variant="outline"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                Önceki
              </Button>
              <span className="muted">
                {page + 1} / {Math.ceil(rows.length / 20)}
              </span>
              <Button
                variant="outline"
                disabled={(page + 1) * 20 >= rows.length}
                onClick={() => setPage((p) => p + 1)}
              >
                Sonraki
              </Button>
            </div>
          )}
        </>
      )}
      <div className="onboarding">
        <span>
          <FileText size={19} />
          Bir görev ver
        </span>
        <ArrowRight size={16} />
        <span>
          <Phone size={19} />
          Numaranı bağla
        </span>
        <ArrowRight size={16} />
        <span>
          <Play size={19} />
          Yayına al
        </span>
      </div>
      <Dialog
        open={open}
        onOpenChange={(v) => {
          if (!busy) setOpen(v);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Yeni agentin</DialogTitle>
            <DialogDescription>
              Nasıl hitap edelim, kimin adına konuşsun?
            </DialogDescription>
          </DialogHeader>
          <form className="fields" onSubmit={create}>
            <Field
              label="Agent adı"
              value={name}
              onChange={setName}
              maxLength={100}
              required
              placeholder="Örneğin, Deniz"
            />
            <Field
              label="Kimin asistanı?"
              value={owner}
              onChange={setOwner}
              maxLength={100}
              required
            />
            <Field
              label="Görevi"
              value={instructions}
              onChange={setInstructions}
              area
              maxLength={20000}
              required
              placeholder="Arayanları karşıla, iletmek istedikleri mesajları not al…"
            />
            <p className="muted">
              Önce taslak oluşturulur. Numara bağlanana kadar çağrı almaz.
            </p>
            {createError && <Notice error>{createError}</Notice>}
            <Button type="submit" disabled={busy || uncertain}>
              {busy ? "Oluşturuluyor…" : "Agent oluştur"}
              <ArrowRight size={16} />
            </Button>
            {uncertain && (
              <Button
                type="button"
                variant="outline"
                onClick={() => location.reload()}
              >
                Agent listesini kontrol et
              </Button>
            )}
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
