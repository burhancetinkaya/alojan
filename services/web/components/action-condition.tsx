"use client";
import type { ActionCondition } from "@/lib/api";
import { SelectField } from "./shared";

export const conditionLabels: Record<ActionCondition, string> = {
  answered: "Tüm cevaplanan çağrılar",
  summary_ready: "Yalnızca özet hazırsa",
  summary_failed: "Yalnızca özet oluşturulamadıysa",
  no_answer: "Yalnızca cevaplanmayan çağrılar",
  interrupted: "Arayan kapattıysa veya görüşme kesildiyse",
};

export function ActionConditionField({
  value,
  onChange,
  allowNoAnswer = true,
}: {
  value?: ActionCondition;
  onChange: (value: ActionCondition) => void;
  allowNoAnswer?: boolean;
}) {
  return (
    <>
      <SelectField
        label="Ne zaman gönderilsin?"
        value={value || "answered"}
        onChange={(v) => onChange(v as ActionCondition)}
      >
        {Object.entries(conditionLabels).map(([key, label]) => (
          <option
            key={key}
            value={key}
            disabled={key === "no_answer" && !allowNoAnswer}
          >
            {label}
          </option>
        ))}
      </SelectField>
      <p className="muted">
        Koşul görüşme ve özet işlemi bittikten sonra değerlendirilir. Koşula
        uymayan çağrılarda gönderim oluşturulmaz. Koşulu değiştirmek yeni
        gönderim izni gerektirir. Cevaplanmayan çağrıda özet hazırlanmaz ve
        konuşma bilgileri boş kalır. Arayanın kapatması normal bir vedalaşma da
        olabilir; bu koşul konuşmanın içeriğinden karar vermez.
      </p>
    </>
  );
}
