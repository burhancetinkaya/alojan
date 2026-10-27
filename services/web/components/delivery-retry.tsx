"use client";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { ApiError, api, errorMessage } from "@/lib/api";
import { Notice } from "./shared";

type Review = {
  review_digest: string;
  can_retry: boolean;
  blocked_reason: string | null;
  warning: string;
  review: {
    action: {
      connection_label: string;
      chat_id?: string;
      endpoint?: string;
      method?: string;
      alias: string;
    };
    message_text: string;
    job: { status: string };
  };
};
const reasons: Record<string, string> = {
  retry_already_requested: "Bu bildirim için yeniden deneme zaten sırada.",
  delivery_not_retryable:
    "Bildirimin mevcut durumu yeniden denemeye uygun değil.",
  manual_retry_limit: "Bu bildirim için yeniden deneme sınırına ulaşıldı.",
  action_grant_required:
    "Gönderim izni artık geçerli değil. Agent'ın izinlerini kontrol edin.",
  invalid_action_intent:
    "Bildirim hedefi veya gönderim izni artık geçerli değil.",
  http_connection_unavailable: "HTTP bağlantısı artık kullanılamıyor.",
  telegram_connection_unavailable: "Telegram bağlantısı artık kullanılamıyor.",
};
export function DeliveryRetry({
  scope,
  profile,
  job,
  csrf,
  onAccepted,
}: {
  scope: string;
  profile: string;
  job: string;
  csrf: string;
  onAccepted: () => void;
}) {
  const base = `workspaces/${scope}/agents/${profile}/deliveries/${job}`;
  const [open, setOpen] = useState(false);
  const [review, setReview] = useState<Review | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [invalid, setInvalid] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [reload, setReload] = useState(0);
  const request = useRef("");
  const submitting = useRef(false);
  useEffect(() => {
    if (!open) return;
    const c = new AbortController();
    setLoading(true);
    setReview(null);
    setAccepted(false);
    setError("");
    setInvalid(false);
    setUncertain(false);
    api<Review>(`${base}/retry-review`, { signal: c.signal })
      .then((r) => {
        if (!c.signal.aborted) {
          request.current = crypto.randomUUID();
          setReview(r);
        }
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      })
      .finally(() => {
        if (!c.signal.aborted) setLoading(false);
      });
    return () => c.abort();
  }, [open, base, reload]);
  async function submit() {
    if (submitting.current || !review?.can_retry || !accepted || invalid)
      return;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      // Keep this ID after a lost response: a repeated click replays the same consent.
      await api(`${base}/retry`, {
        body: {
          request_id: request.current,
          review_digest: review.review_digest,
          accept_duplicate_risk: true,
        },
        csrf,
      });
      setOpen(false);
      onAccepted();
    } catch (e) {
      setError(errorMessage(e));
      if (e instanceof ApiError && e.status < 500) {
        setInvalid(true);
        setAccepted(false);
      } else setUncertain(true);
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!submitting.current) setOpen(value);
      }}
    >
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          Yeniden gönderimi incele
        </Button>
      </DialogTrigger>
      <DialogContent
        className="w-[calc(100vw_-_2rem)] max-h-[90dvh] overflow-y-auto [overflow-wrap:anywhere]"
        showCloseButton={!busy}
      >
        <DialogHeader>
          <DialogTitle>Yeniden gönderim onayı</DialogTitle>
          <DialogDescription>
            Aynı çağrının kayıtlı bildirimi, aşağıdaki hedefe yeniden
            gönderilecek.
          </DialogDescription>
        </DialogHeader>
        {loading && <p role="status">Gönderim bilgileri yükleniyor…</p>}
        {error && <Notice error>{error}</Notice>}
        {review && (
          <>
            <dl>
              <dt className="muted">
                {review.review.action.endpoint
                  ? "HTTP bağlantısı"
                  : "Telegram bağlantısı"}
              </dt>
              <dd>{review.review.action.connection_label}</dd>
              <dt className="muted mt-3">
                {review.review.action.endpoint
                  ? "Hedef adres"
                  : "Sohbet kimliği"}
              </dt>
              <dd>
                {review.review.action.endpoint
                  ? `${review.review.action.method} ${review.review.action.endpoint}`
                  : review.review.action.chat_id}
              </dd>
            </dl>
            <div>
              <p className="font-semibold">
                {review.review.action.endpoint
                  ? "Gönderilecek HTTP isteği"
                  : "Gönderilecek mesaj"}
              </p>
              <pre className="whitespace-pre-wrap font-sans text-sm border rounded-md p-4 max-h-64 overflow-y-auto">
                {review.review.message_text}
              </pre>
            </div>
            <Notice>{review.warning}</Notice>
            {!review.can_retry && (
              <Notice error>
                {reasons[review.blocked_reason || ""] ||
                  "Gönderim izni veya bağlantı kullanılamıyor. Ayarları kontrol edin."}
              </Notice>
            )}
            {review.can_retry && !invalid && (
              <label className="flex gap-3 items-start text-sm">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={accepted}
                  disabled={busy}
                  onChange={(e) => setAccepted(e.target.checked)}
                />
                Hedefi ve mesajı kontrol ettim; aynı mesajın iki kez
                ulaşabileceğini kabul ediyorum.
              </label>
            )}
          </>
        )}
        {uncertain && (
          <Notice>
            İstek alınmış olabilir. Tekrar denerseniz aynı onay isteği kontrol
            edilir; yeni bir gönderim isteği oluşturulmaz.
          </Notice>
        )}
        <DialogFooter>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => setOpen(false)}
          >
            Vazgeç
          </Button>
          {!review || invalid || !review.can_retry ? (
            <Button
              variant="outline"
              disabled={busy || loading}
              onClick={() => setReload((r) => r + 1)}
            >
              Bilgileri yenile
            </Button>
          ) : (
            <Button disabled={!accepted || busy || loading} onClick={submit}>
              {busy
                ? "İstek kaydediliyor…"
                : uncertain
                  ? "Aynı isteği tekrar dene"
                  : "Bu bildirimi yeniden gönder"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
