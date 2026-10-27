-- Fence asynchronous acknowledgements from a replaced node consumer.
-- Historical receipts cannot authorize this process without its local ready pin.
ALTER TABLE release_readiness ADD COLUMN consumer_id uuid;
