-- Accept bounded ASCII email login identifiers; these do not prove mailbox ownership.
CREATE FUNCTION valid_account_login(value text) RETURNS boolean
LANGUAGE sql IMMUTABLE STRICT AS $$
    SELECT value ~ '^[a-z0-9][a-z0-9_.-]{2,63}$'
        OR (length(value) <= 254 AND length(split_part(value,'@',1)) <= 64
            AND value ~ '^[a-z0-9]+([._+-][a-z0-9]+)*@([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?[.])+[a-z]{2,63}$');
$$;
ALTER TABLE users DROP CONSTRAINT users_login_check;
ALTER TABLE users ADD CONSTRAINT users_login_check CHECK (valid_account_login(login));
ALTER TABLE workspace_invitations DROP CONSTRAINT workspace_invitations_login_check;
ALTER TABLE workspace_invitations ADD CONSTRAINT workspace_invitations_login_check
    CHECK (valid_account_login(login));
-- No account is created or ownership transferred by matching an unverified email.
