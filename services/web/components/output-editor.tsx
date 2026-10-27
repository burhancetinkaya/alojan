"use client";
import type { MCPBinding } from "@/lib/mcp";
import { useEffect, useState } from "react";
import { api, errorMessage, type OutputDefinition } from "@/lib/api";
import { Button } from "./ui/button";
import { Field, SelectField, Notice } from "./shared";

type Property = {
  type?: string | string[];
  properties?: Record<string, Property>;
  items?: Property;
};
function paths(schema: Property | null | undefined, prefix = "", depth = 0): string[] {
  if (!schema || depth >= 4 || schema.type !== "object") return [];
  return Object.entries(schema.properties || {}).flatMap(([name, value]) => {
    if (!/^[A-Za-z][A-Za-z0-9_]{0,39}$/.test(name)) return [];
    const path = prefix ? `${prefix}.${name}` : name;
    return value.type === "object" ? paths(value, path, depth + 1) : [path];
  });
}
export function OutputEditor({
  base,
  outputs,
  tools,
  used,
  onChange,
}: {
  base: string;
  outputs: OutputDefinition[];
  tools: MCPBinding[];
  used: string[];
  onChange: (outputs: OutputDefinition[]) => void;
}) {
  const [properties, setProperties] = useState<Record<string, string[]>>({});
  const [error, setError] = useState("");
  const selection = JSON.stringify(
    tools.map((t) => [t.alias, t.connection_id, t.review_id]),
  );
  useEffect(() => {
    const c = new AbortController();
    const selected: string[][] = JSON.parse(selection);
    setProperties({});
    setError("");
    void Promise.all(
      selected.map(async ([alias, connection, review]) => {
        const result = await api<{
          tools: {
            review_id: string;
            output_schema?: Property | null;
            tool: { outputSchema?: Property };
          }[];
        }>(`${base}/mcp-connections/${connection}/tools`, { signal: c.signal });
        const tool = result.tools.find((t) => t.review_id === review);
        return [
          alias,
          tool ? paths(tool.output_schema ?? tool.tool.outputSchema) : [],
        ] as const;
      }),
    )
      .then((values) => {
        if (!c.signal.aborted) setProperties(Object.fromEntries(values));
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(errorMessage(e));
      });
    return () => c.abort();
  }, [base, selection]);
  function patch(index: number, value: Partial<OutputDefinition>) {
    onChange(
      outputs.map((old, i) => (i === index ? { ...old, ...value } : old)),
    );
  }
  return (
    <section className="fields mt-6" aria-label="Özel sonuç alanları">
      <h3 className="section-title">Görüşmeden hangi bilgileri alalım?</h3>
      <p className="muted">
        Alanlarını tanımla; görüşme bitince seçtiğin bilgiler çıkarılsın.
        Bulunamayan bilgi tahmin edilmez. Bir hedefe göndermek için ayrıca
        aşağıdan eşleştir ve gönderim izni ver.
      </p>
      {error && <Notice error>{error}</Notice>}
      {outputs.map((d, index) => (
        <section
          className="form-panel fields"
          key={index}
          aria-label={`Özel alan ${index + 1}`}
        >
          <div className="field-pair">
            <Field
              label="Alan adı"
              value={d.name}
              onChange={(name) => patch(index, { name })}
              maxLength={32}
              disabled={used.includes(d.name)}
              hint="Küçük harf, rakam ve alt çizgi. Eşlenmiş alanı yeniden adlandırmadan önce eşleştirmesini kaldır."
            />
            <SelectField
              label="Alan türü"
              value={d.type}
              onChange={(type) =>
                patch(index, { type: type as OutputDefinition["type"] })
              }
            >
              {Object.entries({
                string: "Metin",
                number: "Sayı",
                boolean: "Doğru / yanlış",
                string_array: "Metin listesi",
                number_array: "Sayı listesi",
                boolean_array: "Doğru / yanlış listesi",
              }).map(([v, label]) => (
                <option key={v} value={v}>
                  {label}
                </option>
              ))}
            </SelectField>
          </div>
          <Field
            label="Hangi bilgi alınsın?"
            value={d.description}
            onChange={(description) => patch(index, { description })}
            maxLength={160}
            hint="Örneğin: Arayanın açıkça belirttiği ürün adı. Şifre veya erişim anahtarı isteme."
          />
          <SelectField
            label="Bilgi kaynağı"
            value={d.source}
            onChange={(source) =>
              patch(index, {
                source: source as OutputDefinition["source"],
                tool_alias: null,
                path: null,
              })
            }
          >
            <option value="conversation">Görüşme ve kaydedilen not</option>
            <option value="tool" disabled={!tools.length}>
              Seçilmiş aracın son başarılı sonucu
            </option>
          </SelectField>
          {d.source === "tool" && (
            <div className="field-pair">
              <SelectField
                label="Sonucu alınacak araç"
                value={d.tool_alias || ""}
                onChange={(tool_alias) =>
                  patch(index, { tool_alias, path: null })
                }
              >
                <option value="">Araç seç</option>
                {tools.map((t) => (
                  <option key={t.alias} value={t.alias}>
                    {t.alias}
                  </option>
                ))}
              </SelectField>
              <SelectField
                label="Araç sonuç alanı"
                value={d.path || ""}
                onChange={(path) => patch(index, { path })}
              >
                <option value="">Alan seç</option>
                {(properties[d.tool_alias || ""] || []).map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </SelectField>
            </div>
          )}
          <Button
            type="button"
            variant="outline"
            disabled={used.includes(d.name)}
            onClick={() => onChange(outputs.filter((_, i) => i !== index))}
          >
            Özel alanı kaldır
          </Button>
        </section>
      ))}
      <Button
        type="button"
        variant="outline"
        disabled={outputs.length >= 8}
        onClick={() => {
          let n = 1;
          while (outputs.some((d) => d.name === `bilgi_${n}`)) n++;
          onChange([
            ...outputs,
            {
              name: `bilgi_${n}`,
              type: "string",
              source: "conversation",
              description: "",
              tool_alias: null,
              path: null,
            },
          ]);
        }}
      >
        Özel alan ekle
      </Button>
      <p className="muted">
        En fazla 8 alan. Araç verisi yalnızca bu görüşmede, kapanıştan önce
        başarıyla tamamlanan seçili sonuçtan alınır. Yeni bir araç çağrısı
        yapılmaz.
      </p>
    </section>
  );
}
