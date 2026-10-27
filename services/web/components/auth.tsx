"use client";
import { useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, ShieldCheck, AudioLines } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Brand, Field, Notice } from "./shared";
import { RegistrationLayout } from "./registration-layout";
import { api, ApiError, errorMessage, type Session } from "@/lib/api";

export function Auth({
  register,
  onSession,
}: {
  register: boolean;
  onSession: (s: Session) => void;
}) {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [recovery, setRecovery] = useState(false);
  const [visible, setVisible] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const submitting = useRef(false);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting.current || uncertain) return;
    submitting.current = true;
    setBusy(true);
    setError("");
    try {
      const session = await api<Session>(
        `auth/${register ? "register" : "login"}`,
        {
          body: {
            login: login.trim(),
            password,
            ...(register ? { display_name: name.trim() } : {}),
          },
        },
      );
      setPassword("");
      onSession(session);
    } catch (e) {
      if (register && (!(e instanceof ApiError) || e.status >= 500)) {
        try {
          const session = await api<Session>("auth/session");
          setPassword("");
          onSession(session);
        } catch {
          setUncertain(true);
          setPassword("");
          setError(
            "Kayıt sonucunu doğrulayamadık. Hesabın oluşmuş olabilir. Tekrar kayıt olmadan önce giriş yapmayı dene.",
          );
        }
      } else setError(errorMessage(e));
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }
  const form = (
    <>
      {register && <div className="eyebrow">01 / Hesabın</div>}
      <h2>{register ? "Kendi alanını oluştur." : "Tekrar hoş geldin"}</h2>
      <p className="muted mb-8">
        {register
          ? "Önce hesabını aç. Bir sonraki adımda ilk agentına bir isim vereceğiz."
          : "Agentlerin kaldığın yerden devam etmeye hazır."}
      </p>
      <form onSubmit={submit} className="fields">
        {register && (
          <Field
            label="Adın soyadın"
            value={name}
            onChange={setName}
            required
            maxLength={100}
            autoComplete="name"
          />
        )}
        <Field
          label="E-posta"
          value={login}
          onChange={setLogin}
          type="email"
          required
          maxLength={254}
          autoComplete="username"
        />
        <div className={register ? "registration-password" : undefined}>
          <Field
            label="Şifre"
            value={password}
            onChange={setPassword}
            type={visible ? "text" : "password"}
            required
            minLength={register ? 8 : undefined}
            maxLength={128}
            autoComplete={register ? "new-password" : "current-password"}
            hint={
              register
                ? "En az 8 karakter. Birkaç kelimelik bir ifade kullanabilirsin."
                : undefined
            }
          />
          {register && (
            <button
              type="button"
              aria-label={visible ? "Şifreyi gizle" : "Şifreyi göster"}
              aria-pressed={visible}
              onClick={() => setVisible(!visible)}
            >
              {visible ? "Gizle" : "Göster"}
            </button>
          )}
        </div>
        {error && <Notice error>{error}</Notice>}
        <Button
          disabled={busy || uncertain}
          type="submit"
          className="w-full h-11"
        >
          {busy ? "Bir saniye…" : register ? "Hesap oluştur" : "Giriş yap"}
          <ArrowRight size={16} />
        </Button>
      </form>
      <p className="muted mt-6 text-center">
        {register ? "Zaten hesabın var mı? " : "Henüz hesabın yok mu? "}
        <Link className="text-link" href={register ? "/giris" : "/kayit"}>
          {register ? "Giriş yap" : "Hesap oluştur"}
        </Link>
      </p>
      {!register && (
        <>
          <button
            className="text-link mt-3"
            onClick={() => setRecovery(!recovery)}
          >
            Şifremi unuttum
          </button>
          {recovery && (
            <Notice>
              Şifre yenileme şu an Alojan yöneticisi tarafından yapılıyor.
              Mevcut agentine erişmek için yeni hesap açmak yerine yöneticinden
              hesabını yenilemesini iste.
            </Notice>
          )}
        </>
      )}
      <p className="muted flex items-center justify-center gap-2 mt-10">
        <ShieldCheck size={15} />
        Sadece kendi agentlerine ve verilerine erişirsin.
      </p>
    </>
  );
  if (register) return <RegistrationLayout step={1}>{form}</RegistrationLayout>;
  return (
    <main className="auth-page">
      <section className="auth-story">
        <Brand />
        <h1>
          Senin adına.
          <br />
          Senin gibi.
        </h1>
        <p>
          Aramalarını karşılayan, mesajlarını toplayan kişisel agentlerinle
          tanış.
        </p>
        <div className="mt-12 flex gap-3 items-center text-primary">
          <AudioLines size={30} />
          <span>Bir görev ver. Gerisini birlikte halledelim.</span>
        </div>
        <div className="auth-footer">
          Kişisel alanın. Kontrol her zaman sende.
        </div>
      </section>
      <section className="auth-form">{form}</section>
    </main>
  );
}
