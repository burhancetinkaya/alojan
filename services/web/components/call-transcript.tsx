"use client";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { Notice } from "./shared";

type Page = {
  utterances: {
    id: string;
    speaker: "caller" | "assistant";
    kind?: "response" | "waiting";
    text: string;
    created_at: string;
  }[];
  next_cursor: string | null;
};
export function CallTranscript({ scope, id }: { scope: string; id: string }) {
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [data, setData] = useState<Page | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!open) return;
    const c = new AbortController();
    setLoading(true);
    setData(null);
    setError("");
    api<Page>(
      `workspaces/${scope}/calls/${id}/transcript${cursor ? `?after=${encodeURIComponent(cursor)}` : ""}`,
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
  }, [open, scope, id, cursor, refresh]);
  return (
    <section className="form-panel" aria-labelledby="call-transcript">
      <h2 className="section-title" id="call-transcript">
        Görüşme dökümü
      </h2>
      <p className="muted">
        Konuşma tanımada hatalar olabilir. Agent metinleri yalnızca gönderilen
        sesle eşleştirilen bölümleri içerir; arayanın duyduğunu kesin olarak
        göstermez.
      </p>
      <div className="actions">
        <Button
          variant="outline"
          aria-expanded={open}
          aria-controls="transcript-content"
          onClick={() => {
            setOpen(!open);
            setCursor("");
            setData(null);
          }}
        >
          {open ? "Dökümü gizle" : "Dökümü göster"}
        </Button>
        {open && (
          <Button
            variant="outline"
            disabled={loading}
            onClick={() => {
              setCursor("");
              setRefresh((r) => r + 1);
            }}
          >
            Dökümü yenile
          </Button>
        )}
      </div>
      {open && (
        <div id="transcript-content" className="mt-6" aria-busy={loading}>
          {error && <Notice error>{error}</Notice>}
          {loading ? (
            <p role="status">Döküm yükleniyor…</p>
          ) : (
            data && (
              <>
                {data.utterances.length ? (
                  <ol className="list-none m-0 p-0">
                    {data.utterances.map((u) => (
                      <li key={u.id} className="py-4 border-b">
                        <div className="actions mb-2">
                          <strong>
                            {u.speaker === "caller" ? "Arayan" : u.kind === "waiting" ? "Agent · Bekleme" : "Agent"}
                          </strong>
                          <time className="muted" dateTime={u.created_at}>
                            {new Date(u.created_at).toLocaleTimeString("tr-TR")}
                          </time>
                        </div>
                        <p className="whitespace-pre-wrap [overflow-wrap:anywhere] mb-0">
                          {u.text ||
                            "Ses gönderildi; bu bölüm için doğrulanmış metin yok."}
                        </p>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="muted">
                    Bu görüşme için gösterilebilir konuşma kaydı yok.
                  </p>
                )}
                <div className="actions mt-6">
                  {cursor && (
                    <Button variant="outline" onClick={() => setCursor("")}>
                      Başa dön
                    </Button>
                  )}
                  {data.next_cursor && (
                    <Button
                      variant="outline"
                      onClick={() => setCursor(data.next_cursor!)}
                    >
                      Sonraki konuşmalar
                    </Button>
                  )}
                </div>
              </>
            )
          )}
        </div>
      )}
    </section>
  );
}
