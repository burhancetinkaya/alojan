"use client";
import { ActionConditionField } from "./action-condition";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, SelectField, Notice } from "./shared";
import type { Action, HTTPConnection, HTTPValue } from "@/lib/api";

export function HTTPActionEditor({
  action,
  connections,
  fields,
  labels,
  index,
  onChange,
  onRemove,
}: {
  action: Action;
  connections: HTTPConnection[];
  fields: string[];
  labels: Record<string, string>;
  index: number;
  onChange: (a: Action) => void;
  onRemove: () => void;
}) {
  const [error, setError] = useState("");
  function patch(p: Partial<Action>) {
    setError("");
    onChange({ ...action, ...p });
  }
  function mapping(group: "body" | "query", name: string, value: HTTPValue) {
    const next = { ...action[group], [name]: value };
    const combined = {
      body: action.body || {},
      query: action.query || {},
      [group]: next,
    };
    const sources = [
      ...Object.values(combined.body),
      ...Object.values(combined.query),
    ]
      .filter(
        (v): v is Extract<HTTPValue, { kind: "source" }> => v.kind === "source",
      )
      .map((v) => v.source);
    const required = sources.flatMap((s) =>
      s.startsWith("outputs.")
        ? ["output_status." + s.split(".")[1]]
        : s.startsWith("summary.")
          ? ["summary_status"]
          : ["called_number", "caller_number"].includes(s)
            ? [s + "_source"]
            : [],
    );
    for (const source of new Set(required))
      if (!sources.includes(source)) {
        let key = source.replaceAll(".", "_");
        let n = 1;
        while (key in combined.body)
          key = source.replaceAll(".", "_") + "_" + n++;
        combined.body = {
          ...combined.body,
          [key]: { kind: "source", source, on_missing: "null" },
        };
      }
    if (Object.keys(combined.body).length > 16) {
      setError(
        "Durum ve kaynak alanlarıyla birlikte en fazla 16 gövde alanı ekleyebilirsin.",
      );
      return;
    }
    patch(combined);
  }
  function rename(group: "body" | "query", old: string, name: string) {
    if (name !== old && name in (action[group] || {})) {
      setError("Alan adları benzersiz olmalı.");
      return;
    }
    patch({
      [group]: Object.fromEntries(
        Object.entries(action[group] || {}).map(([k, v]) => [
          k === old ? name : k,
          v,
        ]),
      ),
    });
  }
  function add(group: "body" | "query") {
    const values = action[group] || {};
    let n = 1;
    while (`field_${n}` in values) n++;
    mapping(group, `field_${n}`, {
      kind: "source",
      source: "call_id",
      on_missing: "fail",
    });
  }
  function transcript(enabled: boolean) {
    const body = Object.fromEntries(
      Object.entries(action.body || {}).filter(
        ([, v]) => !(v.kind === "source" && v.source.startsWith("transcript.")),
      ),
    );
    if (enabled) {
      if (Object.keys(body).length > 14) {
        setError("Konuşma dökümü ve durum bilgisi için iki gövde alanı ayır.");
        return;
      }
      for (const source of ["transcript.text", "transcript.status"]) {
        let key = source.replaceAll(".", "_");
        let n = 1;
        while (key in body) key = source.replaceAll(".", "_") + "_" + n++;
        body[key] = { kind: "source", source, on_missing: "null" };
      }
    }
    if (!Object.keys(body).length)
      body.call_id = { kind: "source", source: "call_id", on_missing: "fail" };
    patch({ transcript_policy: enabled ? "bounded_text.v1" : undefined, body });
  }
  const availableFields = action.transcript_policy
    ? [...fields, "transcript.text", "transcript.status"]
    : fields;
  const target = connections.find((c) => c.id === action.connection_id);
  return (
    <section
      className="form-panel fields"
      aria-label={`HTTP işlemi ${index + 1}`}
    >
      <div className="flex justify-between gap-3">
        <strong>HTTP isteği {index + 1}</strong>
        <Button
          type="button"
          variant="ghost"
          onClick={onRemove}
          aria-label={`HTTP işlemi ${index + 1} kaldır`}
        >
          Kaldır
        </Button>
      </div>
      <Field
        label="HTTP işlem adı"
        value={action.alias}
        onChange={(alias) => patch({ alias })}
        maxLength={40}
      />
      <SelectField
        label="HTTP hedef bağlantısı"
        value={action.connection_id}
        onChange={(connection_id) => patch({ connection_id })}
      >
        <option value="">Bağlantı seç</option>
        {connections.map((c) => (
          <option key={c.id} value={c.id} disabled={!c.enabled}>
            {c.label}
            {c.enabled ? "" : " · Kapalı"}
          </option>
        ))}
      </SelectField>
      {target && <p className="text-sm break-all">{target.endpoint}</p>}
      <SelectField
        label="HTTP yöntemi"
        value={action.method || "POST"}
        onChange={(method) => patch({ method: method as Action["method"] })}
      >
        {["POST", "PUT", "PATCH"].map((m) => (
          <option key={m}>{m}</option>
        ))}
      </SelectField>
      <ActionConditionField
        value={action.condition}
        allowNoAnswer={!action.transcript_policy}
        onChange={(condition) => patch({ condition })}
      />
      <section className="fields" aria-label="Konuşma dökümü paylaşımı">
        <label className="flex gap-2 items-start text-sm">
          <input
            type="checkbox"
            disabled={action.condition === "no_answer"}
            checked={!!action.transcript_policy}
            onChange={(e) => transcript(e.target.checked)}
          />
          Konuşma dökümünü bu hedefle paylaş
        </label>
        <p className="muted">
          Varsayılan olarak kapalıdır. Açarsan kaydedilmiş konuşmanın ilk 100
          satırı, en fazla 8 KB metin olarak gönderilir. Eksik veya kısaltılmış
          içerik durumuyla belirtilir; ses kaydı gönderilmez. Cevaplanmayan
          çağrıda paylaşım bilgilendirmesi okunamadığı için döküm paylaşılmaz.
        </p>
        {action.transcript_policy && (
          <Notice>
            Döküm kişisel veya arayanın söylediği hassas bilgiler içerebilir;
            otomatik sansür uygulanmaz. Hedefteki erişim ve saklama kurallarını
            kontrol et. Karşılamaya “Bu görüşmenin yazılı dökümü, görüşme
            sonunda bağlı hizmet sağlayıcılarla paylaşılabilir.” bilgilendirmesi
            eklenir. Yeni karşılama sesi hazırlanmadan bu değişiklik
            yayınlanamaz.
          </Notice>
        )}
      </section>
      {(["body", "query"] as const).map((group) => (
        <fieldset className="fields border-t pt-4" key={group}>
          <legend className="font-semibold">
            {group === "body" ? "JSON gövdesi" : "Sorgu parametreleri"}
          </legend>
          <p className="muted">
            {group === "body"
              ? "Bilgiler JSON türleri korunarak gönderilir."
              : "Değerler adrese güvenli biçimde eklenir; hedef sunucuyu değiştiremez."}
          </p>
          {Object.entries(action[group] || {}).map(([name, value], i) => (
            <div
              key={i}
              className="fields border rounded-md p-4"
              aria-label={`${group === "body" ? "Gövde" : "Sorgu"} alanı ${i + 1}`}
            >
              <div className="field-pair">
                <Field
                  label="Hedef alan adı"
                  value={name}
                  onChange={(v) => rename(group, name, v)}
                  maxLength={40}
                />
                <SelectField
                  label="Değer kaynağı"
                  disabled={
                    value.kind === "source" &&
                    value.source.startsWith("transcript.")
                  }
                  value={value.kind === "literal" ? "literal" : value.source}
                  onChange={(source) =>
                    mapping(
                      group,
                      name,
                      source === "literal"
                        ? { kind: "literal", value: "" }
                        : { kind: "source", source, on_missing: "null" },
                    )
                  }
                >
                  <option value="literal">Sabit değer</option>
                  {availableFields
                    .filter(
                      (f) =>
                        group === "body" ||
                        (!f.startsWith("outputs.") &&
                          !f.startsWith("transcript.")),
                    )
                    .map((f) => (
                      <option key={f} value={f}>
                        {labels[f] || f}
                      </option>
                    ))}
                </SelectField>
              </div>
              {value.kind === "source" ? (
                <SelectField
                  label="Bilgi bulunamazsa"
                  value={value.on_missing}
                  onChange={(v) =>
                    mapping(group, name, {
                      ...value,
                      on_missing: v as "null" | "omit" | "fail",
                    })
                  }
                >
                  <option value="null">Boş (null) gönder</option>
                  <option value="omit">Bu alanı gönderme</option>
                  <option value="fail">Bu işlemi gönderme</option>
                </SelectField>
              ) : (
                <div className="field-pair">
                  <SelectField
                    label="Sabit değer türü"
                    value={value.value === null ? "null" : typeof value.value}
                    onChange={(v) =>
                      mapping(group, name, {
                        kind: "literal",
                        value:
                          v === "null"
                            ? null
                            : v === "boolean"
                              ? false
                              : v === "number"
                                ? 0
                                : "",
                      })
                    }
                  >
                    <option value="string">Metin</option>
                    <option value="number">Sayı</option>
                    <option value="boolean">Doğru / yanlış</option>
                    <option value="null">Boş (null)</option>
                  </SelectField>
                  {typeof value.value === "boolean" ? (
                    <SelectField
                      label="Sabit değer"
                      value={String(value.value)}
                      onChange={(v) =>
                        mapping(group, name, {
                          kind: "literal",
                          value: v === "true",
                        })
                      }
                    >
                      <option value="true">Doğru</option>
                      <option value="false">Yanlış</option>
                    </SelectField>
                  ) : (
                    value.value !== null && (
                      <Field
                        label="Sabit değer"
                        type={
                          typeof value.value === "number" ? "number" : "text"
                        }
                        value={String(value.value)}
                        maxLength={1024}
                        onChange={(v) => {
                          const next =
                            typeof value.value === "number" ? Number(v) : v;
                          if (typeof next !== "number" || Number.isFinite(next))
                            mapping(group, name, {
                              kind: "literal",
                              value: next,
                            });
                        }}
                      />
                    )
                  )}
                </div>
              )}
              <Button
                type="button"
                variant="outline"
                disabled={
                  value.kind === "source" &&
                  value.source.startsWith("transcript.")
                }
                onClick={() =>
                  patch({
                    [group]: Object.fromEntries(
                      Object.entries(action[group] || {}).filter(
                        ([k]) => k !== name,
                      ),
                    ),
                  })
                }
              >
                Alanı kaldır
              </Button>
            </div>
          ))}
          <Button
            type="button"
            variant="outline"
            disabled={
              Object.keys(action[group] || {}).length >=
              (group === "body" ? 16 : 8)
            }
            onClick={() => add(group)}
          >
            {group === "body" ? "Gövde alanı ekle" : "Sorgu alanı ekle"}
          </Button>
        </fieldset>
      ))}
      <fieldset className="fields border-t pt-4">
        <legend className="font-semibold">
          Sabit başlıklar · isteğe bağlı
        </legend>
        <p className="muted">
          İş etiketi için X-Data- ile başlayan başlıklar kullan. Erişim
          anahtarını Bağlantılar ekranında sakla.
        </p>
        {Object.entries(action.headers || {}).map(([key, value], i) => (
          <div className="field-pair" key={i}>
            <Field
              label="Başlık adı"
              value={key}
              onChange={(name) => {
                if (name !== key && name in (action.headers || {})) {
                  setError("Başlık adları benzersiz olmalı.");
                  return;
                }
                patch({
                  headers: Object.fromEntries(
                    Object.entries(action.headers || {}).map(([k, v]) => [
                      k === key ? name : k,
                      v,
                    ]),
                  ),
                });
              }}
            />
            <Field
              label="Başlık değeri"
              value={value}
              onChange={(v) =>
                patch({ headers: { ...action.headers, [key]: v } })
              }
              maxLength={256}
            />
            <Button
              type="button"
              variant="outline"
              onClick={() =>
                patch({
                  headers: Object.fromEntries(
                    Object.entries(action.headers || {}).filter(
                      ([k]) => k !== key,
                    ),
                  ),
                })
              }
            >
              Başlığı kaldır
            </Button>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          disabled={Object.keys(action.headers || {}).length >= 4}
          onClick={() => {
            let n = 1;
            while (`X-Data-Label${n}` in (action.headers || {})) n++;
            patch({
              headers: { ...action.headers, [`X-Data-Label${n}`]: "team" },
            });
          }}
        >
          Başlık ekle
        </Button>
      </fieldset>
      <p className="muted">
        Özet seçildiğinde durum; telefon seçildiğinde kaynak bilgisi eklenir.
        Bulunamayan zorunlu alan yalnızca bu işlemi durdurur. Belirsiz
        gönderimler otomatik tekrarlanmaz.
      </p>
      {error && <Notice error>{error}</Notice>}
      <details>
        <summary className="text-link">
          Gönderim yapılandırmasını göster
        </summary>
        <pre className="text-sm whitespace-pre-wrap break-all mt-3">
          {JSON.stringify(
            {
              method: action.method,
              endpoint: target?.endpoint,
              headers: action.headers,
              body: action.body,
              query: action.query,
            },
            null,
            2,
          )}
        </pre>
        <p className="muted">
          Bu görünüm istek göndermez; alan eşleştirmelerini gösterir.
        </p>
      </details>
    </section>
  );
}
