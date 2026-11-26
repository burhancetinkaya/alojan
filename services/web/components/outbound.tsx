"use client";

import { useEffect, useRef, useState } from "react";
import { api, errorMessage, type OutboundSettings } from "@/lib/api";
import { Button } from "./ui/button";
import { Field, SelectField, Notice } from "./shared";
import type { WorkspaceProps } from "./workspace";

type Line = {
  agent_id: string;
  name: string;
  caller: string;
  voice: string;
  settings: OutboundSettings;
};
type Row = {
  id: string;
  agent_name: string;
  destination: string;
  queued_at: string;
  status: string;
};
type Detail = Row & {
  message: string | null;
  caller_e164: string;
  ring_timeout_seconds: number;
  post_playback_seconds: number;
  answered_at: string | null;
  ended_at: string | null;
  failure_code: string | null;
};
const labels: Record<string, string> = {
  queued: "Sırada",
  preparing: "Ses hazırlanıyor",
  dialing: "Aranıyor",
  answered: "Cevaplandı",
  completed: "Anons gönderildi",
  busy: "Meşgul",
  no_answer: "Yanıt yok",
  rejected: "Reddedildi",
  interrupted: "Erken kapandı",
  failed: "Başarısız",
  uncertain: "Sonuç belirsiz",
};
const date = (v: string) => new Date(v).toLocaleString("tr-TR");

export function OutboundPolicy({
  value,
  onChange,
}: {
  value: OutboundSettings;
  onChange: (v: OutboundSettings) => void;
}) {
  return (
    <div className="field">
      <label>
        <input
          type="checkbox"
          checked={value.enabled}
          onChange={(e) => onChange({ ...value, enabled: e.target.checked })}
        />{" "}
        Dış aramaya izin ver
      </label>
      <div className="field-pair">
        <Field
          label="Çalma zaman aşımı (sn)"
          type="number"
          min={1}
          max={120}
          value={String(value.ring_timeout_seconds)}
          onChange={(v) =>
            onChange({ ...value, ring_timeout_seconds: Number(v) })
          }
        />
        <Field
          label="Anons sonrası bekleme (sn)"
          type="number"
          min={0}
          max={30}
          value={String(value.post_playback_seconds)}
          onChange={(v) =>
            onChange({ ...value, post_playback_seconds: Number(v) })
          }
        />
      </div>
    </div>
  );
}

