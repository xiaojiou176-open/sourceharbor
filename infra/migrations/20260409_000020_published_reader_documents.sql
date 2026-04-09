CREATE TABLE IF NOT EXISTS published_reader_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stable_key VARCHAR(255) NOT NULL,
    slug VARCHAR(255) NOT NULL UNIQUE,
    window_id VARCHAR(128) NOT NULL,
    topic_key VARCHAR(128),
    topic_label VARCHAR(255),
    title VARCHAR(255) NOT NULL,
    summary TEXT,
    markdown TEXT NOT NULL,
    reader_output_locale VARCHAR(32) NOT NULL DEFAULT 'zh-CN',
    reader_style_profile VARCHAR(64) NOT NULL DEFAULT 'briefing',
    materialization_mode VARCHAR(32) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    published_with_gap BOOLEAN NOT NULL DEFAULT FALSE,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    source_item_count INTEGER NOT NULL DEFAULT 0,
    consumption_batch_id UUID NULL,
    cluster_verdict_manifest_id UUID NULL,
    supersedes_document_id UUID NULL,
    warning_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    coverage_ledger_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    traceability_pack_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_refs_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    sections_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    repair_history_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT published_reader_documents_materialization_mode_check
        CHECK (
            materialization_mode IN (
                'merge_then_polish',
                'polish_only',
                'repair_patch',
                'repair_section',
                'repair_cluster'
            )
        ),
    CONSTRAINT published_reader_documents_version_check CHECK (version >= 1),
    CONSTRAINT published_reader_documents_source_item_count_check CHECK (source_item_count >= 0),
    CONSTRAINT fk_published_reader_documents_batch
        FOREIGN KEY (consumption_batch_id)
        REFERENCES consumption_batches(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_published_reader_documents_manifest
        FOREIGN KEY (cluster_verdict_manifest_id)
        REFERENCES cluster_verdict_manifests(id)
        ON DELETE SET NULL,
    CONSTRAINT fk_published_reader_documents_supersedes
        FOREIGN KEY (supersedes_document_id)
        REFERENCES published_reader_documents(id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_published_reader_documents_stable_key
    ON published_reader_documents(stable_key, is_current, version DESC);

CREATE INDEX IF NOT EXISTS idx_published_reader_documents_window_created
    ON published_reader_documents(window_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_published_reader_documents_topic_key
    ON published_reader_documents(topic_key, created_at DESC);
