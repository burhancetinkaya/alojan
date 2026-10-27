"use client";
import { useId } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Field, SelectField } from "./shared";
import {
  hasUnsafeNumber,
  initialValue,
  type Schema,
  type Value,
} from "@/lib/mcp";

// Only the operator-reviewed closed schema subset is rendered; never remote HTML/code.
export function MCPValue({
  name,
  schema,
  value,
  onChange,
}: {
  name: string;
  schema: Schema;
  value: Value;
  onChange: (value: Value) => void;
}) {
  const id = useId();
  if (schema.enum)
    return (
      <SelectField
        label={name}
        value={JSON.stringify(value)}
        onChange={(v) => onChange(JSON.parse(v))}
      >
        {schema.enum.map((v) => (
          <option key={JSON.stringify(v)} value={JSON.stringify(v)}>
            {String(v)}
          </option>
        ))}
      </SelectField>
    );
  if (Array.isArray(schema.type)) {
    const scalar = { ...schema, type: schema.type[0] };
    return (
      <fieldset className="fields">
        <legend className="font-medium">{name}</legend>
        <label className="flex gap-2 items-center">
          <input
            type="checkbox"
            checked={value === null}
            onChange={(e) =>
              onChange(e.target.checked ? null : initialValue(scalar))
            }
          />
          {name} · Boş değer gönder
        </label>
        {value !== null && (
          <MCPValue
            name={name}
            schema={scalar}
            value={value}
            onChange={onChange}
          />
        )}
      </fieldset>
    );
  }
  if (schema.type === "object") {
    const object = value as Record<string, Value>;
    return (
      <fieldset className="fields border-l pl-4">
        <legend className="font-medium mb-3">{name}</legend>
        {Object.entries(schema.properties || {}).map(([key, child]) => (
          <div key={key} className="fields">
            {!schema.required?.includes(key) && (
              <label className="flex gap-2 items-center">
                <input
                  type="checkbox"
                  checked={Object.hasOwn(object, key)}
                  onChange={(e) => {
                    const next = { ...object };
                    if (e.target.checked) next[key] = initialValue(child);
                    else delete next[key];
                    onChange(next);
                  }}
                />
                {key} alanını ekle
              </label>
            )}
            {Object.hasOwn(object, key) && (
              <MCPValue
                name={`${name} · ${key}`}
                schema={child}
                value={object[key]}
                onChange={(v) => onChange({ ...object, [key]: v })}
              />
            )}
          </div>
        ))}
      </fieldset>
    );
  }
  if (schema.type === "array") {
    const items = value as Value[];
    return (
      <fieldset className="fields border-l pl-4">
        <legend className="font-medium mb-3">{name}</legend>
        <p className="muted">
          {schema.minItems || 0}–{schema.maxItems} öğe
        </p>
        {items.map((v, i) => (
          <div key={i} className="fields">
            <MCPValue
              name={`${name} · ${i + 1}`}
              schema={schema.items!}
              value={v}
              onChange={(next) =>
                onChange(items.map((old, j) => (i === j ? next : old)))
              }
            />
            <Button
              type="button"
              variant="ghost"
              onClick={() => onChange(items.filter((_, j) => i !== j))}
            >
              {name} · {i + 1} kaldır
            </Button>
          </div>
        ))}
        <Button
          type="button"
          variant="outline"
          disabled={items.length >= (schema.maxItems || 0)}
          onClick={() => onChange([...items, initialValue(schema.items!)])}
        >
          {name} · Öğe ekle
        </Button>
      </fieldset>
    );
  }
  if (schema.type === "boolean")
    return (
      <SelectField
        label={name}
        value={String(value)}
        onChange={(v) => onChange(v === "true")}
      >
        <option value="true">Evet</option>
        <option value="false">Hayır</option>
      </SelectField>
    );
  if (schema.type === "null") return <p>{name}: Boş değer</p>;
  if (schema.type === "integer" || schema.type === "number") {
    const unsafe = value !== "" && hasUnsafeNumber(Number(value));
    const error = unsafe
      ? "Bu sayı güvenli sınırı aşıyor. Tam sayı büyüklüğü 9007199254740991 değerini aşamaz."
      : "";
    return (
      <div className="field">
        <Label htmlFor={id}>{name}</Label>
        <Input
          id={id}
          type="number"
          step={schema.type === "integer" ? 1 : "any"}
          min={schema.minimum}
          max={schema.maximum}
          required
          aria-invalid={unsafe}
          aria-describedby={unsafe ? `${id}-error` : undefined}
          ref={(input) => {
            input?.setCustomValidity(error);
          }}
          value={String(value)}
          onChange={(e) => {
            const raw = e.target.value;
            const number = Number(raw);
            onChange(raw === "" || hasUnsafeNumber(number) ? raw : number);
          }}
        />
        {error && (
          <p id={`${id}-error`} role="alert">
            {error}
          </p>
        )}
      </div>
    );
  }
  return (
    <Field
      label={name}
      value={String(value)}
      onChange={onChange}
      required={(schema.minLength || 0) > 0}
      minLength={schema.minLength}
      maxLength={schema.maxLength}
    />
  );
}
