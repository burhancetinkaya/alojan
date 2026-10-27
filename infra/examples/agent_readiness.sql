-- Read-only operator diagnostic for the AGP-03 readiness coordinator.
-- Replace the synthetic workspace UUID and node with the intended deployment.
-- Never seed ready=true: only the owning consumer may issue/renew its receipt.
BEGIN;
SELECT set_config('alojan.scope_id','00000000-0000-4000-8000-000000000001',true);
SELECT release_id,node_id,
       ready AND acknowledged_at<=clock_timestamp() AND valid_until>clock_timestamp() AS receipt_valid,
       acknowledged_at,valid_until
FROM release_readiness
WHERE scope_id='00000000-0000-4000-8000-000000000001' AND node_id='example-node'
ORDER BY release_id;
ROLLBACK;
-- A valid database receipt is insufficient: the receiving agent also requires
-- its own fresh, process-local prepared pin. No credentials or consumer IDs shown.
