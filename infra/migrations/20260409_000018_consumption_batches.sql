-- Revision: 20260409_000018
-- Introduce consumption batch ledger for split Track/Consume runtime

ALTER TABLE ingest_run_items
    DROP CONSTRAINT IF EXISTS ingest_run_items_item_status_check;

UPDATE ingest_run_items
SET item_status = 'pending_consume'
WHERE item_status = 'queued';

ALTER TABLE ingest_run_items
    ADD CONSTRAINT ingest_run_items_item_status_check
        CHECK (item_status IN ('pending_consume', 'batch_assigned', 'closed', 'deduped', 'skipped'));

CREATE TABLE IF NOT EXISTS consumption_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_id VARCHAR(255) NULL UNIQUE,
    status VARCHAR(32) NOT NULL DEFAULT 'frozen',
    trigger_mode VARCHAR(32) NOT NULL DEFAULT 'manual',
    window_id VARCHAR(128) NOT NULL,
    timezone_name VARCHAR(128) NOT NULL,
    cutoff_at TIMESTAMPTZ NOT NULL,
    requested_by VARCHAR(255),
    requested_trace_id VARCHAR(255),
    filters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    base_published_doc_versions JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_item_count INTEGER NOT NULL DEFAULT 0,
    processed_job_count INTEGER NOT NULL DEFAULT 0,
    succeeded_job_count INTEGER NOT NULL DEFAULT 0,
    failed_job_count INTEGER NOT NULL DEFAULT 0,
    process_summary_json JSONB,
    error_message TEXT,
    judged_at TIMESTAMPTZ,
    materialized_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT consumption_batches_status_check
        CHECK (status IN ('frozen', 'judged', 'materialized', 'closed', 'failed')),
    CONSTRAINT consumption_batches_trigger_mode_check
        CHECK (trigger_mode IN ('manual', 'auto')),
    CONSTRAINT consumption_batches_non_negative_counts_check
        CHECK (
            source_item_count >= 0
            AND processed_job_count >= 0
            AND succeeded_job_count >= 0
            AND failed_job_count >= 0
        )
);

CREATE TABLE IF NOT EXISTS consumption_batch_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    consumption_batch_id UUID NOT NULL,
    ingest_run_item_id UUID NULL,
    subscription_id UUID NULL,
    video_id UUID NULL,
    job_id UUID NULL,
    ingest_event_id UUID NULL,
    platform VARCHAR(32) NOT NULL,
    video_uid VARCHAR(512) NOT NULL,
    source_url VARCHAR(2048) NOT NULL,
    title VARCHAR(500),
    published_at TIMESTAMPTZ,
    source_effective_at TIMESTAMPTZ NOT NULL,
    discovered_at TIMESTAMPTZ NOT NULL,
    entry_hash VARCHAR(128),
    pipeline_mode VARCHAR(64),
    content_type VARCHAR(32) NOT NULL DEFAULT 'video',
    source_origin VARCHAR(32) NOT NULL DEFAULT 'subscription_tracked',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT consumption_batch_items_source_origin_check
        CHECK (source_origin IN ('subscription_tracked', 'manual_injected')),
    CONSTRAINT consumption_batch_items_content_type_check
        CHECK (content_type IN ('video', 'article')),
    CONSTRAINT fk_consumption_batch_items_batch
        FOREIGN KEY (consumption_batch_id)
        REFERENCES consumption_batches(id)
        ON DELETE CASCADE,
    CONSTRAINT fk_consumption_batch_items_ingest_run_item
        FOREIGN KEY (ingest_run_item_id)
        REFERENCES ingest_run_items(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_consumption_batch_items_subscription
        FOREIGN KEY (subscription_id)
        REFERENCES subscriptions(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_consumption_batch_items_video
        FOREIGN KEY (video_id)
        REFERENCES videos(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_consumption_batch_items_job
        FOREIGN KEY (job_id)
        REFERENCES jobs(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_consumption_batch_items_ingest_event
        FOREIGN KEY (ingest_event_id)
        REFERENCES ingest_events(id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_consumption_batches_status_created_at
    ON consumption_batches(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_consumption_batches_window_cutoff
    ON consumption_batches(window_id, cutoff_at DESC);

CREATE INDEX IF NOT EXISTS idx_consumption_batch_items_batch_id
    ON consumption_batch_items(consumption_batch_id, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_consumption_batch_items_job_id
    ON consumption_batch_items(job_id);

CREATE INDEX IF NOT EXISTS idx_ingest_run_items_item_status_created_at
    ON ingest_run_items(item_status, created_at ASC);
