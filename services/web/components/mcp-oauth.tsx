"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { api, errorMessage, type Session } from "@/lib/api";
import { Field, Notice, SelectField } from "./shared";

type Provider = {
  id: string;
  label: string;
  resource: string;
  issuer: string;
  authorization_endpoint: string;
  scopes: string[];
};

export function MCPOAuth({ base, csrf }: { base: string; csrf: string }) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [selected, setSelected] = useState("");
  const [label, setLabel] = useState("");
  const [review, setReview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const submitting = useRef(false);
  const provider = providers.find((p) => p.id === selected);
  useEffect(() => {
    const c = new AbortController();
    api<{ providers: Provider[] }>(`${base}/mcp-oauth`, { signal: c.signal })
      .then((v) => {
        if (!c.signal.aborted) setProviders(v.providers || []);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      });
    return () => c.abort();
  }, [base]);
  async function connect() {
    if (!provider || submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await api<{ authorization_url: string }>(
        `${base}/mcp-oauth`,
        { csrf, body: { provider_id: provider.id, label } },
      );
      const target = new URL(result.authorization_url);
      const approved = new URL(provider.authorization_endpoint);
      if (
        target.protocol !== "https:" ||
        target.username ||
        target.password ||
        target.hash ||
        target.origin !== approved.origin ||
        target.pathname !== approved.pathname
      )
        throw new Error("OAuth destination mismatch");
      window.location.assign(target.href);
    } catch (e) {
      setError(errorMessage(e));
      setReview(false);
      setBusy(false);
      submitting.current = false;
    }
  }
  return (
    <section
      className="form-panel fields max-w-xl mt-6"
      aria-label="OAuth hesabı bağla"
    >
      <h3 className="font-semibold">Hesabını bağla · OAuth</h3>
      <p className="muted">
        Şifreni Alojan'a vermeden, sağlayıcının kendi sayfasından giriş yap.
      </p>
      {error && <Notice error>{error}</Notice>}
      {!providers.length ? (
        <p className="muted">Henüz OAuth sağlayıcısı tanımlanmamış.</p>
      ) : (
        <form
          className="fields"
          onSubmit={(e) => {
            e.preventDefault();
            setError("");
            setReview(true);
          }}
        >
          <fieldset disabled={busy} className="fields">
            <SelectField
              label="OAuth sağlayıcısı"
              value={selected}
              onChange={setSelected}
            >
              <option value="">Sağlayıcı seç</option>
              {providers.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </SelectField>
            <Field
              label="OAuth bağlantı adı"
              required
              maxLength={80}
              value={label}
              onChange={setLabel}
            />
            <Button type="submit" disabled={!provider}>
              Bağlantıyı incele
            </Button>
          </fieldset>
        </form>
      )}
      <Dialog
        open={review}
        onOpenChange={(v) => {
          if (!busy) setReview(v);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Hesabını bağla</DialogTitle>
            <DialogDescription>
              Bu sağlayıcının giriş sayfasına geçeceksin. Hesabını bağlamak
              agentına araç çalıştırma izni vermez; araçları ve izinlerini
              ayrıca seçersin.
            </DialogDescription>
          </DialogHeader>
          {provider && (
            <div className="fields break-words">
              <strong>{provider.label}</strong>
              <p className="text-sm break-all">
                Giriş sağlayıcısı: {provider.issuer}
              </p>
              <p className="text-sm break-all">
                Giriş sayfası: {provider.authorization_endpoint}
              </p>
              <p className="text-sm break-all">
                Bilgi kaynağı: {provider.resource}
              </p>
              <p className="text-sm">
                İstenen erişimler: {provider.scopes.join(", ")}
              </p>
            </div>
          )}
          <div className="actions">
            <Button disabled={busy} onClick={connect}>
              {busy ? "Yönlendiriliyor…" : "Sağlayıcıya git ve bağla"}
            </Button>
            <Button
              variant="outline"
              disabled={busy}
              onClick={() => setReview(false)}
            >
              Vazgeç
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}

export function MCPOAuthCallback() {
  const started = useRef(false);
  const [status, setStatus] = useState("Bağlantın tamamlanıyor…");
  const [error, setError] = useState(false);
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    const query = new URLSearchParams(window.location.search);
    // Strict session cookies are sent by the subsequent same-origin fetch, not the cross-site return.
    window.history.replaceState(null, "", "/mcp-donus");
    async function finish() {
      try {
        const keys = [...query.keys()];
        if (
          keys.length !== new Set(keys).size ||
          keys.some(
            (k) =>
              ![
                "state",
                "code",
                "iss",
                "error",
                "error_description",
                "error_uri",
                "session_state",
              ].includes(k),
          ) ||
          query.has("error")
        )
          throw new Error("OAuth return declined");
        const state = query.get("state") || "";
        const scope = state.match(
          /^([a-f0-9-]{36})\.[a-f0-9-]{36}\.[A-Za-z0-9_-]{43}$/,
        )?.[1];
        if (!scope || !query.get("code") || !query.get("iss"))
          throw new Error("Invalid OAuth return");
        const session = await api<Session>("auth/session");
        if (
          !session.workspaces.some((w) => w.id === scope && w.role === "owner")
        )
          throw new Error("OAuth workspace unavailable");
        await api(`workspaces/${scope}/mcp-oauth/complete`, {
          csrf: session.csrf_token,
          body: { state, code: query.get("code"), issuer: query.get("iss") },
        });
        setStatus(
          "Hesabın bağlandı. Bağlantılar ekranından araç listesini tarayıp agentına ekleyebilirsin.",
        );
      } catch {
        setError(true);
        setStatus(
          "Bağlantı tamamlanamadı veya sonuç alınamadı. Bağlantılarını kontrol et; kayıt yoksa aynı hesapla giriş yapıp yeniden başlat.",
        );
      }
    }
    void finish();
  }, []);
  return (
    <main className="mx-auto max-w-xl p-6 pt-20 fields">
      <h1 className="page-title">Hesap bağlantısı</h1>
      <Notice error={error}>{status}</Notice>
      <Link className="text-link" href="/baglantilar">
        Bağlantılarıma dön
      </Link>
    </main>
  );
}
