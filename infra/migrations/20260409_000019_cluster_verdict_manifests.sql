CREATE TABLE IF NOT EXISTS cluster_verdict_manifests (
    id UUID PRIMARY KEY,
    consumption_batch_id UUID NOT NULL UNIQUE,
    window_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ready',
    manifest_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_item_count INTEGER NOT NULL DEFAULT 0,
    cluster_count INTEGER NOT NULL DEFAULT 0,
    singleton_count INTEGER NOT NULL DEFAULT 0,
    summary_markdown TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT cluster_verdict_manifests_status_check
        CHECK (status IN ('ready', 'gap_detected')),
    CONSTRAINT cluster_verdict_manifests_non_negative_counts_check
        CHECK (source_item_count >= 0 AND cluster_count >= 0 AND singleton_count >= 0),
    CONSTRAINT fk_cluster_verdict_manifests_batch
        FOREIGN KEY (consumption_batch_id)
        REFERENCES consumption_batches(id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_cluster_verdict_manifests_window_created
    ON cluster_verdict_manifests(window_id, created_at DESC);
