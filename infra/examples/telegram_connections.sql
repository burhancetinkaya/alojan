-- Metadata-only operator diagnostic. Creation/revocation uses the owner API.
-- A saved connection neither grants permission nor triggers external delivery.
BEGIN;
SELECT set_config('alojan.scope_id','00000000-0000-4000-8000-000000000001',true);
SELECT id,label,chat_id,enabled,created_at
FROM telegram_connections
WHERE scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid;
ROLLBACK;