export function Outbound({ scope, session, role }: WorkspaceProps) {
  const base = `workspaces/${scope}/outbound-calls`;
  const [lines, setLines] = useState<Line[]>([]),
    [lineIndex, select] = useState("0");
  const [to, setTo] = useState(""),
    [text, setText] = useState(""),
    [ring, setRing] = useState("30"),
    [wait, setWait] = useState("2");
  const [after, setAfter] = useState(""),
    [next, setNext] = useState(""),
    [rows, setRows] = useState<Row[]>([]);
  const [selected, setSelected] = useState(""),
    [detail, setDetail] = useState<Detail | null>(null);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [receipt, setReceipt] = useState("");
  const [revision, refresh] = useState(0);
  const submission = useRef({ body: "", key: "", sending: false });
  const line = lines[Number(lineIndex)];
  useEffect(() => {
    const ctrl = new AbortController();
    api<{ agents: Line[] }>(base + "/eligible", { signal: ctrl.signal })
      .then((r) => setLines(r.agents))
      .catch((e) => {
        if (!ctrl.signal.aborted) setError(errorMessage(e));
      });
    return () => ctrl.abort();
  }, [base]);
  useEffect(() => {
    if (line) {
      setRing(String(line.settings.ring_timeout_seconds));
      setWait(String(line.settings.post_playback_seconds));
    }
  }, [line]);
  useEffect(() => {
    const ctrl = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const page = await api<{ calls: Row[]; next_cursor: string | null }>(
          base + (after ? "?after=" + after : ""),
          { signal: ctrl.signal },
        );
        if (ctrl.signal.aborted) return;
        setRows(page.calls);
        setNext(page.next_cursor || "");
        if (selected) {
          const item = await api<Detail>(base + "/" + selected, {
            signal: ctrl.signal,
          });
          if (!ctrl.signal.aborted) setDetail(item);
        }
      } catch (e) {
        if (!ctrl.signal.aborted) setError(errorMessage(e));
      }
      if (!ctrl.signal.aborted) timer = setTimeout(load, 4000);
    }
    load();
    return () => {
      ctrl.abort();
      clearTimeout(timer);
    };
  }, [base, after, selected, revision]);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!line || submission.current.sending) return;
    const body = {
      agent_id: line.agent_id,
      caller: line.caller,
      to,
      text,
      ring_timeout_seconds: Number(ring),
      post_playback_seconds: Number(wait),
    };
    const encoded = JSON.stringify(body);
    if (submission.current.body !== encoded)
      submission.current = {
        body: encoded,
        key: crypto.randomUUID(),
        sending: false,
      };
    submission.current.sending = true;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ id: string }>(base, {
        body,
        csrf: session.csrf_token,
        idempotencyKey: submission.current.key,
      });
      setReceipt(result.id);
      setSelected(result.id);
      setDetail(null);
      setAfter("");
      setText("");
      submission.current.body = "";
      refresh((v) => v + 1);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      submission.current.sending = false;
      setBusy(false);
    }
  }
  return (
    <>
      <h1>Outbound</h1>
      <div className="outbound-layout">
      {error && <Notice error>{error}</Notice>}
      {role !== "viewer" && (
        <form className="outbound-panel" onSubmit={submit}>
          <h2 className="section-title">Yeni arama</h2>
          <fieldset className="outbound-fields" disabled={busy || !line}>
            <SelectField
              label="Arayan ajan"
              value={lineIndex}
              onChange={select}
            >
              {lines.map((l, i) => (
                <option key={l.caller} value={String(i)}>
                  {l.name} · {l.caller}
                </option>
              ))}
            </SelectField>
            {line ? (
              <p className="outbound-voice">Seçilen ses · {line.voice === "ema-default" ? "EMA" : line.voice}</p>
            ) : (
              <p>
                Dış arama için yayınlanmış ve doğrulanmış bir hatta bağlı ajan
                gerekiyor.
              </p>
            )}
            <Field
              label="Aranacak telefon"
              type="tel"
              value={to}
              onChange={setTo}
              required
            />
            <Field
              label="Okunacak metin"
              value={text}
              onChange={setText}
              area
              required
              maxLength={2000}
            />
            <div className="field-pair">
              <Field
                label="Çalma zaman aşımı (sn)"
                type="number"
                min={1}
                max={120}
                required
                value={ring}
                onChange={setRing}
              />
              <Field
                label="Anons sonrası bekleme (sn)"
                type="number"
                min={0}
                max={30}
                required
                value={wait}
                onChange={setWait}
              />
            </div>
            <Button type="submit">Aramayı başlat</Button>
          </fieldset>
        </form>
      )}
      <div className="outbound-results">
      {receipt && <div className="outbound-receipt" role="status">Arama sıraya alındı <small>{receipt}</small></div>}
      <section className="outbound-panel">
      <h2 className="section-title">Arama geçmişi</h2>
      {rows.length === 0 ? (
        <p className="muted">Henüz arama yok.</p>
      ) : (
        <div className="outbound-table"><table>
          <thead>
            <tr>
              <th>Ajan</th>
              <th>Numara</th>
              <th>Zaman</th>
              <th>Durum</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} data-selected={r.id === selected}>
                <td>{r.agent_name}</td>
                <td>
                  <button
                    onClick={() => {
                      setDetail(null);
                      setSelected(r.id);
                      refresh((v) => v + 1);
                    }}
                  >
                    {r.destination}
                  </button>
                </td>
                <td>{date(r.queued_at)}</td>
                <td><span className="outbound-status">{labels[r.status]}</span></td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      {after && <Button onClick={() => setAfter("")}>İlk sayfa</Button>}
      {next && <Button onClick={() => setAfter(next)}>Sonraki sayfa</Button>}
      </section>
      {detail && (
        <section className="outbound-panel outbound-detail">
          <h2 className="section-title">Arama detayı</h2>
          <p>
            {detail.agent_name} · {detail.caller_e164} → {detail.destination}
          </p>
          <p>
            <span className="outbound-status">{labels[detail.status]}</span> <small>{detail.id}</small>
          </p>
          <p className="outbound-message">{detail.message}</p>
          <p>
            Çalma zaman aşımı {detail.ring_timeout_seconds} sn · Anons sonrası{" "}
            {detail.post_playback_seconds} sn
          </p>
          {detail.answered_at && <p>Cevaplandı: {date(detail.answered_at)}</p>}
          {detail.ended_at && <p>Bitiş: {date(detail.ended_at)}</p>}
          {detail.failure_code && <p>{detail.failure_code}</p>}
        </section>
      )}
      </div>
      </div>
    </>
  );
}
