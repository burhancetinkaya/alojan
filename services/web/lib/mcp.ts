export type Value =
  | string
  | number
  | boolean
  | null
  | Value[]
  | { [key: string]: Value };

export function hasUnsafeNumber(value: unknown): boolean {
  if (typeof value === "number")
    return (
      !Number.isFinite(value) ||
      (Number.isInteger(value) && !Number.isSafeInteger(value))
    );
  if (value && typeof value === "object")
    return Object.values(value).some(hasUnsafeNumber);
  return false;
}
export type Schema = {
  type:
    | "object"
    | "array"
    | "string"
    | "integer"
    | "number"
    | "boolean"
    | "null"
    | ["string" | "integer" | "number" | "boolean", "null"];
  properties?: Record<string, Schema>;
  required?: string[];
  items?: Schema;
  enum?: (string | number | boolean | null)[];
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  format?: "uuid" | "date-time";
  minItems?: number;
  maxItems?: number;
};
export type MCPBinding = {
  connection_id: string;
  review_id: string;
  alias: string;
  guidance: string;
  fixed_arguments: Record<string, Value>;
};
export type MCPConnection = {
  id: string;
  label: string;
  endpoint: string;
  auth_type: string;
  auth_status?: string | null;
  enabled: boolean;
};
export type MCPTool = {
  name: string;
  description: string;
  digest: string;
  inputSchema: Schema;
  outputSchema?: Schema;
};
export type QualifiedSchemas = {
  schema_policy?: "bounded.v1" | "bounded.v2";
  input_schema?: Schema;
  output_schema?: Schema | null;
};
export type Catalog = {
  tools: (QualifiedSchemas & { review_id: string | null; tool: MCPTool })[];
};
export type MCPReview = {
  draft_version: number;
  review_digest: string;
  review: {
    tools: (MCPBinding &
      QualifiedSchemas & {
        endpoint: string;
        tool: MCPTool;
        runtime_schema: Schema;
      })[];
  };
};
export type MCPGrant = { id: string; review_digest: string; enabled: boolean };
export function initialValue(schema: Schema): Value {
  if (schema.enum?.length) return schema.enum[0];
  if (Array.isArray(schema.type)) return null;
  switch (schema.type) {
    case "object":
      return Object.fromEntries(
        (schema.required || []).map((key) => [
          key,
          initialValue(schema.properties![key]),
        ]),
      );
    case "array":
      return [];
    case "boolean":
      return false;
    case "null":
      return null;
    case "integer":
    case "number":
      return schema.minimum ?? 0;
    default:
      return "";
  }
}
