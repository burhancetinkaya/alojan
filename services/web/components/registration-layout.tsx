import { Brand } from "./shared";

export function RegistrationLayout({
  step,
  children,
}: {
  step: number;
  children: React.ReactNode;
}) {
  return (
    <main className="auth-page registration-page">
      <section className="auth-story">
        <Brand />
        <h1>
          İlk agentınla
          <br />
          tanışmaya
          <br />
          hazır mısın?
        </h1>
        <p>
          Sen işine odaklan.
          <br />
          Aramalarını karşılayacak bir yardımcın olsun.
        </p>
        <ol className="registration-steps" aria-label="Kayıt adımları">
          {["Hesabını oluştur", "Agentını tanıt", "Hazırlamaya başla"].map(
            (label, i) => (
              <li
                key={label}
                aria-current={step === i + 1 ? "step" : undefined}
              >
                <span>0{i + 1}</span>
                {label}
              </li>
            ),
          )}
        </ol>
        <div className="auth-footer">
          Kişisel alanın. Kontrol her zaman sende.
        </div>
      </section>
      <section className="auth-form">{children}</section>
    </main>
  );
}
