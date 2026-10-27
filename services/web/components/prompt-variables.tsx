"use client";
import type { PromptTemplate } from "@/lib/api";
import { Button } from "./ui/button";
import { Field } from "./shared";

const systemVariables = [
  ["current_datetime", "Güncel tarih ve saat"], ["current_date", "Bugünün tarihi"],
  ["current_time", "Güncel saat"], ["today_start", "Bugünün başlangıcı"],
  ["yesterday_start", "Dünün başlangıcı"], ["yesterday_end", "Dünün sonu"],
  ["timezone", "Saat dilimi"], ["agent_name", "Agent adı"], ["owner_name", "Sahibinin adı"],
];
export function PromptVariables({ value, onChange, onInsert }: {
  value: PromptTemplate | null;
  onChange: (value: PromptTemplate | null) => void;
  onInsert: (name: string) => void;
}) {
  return <section className="fields" aria-label="Talimat değişkenleri">
    <label className="flex gap-2 items-center">
      <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked ? { version: 1, timezone: "Europe/Istanbul", variables: [] } : null)} />
      Talimat değişkenlerini kullan
    </label>
    {value && <>
      <p className="muted">Değişkenler agent talimatlarına otomatik yerleşir. Tarih ve saat her konuşma adımında yenilenir. Buraya şifre veya token yazma.</p>
      <Field label="Talimat saat dilimi" value={value.timezone} maxLength={64} onChange={(timezone) => onChange({ ...value, timezone })} hint="Örneğin Europe/Istanbul veya UTC" />
      <div className="flex flex-wrap gap-2">{systemVariables.map(([name, label]) => <Button key={name} type="button" variant="outline" size="sm" onClick={() => onInsert(name)} title={"{{" + name + "}}"}>{label} ekle</Button>)}</div>
      {value.variables.map((variable, index) => <div key={index} className="fields rounded-lg border p-3">
        <Field label={`Değişken adı ${index + 1}`} value={variable.name} maxLength={48} onChange={(name) => onChange({ ...value, variables: value.variables.map((v, i) => i === index ? { ...v, name } : v) })} hint="Küçük harf, rakam ve alt çizgi; örneğin ekip_adi" />
        <Field label={`Değişken değeri ${index + 1}`} value={variable.value} maxLength={1000} area onChange={(text) => onChange({ ...value, variables: value.variables.map((v, i) => i === index ? { ...v, value: text } : v) })} />
        <div className="flex gap-2">
          <Button type="button" variant="outline" disabled={!/^[a-z][a-z0-9_]{0,47}$/.test(variable.name)} onClick={() => onInsert(variable.name)}>Talimatlara ekle</Button>
          <Button type="button" variant="ghost" onClick={() => onChange({ ...value, variables: value.variables.filter((_, i) => i !== index) })}>Değişkeni kaldır</Button>
        </div>
      </div>)}
      <Button type="button" variant="outline" disabled={value.variables.length >= 16} onClick={() => onChange({ ...value, variables: [...value.variables, { name: "", value: "" }] })}>Özel değişken ekle</Button>
      <p className="muted">Örnek: {"{{ekip_adi}}"}. Sistem değişkenlerinin adları değiştirilemez. Tanımsız veya aynı adlı değişkenler kaydedilemez. Değişkenler kapatılırsa işaretler düz metin olarak kalır.</p>
    </>}
  </section>;
}
