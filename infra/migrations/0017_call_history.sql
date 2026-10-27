-- AGP-06: bounded management pagination over immutable scope-owned call history.
SET LOCAL lock_timeout = '200ms';
SET LOCAL statement_timeout = '3s';
CREATE INDEX call_route_scope_history ON call_route_snapshots(scope_id,created_at DESC,call_id DESC);
CREATE INDEX call_route_profile_history ON call_route_snapshots(scope_id,profile_id,created_at DESC,call_id DESC);
