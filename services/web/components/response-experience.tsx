"use client";

import type { Draft } from "@/lib/api";
import { Field, SelectField } from "./shared";

export function ResponseExperience({ value, onChange }: {
  value: Draft["response_experience"];
  onChange: (value: NonNullable<Draft["response_experience"]>) => void;
}) {
  const current = value ?? { schema_version: 1, enabled: false, style: "concise", waiting_text: null };
  return (
    <div className="fields">
      <label className="flex gap-3 items-center">
        <input type="checkbox" checked={current.enabled}
          onChange={(event) => onChange({ ...current, enabled: event.target.checked })} />
        Araç yanıtı uzadığında arayanı bilgilendir
      </label>
      <p className="muted">Agent kısa bir bekleme cümlesi söyler. Yanıt hazır olduğunda konuşmasına geçer; aynı istekte tekrar tekrar bekletme mesajı vermez.</p>
      {current.enabled && <>
        <SelectField label="Bekleme ifadesi" value={current.style}
          onChange={(style) => onChange({ ...current, style: style as "concise" | "natural" })}>
          <option value="concise">Kısa</option>
          <option value="natural">Doğal</option>
        </SelectField>
        <Field label="Özel bekleme cümlesi (isteğe bağlı)" value={current.waiting_text ?? ""}
          maxLength={100} onChange={(text) => onChange({ ...current, waiting_text: text || null })}
          hint="Boş bırakırsan hazır ifadeyi kullanır. Sonuç, süre veya işlem başarısı vaat etmeyen kısa bir cümle yaz." />
        <p className="muted">Değişiklikten sonra sesleri yeniden hazırla ve yeni sürümü yayınla.</p>
      </>}
    </div>
  );
}
