"use client";
import { ConnectionSetup } from "./connection-setup";
import { PersonalTokens } from "./personal-tokens";
import { Performance } from "./performance";
import { Calls, CallDetail } from "./calls";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import {
  AudioLines,
  Gauge,
  Phone,
  History,
  Unplug,
  ChevronRight,
  Menu,
  X,
  LogOut,
  ArrowLeft,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { api, ApiError, errorMessage, type Session } from "@/lib/api";
import { Auth } from "./auth";
import { Onboarding } from "./onboarding";
import { Brand, Loading, Notice, SelectField, Field } from "./shared";
import { AgentList } from "./agent-list";
import { AgentEditor } from "./agent-editor";
import { useDraftMemory } from "./draft-memory";
import { Numbers, Connections } from "./workspace-resources";

export type WorkspaceProps = { session: Session; scope: string; role: string };
const navigation = [
  { href: "/agentler", label: "Agentler", icon: AudioLines },
  { href: "/numaralar", label: "Numaralar", icon: Phone },
  { href: "/aramalar", label: "Aramalar", icon: History },
  { href: "/performans", label: "Performans", icon: Gauge },
  { href: "/baglantilar", label: "Bağlantılar", icon: Unplug },
  { href: "/mcp-erisim", label: "MCP erişimi", icon: Unplug },
];
export function Workspace() {
  const memory = useDraftMemory();
  const pathname = usePathname();
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [scope, setScope] = useState("");
  const [mobile, setMobile] = useState(false);
  const setupRoute = pathname.match(
    /^\/baglanti-kur\/([a-f0-9-]{36})\/([a-f0-9-]{36})$/,
  );
  function initialScope(s: Session) {
    return setupRoute && s.workspaces.some((w) => w.id === setupRoute[1])
      ? setupRoute[1]
      : s.workspaces[0]?.id || "";
  }
  function accept(s: Session) {
    memory.drafts.clear();
    memory.session = s.csrf_token;
    setSession(s);
    setScope(initialScope(s));
    router.replace(
      setupRoute
        ? pathname
        : pathname === "/kayit"
          ? "/baslangic"
          : "/agentler",
    );
  }
  useEffect(() => {
    const controller = new AbortController();
    api<Session>("auth/session", { signal: controller.signal })
      .then((s) => {
        if (controller.signal.aborted) return;
        if (memory.session !== s.csrf_token) memory.drafts.clear();
        memory.session = s.csrf_token;
        setSession(s);
        setScope(initialScope(s));
      })
      .catch((e) => {
        if (
          !controller.signal.aborted &&
          e instanceof ApiError &&
          e.status === 401
        ) {
          memory.drafts.clear();
          memory.session = null;
        }
        if (
          !controller.signal.aborted &&
          !(e instanceof ApiError && e.status === 401)
        )
          setError(errorMessage(e));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    const expired = () => {
      memory.drafts.clear();
      memory.session = null;
      setSession(null);
      setScope("");
      router.replace("/giris");
    };
    window.addEventListener("alojan-session-expired", expired);
    return () => {
      controller.abort();
      window.removeEventListener("alojan-session-expired", expired);
    };
  }, [router, memory]);
  useEffect(() => {
    setMobile(false);
  }, [pathname]);
  async function logout() {
    try {
      await api("auth/logout", { body: {}, csrf: session?.csrf_token });
      memory.drafts.clear();
      memory.session = null;
      setSession(null);
      setScope("");
      router.replace("/giris");
    } catch (e) {
      setError(errorMessage(e));
    }
  }
  if (loading) return <Loading />;
  if (!session)
    return (
      <>
        {error && (
          <Notice error>
            {error}{" "}
            <button className="text-link" onClick={() => location.reload()}>
              Tekrar dene
            </button>
          </Notice>
        )}
        <Auth
          key={pathname}
          register={pathname === "/kayit"}
          onSession={accept}
        />
      </>
    );
  const selected = session.workspaces.find((w) => w.id === scope);
  const props = { session, scope, role: selected?.role || "viewer" };
  if (pathname === "/baslangic" && scope)
    return <Onboarding key={scope} {...props} />;
  const agentId = pathname.match(/^\/agentler\/([a-f0-9-]{36})$/)?.[1];
  return (
    <>
      <a href="#main-content" className="skip-link">
        İçeriğe geç
      </a>
      <div className="shell">
        <aside
          className={`sidebar${mobile ? " open" : ""}`}
          aria-label="Ana gezinme"
        >
          <Link href="/agentler">
            <Brand />
          </Link>
          <div className="workspace-label">
            {session.workspaces.length > 1 ? (
              <SelectField
                label="Çalışma alanı"
                value={scope}
                onChange={(s) => {
                  setScope(s);
                  router.push("/agentler");
                }}
              >
                {session.workspaces.map((w) => (
                  <option key={w.id} value={w.id}>
                    {w.name}
                  </option>
                ))}
              </SelectField>
            ) : (
              "Kişisel alan"
            )}
          </div>
          <nav>
            {navigation.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={
                  pathname.startsWith(item.href) ? "page" : undefined
                }
                className={`nav-link${pathname.startsWith(item.href) || (item.href === "/agentler" && pathname === "/") ? " active" : ""}`}
              >
                <item.icon aria-hidden="true" />
                {item.label}
              </Link>
            ))}
          </nav>
          <Link href="/hesap" className="account">
            <span className="avatar">
              {session.user.display_name?.[0] || "A"}
            </span>
            <div className="min-w-0">
              <div className="truncate">{session.user.display_name}</div>
              <div className="muted">Hesap ayarları</div>
            </div>
            <ChevronRight size={16} className="ml-auto" />
          </Link>
        </aside>
        <div>
          <div className="mobile-header">
            <Button
              variant="ghost"
              size="icon"
              aria-label={mobile ? "Menüyü kapat" : "Menüyü aç"}
              onClick={() => setMobile(!mobile)}
            >
              {mobile ? <X /> : <Menu />}
            </Button>
            <Brand />
          </div>
          {mobile && (
            <button
              className="fixed inset-0 bg-black/20 z-30"
              aria-label="Menüyü kapat"
              onClick={() => setMobile(false)}
            />
          )}
          <main className="main" id="main-content">
            <div className="eyebrow">
              <ArrowLeft size={14} />
              <Link href="/agentler">
                {agentId ? "Agentler" : "ÇALIŞMA ALANIN"}
              </Link>
              {agentId && <span>/ Düzenle</span>}
            </div>
            {error && <Notice error>{error}</Notice>}
            {!scope ? (
              <Notice error>
                Bu hesapta erişilebilir bir çalışma alanı yok.
              </Notice>
            ) : (
              <div key={`${scope}:${pathname}`}>
                {setupRoute ? (
                  <ConnectionSetup
                    {...props}
                    scope={setupRoute[1]}
                    id={setupRoute[2]}
                  />
                ) : agentId ? (
                  <AgentEditor {...props} id={agentId} />
                ) : pathname === "/numaralar" ? (
                  <Numbers {...props} />
                ) : pathname === "/baglantilar" ? (
                  <Connections {...props} />
                ) : pathname === "/aramalar" ? (
                  <Calls {...props} />
                ) : /^\/aramalar\/[a-f0-9-]{36}$/.test(pathname) ? (
                  <CallDetail {...props} id={pathname.split("/")[2]} />
                ) : pathname === "/performans" ? (
                  <Performance scope={scope} />
                ) : pathname === "/mcp-erisim" ? (
                  <PersonalTokens {...props} />
                ) : pathname === "/hesap" ? (
                  <Account session={session} logout={logout} />
                ) : ["/", "/agentler", "/giris", "/kayit"].includes(
                    pathname,
                  ) ? (
                  <AgentList {...props} />
                ) : (
                  <Notice error>
                    Bu sayfa bulunamadı.{" "}
                    <Link href="/agentler" className="text-link">
                      Agentlerine dön
                    </Link>
                  </Notice>
                )}
              </div>
            )}
          </main>
        </div>
      </div>
    </>
  );
}
function Account({
  session,
  logout,
}: {
  session: Session;
  logout: () => void;
}) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("auth/password", {
        body: { current_password: current, new_password: next },
        csrf: session.csrf_token,
      });
      window.dispatchEvent(new Event("alojan-session-expired"));
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Hesabın</h1>
          <p className="subtitle">{session.user.login}</p>
        </div>
        <Button variant="outline" onClick={logout}>
          <LogOut size={16} />
          Çıkış yap
        </Button>
      </div>
      <form className="fields max-w-lg" onSubmit={submit}>
        <h2 className="section-title">Şifreni değiştir</h2>
        <Field
          label="Mevcut şifre"
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={setCurrent}
          required
        />
        <Field
          label="Yeni şifre"
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={setNext}
          required
          minLength={8}
          maxLength={128}
          hint="En az 8 karakter. Değişiklikten sonra yeniden giriş yapacaksın."
        />
        {error && <Notice error>{error}</Notice>}
        <Button disabled={busy} type="submit">
          {busy ? "Kaydediliyor…" : "Şifreyi değiştir"}
        </Button>
      </form>
    </>
  );
}
