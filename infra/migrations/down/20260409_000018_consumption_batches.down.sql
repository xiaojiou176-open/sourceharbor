-- Down migration for 20260409_000018_consumption_batches.sql

DROP INDEX IF EXISTS idx_ingest_run_items_item_status_created_at;
DROP INDEX IF EXISTS idx_consumption_batch_items_job_id;
DROP INDEX IF EXISTS idx_consumption_batch_items_batch_id;
DROP INDEX IF EXISTS idx_consumption_batches_window_cutoff;
DROP INDEX IF EXISTS idx_consumption_batches_status_created_at;

DROP TABLE IF EXISTS consumption_batch_items;
DROP TABLE IF EXISTS consumption_batches;

ALTER TABLE ingest_run_items
    DROP CONSTRAINT IF EXISTS ingest_run_items_item_status_check;

UPDATE ingest_run_items
SET item_status = 'queued'
WHERE item_status IN ('pending_consume', 'batch_assigned', 'closed');

ALTER TABLE ingest_run_items
    ADD CONSTRAINT ingest_run_items_item_status_check
        CHECK (item_status IN ('queued', 'deduped', 'skipped'));
