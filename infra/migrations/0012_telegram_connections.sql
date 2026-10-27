-- AGP-05: fixed Telegram destinations; storage is not an execution grant.
CREATE TABLE telegram_connections (
    id uuid PRIMARY KEY,
    scope_id uuid NOT NULL REFERENCES recipient_scopes(id),
    label text NOT NULL CHECK(length(label) BETWEEN 1 AND 80),
    chat_id text NOT NULL CHECK(chat_id ~ '^-?[1-9][0-9]{0,15}$'
        AND abs(chat_id::numeric) <= 4503599627370495),
    ciphertext bytea NOT NULL CHECK(octet_length(ciphertext) BETWEEN 32 AND 8192),
    enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(scope_id,id)
);
ALTER TABLE telegram_connections ENABLE ROW LEVEL SECURITY;
ALTER TABLE telegram_connections FORCE ROW LEVEL SECURITY;
CREATE POLICY telegram_workspace ON telegram_connections
    USING(scope_id=nullif(current_setting('alojan.scope_id',true),'')::uuid);
CREATE FUNCTION pin_telegram_connection() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF (NEW.id,NEW.scope_id,NEW.label,NEW.chat_id,NEW.ciphertext,NEW.created_at)
        IS DISTINCT FROM (OLD.id,OLD.scope_id,OLD.label,OLD.chat_id,OLD.ciphertext,OLD.created_at)
        OR (NOT OLD.enabled AND NEW.enabled) THEN
        RAISE EXCEPTION 'Telegram destination is immutable; create a new connection' USING ERRCODE='23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER pin_telegram_connection BEFORE UPDATE ON telegram_connections
    FOR EACH ROW EXECUTE FUNCTION pin_telegram_connection();
