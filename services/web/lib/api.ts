import type { MCPBinding } from "./mcp";
export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
  ) {
    super(messageFor(status, code));
  }
}

const messages: Record<string, string> = {
  invalid_personal_token:
    "Token adını, izinleri ve geçerlilik süresini kontrol et.",
  personal_token_limit:
    "En fazla 20 aktif token olabilir. Kullanmadığın bir erişimi iptal et.",
  insufficient_scope: "Bu işlem için gerekli erişim iznin yok.",
  invalid_connection_setup:
    "Bağlantı bilgileri geçerli değil. İstemciden kurulumu yeniden başlat.",
  connection_setup_expired:
    "Kurulumun süresi doldu. İstemciden yeni bir kurulum başlat.",
  connection_setup_revoked:
    "Bu kurulumu başlatan erişim iptal edilmiş. Yeni bir kurulum başlat.",

  invalid_output_configuration:
    "Özel alanın seçili aracın sonuç şemasında bulunduğunu ve türünün eşleştiğini kontrol et.",
  invalid_action_intent:
    "Gönderim ayarı boyut sınırını aşıyor. Hedef adresini, sabit değerleri veya sorgu alanlarını kısaltıp yeniden incele.",
  invalid_http_connection:
    "HTTPS hedef adresini ve erişim anahtarını kontrol et. Adreste sorgu, kullanıcı bilgisi veya özel port kullanma.",
  http_connection_unavailable:
    "HTTP bağlantısı kapalı veya bu çalışma alanına ait değil.",
  oauth_provider_unavailable: "Bu hesap bağlantısı henüz kullanılamıyor.",
  oauth_flow_limit:
    "Bağlantı deneme sınırına ulaşıldı. Daha sonra tekrar dene.",
  oauth_metadata_unavailable:
    "Sağlayıcının giriş bilgileri doğrulanamadı. Alojan yöneticisiyle kontrol et.",
  oauth_exchange_failed:
    "Hesap bağlantısı tamamlanamadı. Bağlantılarını kontrol edip yeniden başlat.",
  oauth_flow_consumed:
    "Bu giriş denemesi artık kullanılamıyor. Bağlantılarını kontrol edip yeniden başlat.",
  invalid_oauth_callback:
    "Giriş dönüşü bu hesap veya oturumla eşleşmedi. Yeniden başlat.",
  oauth_reconnect_required:
    "Hesap erişimi sona erdi. Yeni bir OAuth bağlantısı oluşturup seç.",
  invalid_mcp_connection:
    "MCP adresini ve erişim anahtarını kontrol et. Geçerli bir HTTPS adresi gerekiyor.",
  mcp_connection_unavailable:
    "MCP bağlantısı kapalı veya erişilemiyor. Başka bir bağlantı seç.",
  mcp_discovery_required:
    "Önce Bağlantılar ekranından araç listesini tara ve sonucu kontrol et.",
  mcp_tool_review_required:
    "Bu aracın Alojan incelemesi henüz tamamlanmadı veya kaldırıldı.",
  mcp_tool_changed:
    "Sunucudaki araç tanımı değişti. Yeni incelemeden geçmiş aracı seçip yeniden izin ver.",
  unsupported_mcp_configuration:
    "Sabit parametreleri kontrol et. Değerler aracın beklediği tür ve sınırlarla eşleşmeli.",
  mcp_grant_required:
    "Yayınlamadan önce Araçlar sekmesinde MCP araç iznini inceleyip onayla.",
  invalid_mcp_grant:
    "Bu sürümün MCP izni geçerli değil. Araç seçimini ve izinleri kontrol et.",
  stale_mcp_review:
    "Araçlar veya sabit değerler değişti. İzin vermeden önce yeniden incele.",
  no_mcp_tools: "Önce bir MCP aracı ekleyip taslağı kaydet.",
  mcp_discovery_limit: "Tarama sınırına ulaşıldı. Daha sonra tekrar dene.",
  unsupported_mcp_release:
    "Seçilen araçların toplam boyutu yayın sınırını aşıyor. Daha az araç seç.",
  release_not_ready_on_node:
    "Ses sunucusu bu sürümü henüz hazır olarak doğrulamadı. Biraz sonra tekrar dene; mevcut numara eşlemesi korunur.",
  voice_node_not_configured:
    "Bu ortamın ses sunucusu bağlantısı henüz yapılandırılmamış. Alojan yöneticisinin kurulumu tamamlaması gerekiyor.",
  stale_publication:
    "Yayın başka bir yerde değişti. Geçmişi yenileyip seçimini yeniden kontrol et.",
  invalid_release:
    "Bu sürüm artık yayın için geçerli değil. Başka bir sürüm seçin.",
  invalid_action_grant:
    "Bu sürümün gönderim izni artık geçerli değil. Agent'ın izinlerini kontrol edin.",
  stale_retry_review:
    "Gönderim durumu değişti. Güncel bilgileri inceleyip yeniden onaylayın.",
  retry_already_requested: "Bu bildirim için yeniden deneme zaten sırada.",
  manual_retry_limit: "Bu bildirim için yeniden deneme sınırına ulaşıldı.",
  delivery_not_retryable:
    "Bildirimin mevcut durumu yeniden denemeye uygun değil.",
  invalid_transcript_cursor:
    "Konuşma kaydı değişmiş olabilir. Dökümü baştan yenileyin.",
  voice_preparation_limit:
    "Ses hazırlığı sınırına ulaşıldı. Bir süre sonra tekrar deneyin veya destek ekibiyle iletişime geçin.",
  voice_preview_unavailable:
    "Ses dosyasına şu anda erişilemiyor. Biraz sonra tekrar deneyin.",
  stale_action_review:
    "Bildirim hedefi, koşulu veya alanları değişti. İzin vermeden önce yeniden inceleyin.",
  no_post_call_actions:
    "Önce bir çağrı sonrası işlem ekleyip taslağı kaydedin.",
  invalid_credentials: "E-posta veya şifre doğru değil.",
  login_unavailable: "Bu hesap zaten var. Giriş yapmayı deneyin.",
  password_requires_8_to_128_characters: "Şifreniz 8–128 karakter olmalı.",
  invalid_password: "Şifreniz 8–128 karakter olmalı.",
  invalid_login: "Geçerli bir e-posta adresi yazın.",
  stale_version:
    "Bu kayıt başka bir yerde değişti. Yeniden açıp değişikliklerinizi kontrol edin.",
  invalid_agent_configuration:
    "Agent ayarları geçerli değil. Alan uzunluklarını ve seçili bağlantıları kontrol edin.",
  voice_assets_pending:
    "Yeni karşılama sesi henüz hazır değil. Mevcut sürüm çalışmaya devam ediyor.",
  model_not_qualified: "Bu model şu anda yayın için kullanılamıyor.",
  number_not_verified: "Önce bu numaranın size ait olduğu doğrulanmalı.",
  release_not_ready: "Agent bu numarada çalışmaya henüz hazır değil.",
  origin_rejected:
    "Bu adres için güvenli giriş yapılandırılmamış. Doğru Alojan adresini kullanın.",
  csrf_rejected: "Oturumunuz değişmiş olabilir. Yeniden giriş yapın.",
  invalid_number: "Numarayı +90850 ile başlayan biçimde yazın.",
  action_grant_required: "Çağrı sonrası bildirim için yayın izni gerekiyor.",
};
function messageFor(status: number, code: string) {
  return (
    messages[code] ||
    (
      {
        400: "Alanları kontrol edip tekrar deneyin.",
        401: "Oturumunuz sona erdi. Yeniden giriş yapın.",
        403: "Bu işlem için yetkiniz yok.",
        404: "Kayıt bulunamadı veya bu çalışma alanına ait değil.",
        409: "İşlem henüz tamamlanamıyor. Hazırlık ve bağlantı durumlarını kontrol edin.",
        412: messages.stale_version,
        429: "Çok fazla deneme yapıldı. Birkaç dakika sonra tekrar deneyin.",
        503: "Servise şu anda ulaşılamıyor. Biraz sonra tekrar deneyin.",
      } as Record<number, string>
    )[status] ||
    "İşlem tamamlanamadı. Lütfen tekrar deneyin."
  );
}
export async function api<T>(
  path: string,
  options: {
    method?: string;
    body?: unknown;
    csrf?: string;
    version?: number;
    signal?: AbortSignal;
    responseType?: "blob";
  } = {},
): Promise<T> {
  const response = await fetch(`/v1/${path}`, {
    method: options.method || (options.body !== undefined ? "POST" : "GET"),
    credentials: "same-origin",
    cache: "no-store",
    signal: options.signal,
    headers: {
      ...(options.body !== undefined
        ? { "Content-Type": "application/json" }
        : {}),
      ...(options.csrf ? { "X-CSRF-Token": options.csrf } : {}),
      ...(options.version !== undefined
        ? { "If-Match": `"${options.version}"` }
        : {}),
    },
    ...(options.body !== undefined
      ? { body: JSON.stringify(options.body) }
      : {}),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    if (
      response.status === 401 &&
      payload.error !== "invalid_credentials" &&
      !path.startsWith("auth/")
    )
      window.dispatchEvent(new Event("alojan-session-expired"));
    throw new ApiError(
      response.status,
      typeof payload.error === "string" ? payload.error : "request_failed",
    );
  }
  return (
    options.responseType === "blob" ? response.blob() : response.json()
  ) as Promise<T>;
}
export function errorMessage(error: unknown) {
  return error instanceof ApiError
    ? error.message
    : "Bağlantı kurulamadı. Lütfen tekrar deneyin.";
}
export type Session = {
  user: { id: string; login: string; display_name: string };
  csrf_token: string;
  workspaces: { id: string; name: string; role: string }[];
};
export type Tool = { tool: string; alias: string; guidance: string };
export type HTTPValue =
  | { kind: "source"; source: string; on_missing: "null" | "omit" | "fail" }
  | { kind: "literal"; value: string | number | boolean | null };
export type HTTPConnection = {
  id: string;
  label: string;
  endpoint: string;
  auth_type: "none" | "bearer";
  enabled: boolean;
};
export type ActionCondition =
  | "answered"
  | "summary_ready"
  | "summary_failed"
  | "no_answer"
  | "interrupted";
export type Action = {
  condition?: ActionCondition;
  transcript_policy?: "bounded_text.v1";
  alias: string;
  adapter: string;
  connection_id: string;
  fields?: string[];
  method?: "POST" | "PUT" | "PATCH";
  body?: Record<string, HTTPValue>;
  query?: Record<string, HTTPValue>;
  headers?: Record<string, string>;
  [key: string]: unknown;
};
export type OutputDefinition = {
  name: string;
  type:
    | "string"
    | "number"
    | "boolean"
    | "string_array"
    | "number_array"
    | "boolean_array";
  source: "conversation" | "tool";
  description: string;
  tool_alias: string | null;
  path: string | null;
};
export type PromptTemplate = {
  version: 1;
  timezone: string;
  variables: { name: string; value: string }[];
};
export type Draft = {
  response_experience?: {
    schema_version: 1;
    enabled: boolean;
    style: "concise" | "natural";
    waiting_text: string | null;
  } | null;
  prompt_template?: PromptTemplate | null;
  agent_name: string;
  owner_display_name: string;
  owner_address: string;
  owner_dative: string;
  owner_genitive: string;
  instructions: string;
  role_description: string;
  tone_description: string;
  business_context: string;
  model: string;
  model_connection?: string;
  voice: string;
  greeting_text: string;
  tools: Tool[];
  mcp_tools?: MCPBinding[];
  outputs?: OutputDefinition[];
  post_call_actions?: Action[];
  [key: string]: unknown;
};
export type Agent = { id: string; version: number; content: Draft };
export type Releases = {
  version: number;
  current_release: string | null;
  releases: {
    id: string;
    revision: number;
    digest: string;
    rollback_of: string | null;
  }[];
};
export type Phone = {
  id: string;
  number: string;
  version: number;
  status: string;
  enabled: boolean;
  release_id: string | null;
};
export type Connection = {
  id: string;
  label: string;
  enabled: boolean;
  provider?: string;
  chat_id?: string;
};
export type Model = { id: string; revision: number; name: string };
export function maskNumber(number: string) {
  return `0850 ••• •• ${number.slice(-2)}`;
}
