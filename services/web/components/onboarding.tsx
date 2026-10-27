"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api, ApiError, errorMessage, type Agent } from "@/lib/api";
import { Field, Loading, Notice } from "./shared";
import { RegistrationLayout } from "./registration-layout";
import type { WorkspaceProps } from "./workspace";

export function Onboarding({ scope, session, role }: WorkspaceProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  const [uncertain, setUncertain] = useState(false);
  const [name, setName] = useState("");
  const [owner, setOwner] = useState(session.user.display_name);
  const [instructions, setInstructions] = useState(
    "Arayanın adını, arama nedenini ve iletmek istediği mesajı not al. Kısa ve nazik konuş.",
  );
  const [agent, setAgent] = useState<Agent | null>(null);
  const [skipped, setSkipped] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const step = agent || skipped ? 3 : 2;
  useEffect(() => {
    const controller = new AbortController();
    api<{ agents: { id: string }[] }>(`workspaces/${scope}/agents`, {
      signal: controller.signal,
    })
      .then(({ agents }) => {
        if (controller.signal.aborted) return;
        // Reload after a completed or uncertain create resumes from saved agents.
        if (agents.length) router.replace("/agentler");
        else setLoading(false);
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          setLoadError(errorMessage(e));
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [scope, router]);
  useEffect(() => {
    if (!loading) heading.current?.focus();
  }, [step, loading]);
  async function create(e: React.FormEvent) {
    e.preventDefault();
    if (submitting.current || uncertain || loading || loadError) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await api<Agent>(`workspaces/${scope}/agents`, {
        csrf: session.csrf_token,
        body: {
          agent_name: name.trim(),
          owner_display_name: owner.trim(),
          owner_address: owner.trim(),
          owner_dative: owner.trim(),
          owner_genitive: `${owner.trim()} adlı kişinin`,
          instructions: instructions.trim(),
        },
      });
      setAgent(result);
    } catch (e) {
      if (!(e instanceof ApiError) || e.status >= 500) {
        setUncertain(true);
        setError(
          "Kayıt sonucunu doğrulayamadık. Yeniden oluşturmadan önce agentlerini kontrol et. Taslağın kaydedilmiş olabilir.",
        );
      } else setError(errorMessage(e));
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }
  return (
    <RegistrationLayout step={step}>
      {loading ? (
        <Loading />
      ) : loadError ? (
        <Notice error>
          {loadError}{" "}
          <button className="text-link" onClick={() => location.reload()}>
            Tekrar dene
          </button>
        </Notice>
      ) : role !== "owner" && role !== "editor" ? (
        <Notice error>
          Agent oluşturmak için düzenleme yetkisi gerekiyor.
        </Notice>
      ) : step === 2 ? (
        <>
          <div className="eyebrow">02 / İlk agentın</div>
          <h2 ref={heading} tabIndex={-1}>
            Ona bir isim ver.
          </h2>
          <p className="muted mb-8">
            Nasıl tanışacağını ve ne yapacağını anlat. Bunları daha sonra
            değiştirebilirsin.
          </p>
          <form onSubmit={create} className="fields">
            <Field
              label="Agentının adı"
              value={name}
              onChange={setName}
              placeholder="Örn. Deniz"
              required
              maxLength={100}
              disabled={busy || uncertain}
            />
            <Field
              label="Kimin asistanı?"
              value={owner}
              onChange={setOwner}
              required
              maxLength={100}
              disabled={busy || uncertain}
            />
            <Field
              label="Arayanlara nasıl yardımcı olsun?"
              value={instructions}
              onChange={setInstructions}
              required
              maxLength={12000}
              area
              rows={4}
              disabled={busy || uncertain}
            />
            <div className="registration-preview">
              <small>KARŞILAMA ÖRNEĞİ · Metin önizlemesi</small>
              Merhaba, ben {name.trim() || "Agentın"}. {owner.trim() || "Senin"}{" "}
              adlı kişinin yapay zekâ asistanıyım.
            </div>
            <p className="muted">
              Ses ve konuşma ayarları hazır gelir. Sesi yayına almadan önce
              hazırlayıp dinleyebilirsin.
            </p>
            {error && <Notice error>{error}</Notice>}
            <Button
              type="submit"
              disabled={busy || uncertain}
              className="w-full h-11"
            >
              {busy ? "Taslağın kaydediliyor…" : "Agent taslağımı oluştur"}
            </Button>
            {!uncertain && (
              <button
                type="button"
                disabled={busy}
                className="text-link registration-skip"
                onClick={() => setSkipped(true)}
              >
                Şimdilik atla
              </button>
            )}
          </form>
        </>
      ) : skipped ? (
        <>
          <div className="eyebrow">Kişisel alanın hazır</div>
          <h2 ref={heading} tabIndex={-1}>
            İstediğinde başlayalım.
          </h2>
          <p className="muted mb-8">
            Hesabın hazır. Henüz bir agent oluşturmadın. İlk agentını şimdi
            hazırlayabilir veya daha sonra devam edebilirsin.
          </p>
          <Button className="w-full h-11" onClick={() => setSkipped(false)}>
            İlk agentımı oluştur
          </Button>
        </>
      ) : (
        agent && (
          <>
            <div className="eyebrow">03 / Sıradaki adımlar</div>
            <h2 ref={heading} tabIndex={-1}>
              {agent.content.agent_name} ile başlayalım.
            </h2>
            <Badge variant="outline">Taslak · Henüz çağrı karşılamıyor</Badge>
            <p className="muted mt-4">
              İlk agentın için bir başlangıç hazırladık. Yayına almadan önce son
              ayarlarını tamamla.
            </p>
            <ol className="registration-tasks">
              <li>
                <span>01</span>
                <div>
                  <Link className="text-link" href={`/agentler/${agent.id}`}>
                    Sesini hazırla, dinle.
                  </Link>
                  <p>
                    Karşılamasını kontrol et. Talimatlarını, araçlarını ve model
                    bağlantısını düzenle.
                  </p>
                </div>
              </li>
              <li>
                <span>02</span>
                <div>
                  <Link className="text-link" href="/numaralar">
                    0850 numaranı tanımla.
                  </Link>
                  <p>
                    Netgsm numaranı ekle. Sana ait olduğu ve yönlendirmesi
                    doğrulansın.
                  </p>
                </div>
              </li>
              <li>
                <span>03</span>
                <div>
                  <Link className="text-link" href="/baglantilar">
                    Bildirimlerini seç.
                  </Link>
                  <p>
                    İstersen Telegram bağlantını ekle, ardından agentının çağrı
                    sonrası ayarlarından hedefi ve gönderim iznini belirle.
                  </p>
                </div>
              </li>
            </ol>
            <Notice>
              Agent hazır olduğunda sürümünü yayınla, ardından doğrulanmış
              numarana bağla.
            </Notice>
            <Button asChild className="w-full h-11 mt-6">
              <Link href={`/agentler/${agent.id}`}>Agentımı düzenle</Link>
            </Button>
          </>
        )
      )}
      <p className="muted mt-6 text-center">
        <Link href="/agentler" className="text-link">
          Çalışma alanına git
        </Link>
      </p>
    </RegistrationLayout>
  );
}
