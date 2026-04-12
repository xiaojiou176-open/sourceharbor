type ExtensibleString = string & {};
export type Platform =
	| "youtube"
	| "bilibili"
	| "rsshub"
	| "generic"
	| ExtensibleString;
export type SourceType =
	| "url"
	| "youtube_channel_id"
	| "youtube_user"
	| "bilibili_uid"
	| "rsshub_route"
	| ExtensibleString;
export type SubscriptionCategory =
	| "tech"
	| "creator"
	| "macro"
	| "ops"
	| "misc";
export type SubscriptionAdapterType =
	| "rsshub_route"
	| "rss_generic"
	| ExtensibleString;
export type JobStatus = "queued" | "running" | "succeeded" | "failed";
export type PipelineFinalStatus = "succeeded" | "degraded" | "failed";
export type VideoProcessMode =
	| "full"
	| "text_only"
	| "refresh_comments"
	| "refresh_llm";

export type Subscription = {
	id: string;
	platform: Platform;
	source_type: SourceType;
	source_value: string;
	source_name: string;
	support_tier: "strong_supported" | "generic_supported";
	content_profile: ContentType;
	adapter_type: SubscriptionAdapterType;
	source_url: string | null;
	rsshub_route: string;
	creator_display_name?: string | null;
	creator_handle?: string | null;
	source_homepage_url?: string | null;
	avatar_url?: string | null;
	avatar_label?: string | null;
	thumbnail_url?: string | null;
	source_universe_label?: string | null;
	identity_status?: string | null;
	category: SubscriptionCategory;
	tags: string[];
	priority: number;
	enabled: boolean;
	created_at: string;
	updated_at: string;
};

export type SubscriptionUpsertRequest = {
	platform: Platform;
	source_type: SourceType;
	source_value: string;
	adapter_type?: SubscriptionAdapterType;
	source_url?: string | null;
	rsshub_route?: string | null;
	category?: SubscriptionCategory;
	tags?: string[];
	priority?: number;
	enabled?: boolean;
};

export type SubscriptionUpsertResponse = {
	subscription: Subscription;
	created: boolean;
};

export type ManualSourceIntakeRequest = {
	raw_input: string;
	category?: SubscriptionCategory;
	tags?: string[];
	priority?: number;
	enabled?: boolean;
};

export type ManualSourceIntakeResult = {
	line_number: number;
	raw_input: string;
	target_kind: "subscription_source" | "manual_source_item" | "unsupported";
	recommended_action: "save_subscription" | "add_to_today" | "unsupported";
	applied_action: "save_subscription" | "add_to_today" | null;
	status: "created" | "updated" | "queued" | "reused" | "rejected";
	platform: Platform | string | null;
	source_type: SourceType | string | null;
	source_value: string | null;
	source_url: string | null;
	rsshub_route: string | null;
	adapter_type: SubscriptionAdapterType | string | null;
	content_profile: ContentType | string | null;
	support_tier: "strong_supported" | "generic_supported" | string | null;
	display_name: string | null;
	relation_kind?: string | null;
	matched_subscription_id?: string | null;
	matched_subscription_name?: string | null;
	matched_by?: string | null;
	match_confidence?: string | null;
	source_universe_label?: string | null;
	creator_display_name?: string | null;
	creator_handle?: string | null;
	thumbnail_url?: string | null;
	avatar_url?: string | null;
	avatar_label?: string | null;
	message: string;
	subscription_id: string | null;
	job_id: string | null;
};

export type ManualSourceIntakeResponse = {
	processed_count: number;
	created_subscriptions: number;
	updated_subscriptions: number;
	queued_manual_items: number;
	reused_manual_items: number;
	rejected_count: number;
	results: ManualSourceIntakeResult[];
};

export type SubscriptionTemplateSupportTier = {
	id: "strong_supported" | "generic_supported";
	label: string;
	description: string;
	content_profile: ContentType;
	supports_video_pipeline: boolean;
	verification_status: string;
};

export type SubscriptionTemplate = {
	id: string;
	label: string;
	description: string;
	support_tier: SubscriptionTemplateSupportTier["id"];
	platform: Platform;
	source_type: SourceType;
	adapter_type: SubscriptionAdapterType;
	content_profile: ContentType;
	category?: SubscriptionCategory | string | null;
	source_value_placeholder?: string | null;
	source_url_placeholder?: string | null;
	rsshub_route_hint?: string | null;
	source_url_required: boolean;
	supports_video_pipeline: boolean;
	fill_now?: string | null;
	proof_boundary?: string | null;
	evidence_note?: string | null;
};

export type SubscriptionTemplateCatalogResponse = {
	support_tiers: SubscriptionTemplateSupportTier[];
	templates: SubscriptionTemplate[];
};

export type IngestPollRequest = {
	subscription_id?: string;
	platform?: Platform;
	max_new_videos?: number;
};

export type IngestCandidate = {
	video_id: string;
	platform: Platform;
	video_uid: string;
	source_url: string;
	title: string | null;
	published_at: string | null;
	job_id: string;
};

export type IngestPollResponse = {
	run_id: string;
	workflow_id: string | null;
	status: "queued" | "running" | "succeeded" | "failed" | "skipped";
	enqueued: number;
	candidates: IngestCandidate[];
};

export type IngestRunItem = {
	id: string;
	subscription_id: string | null;
	video_id: string | null;
	job_id: string | null;
	ingest_event_id: string | null;
	platform: Platform | string;
	video_uid: string;
	source_url: string;
	title: string | null;
	published_at: string | null;
	entry_hash: string | null;
	pipeline_mode: string | null;
	content_type: ContentType;
	item_status: string;
	created_at: string;
	updated_at: string;
};

export type IngestRunSummary = {
	id: string;
	subscription_id: string | null;
	workflow_id: string | null;
	platform: Platform | string | null;
	max_new_videos: number;
	status: "queued" | "running" | "succeeded" | "failed" | "skipped";
	jobs_created: number;
	candidates_count: number;
	feeds_polled: number;
	entries_fetched: number;
	entries_normalized: number;
	ingest_events_created: number;
	ingest_event_duplicates: number;
	job_duplicates: number;
	error_message: string | null;
	created_at: string;
	updated_at: string;
	completed_at: string | null;
};

export type IngestRun = IngestRunSummary & {
	requested_by: string | null;
	requested_trace_id: string | null;
	filters_json: Record<string, unknown> | null;
	items: IngestRunItem[];
};

export type ClusterVerdictManifestMember = {
	source_item_id: string;
	job_id: string | null;
	platform: string;
	source_origin: string;
	title: string;
	source_url: string | null;
	published_at: string | null;
	claim_kinds: string[];
	digest_preview: string;
};

export type ClusterVerdictCluster = {
	cluster_id: string;
	cluster_key: string;
	topic_key: string | null;
	topic_label: string;
	decision: "merge_then_polish";
	source_item_count: number;
	source_item_ids: string[];
	job_ids: string[];
	platforms: string[];
	claim_kinds: string[];
	headline: string;
	digest_preview: string;
	members: ClusterVerdictManifestMember[];
};

export type ClusterVerdictSingleton = {
	singleton_id: string;
	source_item_id: string;
	ingest_run_item_id: string | null;
	job_id: string | null;
	platform: string;
	source_origin: string;
	content_type: string;
	title: string;
	source_url: string | null;
	published_at: string | null;
	topic_key: string | null;
	topic_label: string | null;
	claim_kinds: string[];
	decision: "polish_only";
	digest_preview: string;
};

export type ClusterVerdictManifestPayload = {
	manifest_kind: string;
	generated_at: string;
	consumption_batch_id: string;
	window_id: string;
	status: "ready" | "gap_detected";
	source_item_count: number;
	cluster_count: number;
	singleton_count: number;
	clusters: ClusterVerdictCluster[];
	singletons: ClusterVerdictSingleton[];
};

export type ClusterVerdictManifest = {
	id: string;
	consumption_batch_id: string;
	window_id: string;
	status: "ready" | "gap_detected";
	source_item_count: number;
	cluster_count: number;
	singleton_count: number;
	summary_markdown: string | null;
	manifest: ClusterVerdictManifestPayload;
	created_at: string;
	updated_at: string;
};

export type ReaderDocumentSection = {
	section_id: string;
	title: string;
	markdown: string;
	source_item_ids: string[];
};

export type ReaderDocumentWarning = {
	warning_kind: string;
	published_with_gap: boolean;
	reasons: string[];
	failed_source_count: number;
	degraded_source_count: number;
	missing_digest_count: number;
	warning_kinds?: string[];
	affected_scope?: {
		source_item_ids?: string[];
		section_ids?: string[];
		source_item_count?: number;
		section_count?: number;
	};
	version?: number | null;
	readable_why?: string | null;
	not_fully_sealed_why?: string | null;
	status?: string | null;
	generated_at: string | null;
};

export type RawStageContractReceipt = {
	content_type?: string | null;
	analysis_mode?: string | null;
	video_first?: boolean | null;
	video_input_required?: boolean | null;
	preprocess_enabled?: boolean | null;
	preprocess_model?: string | null;
	preprocess_input_mode?: string | null;
	preprocess_media_input?: string | null;
	review_required?: boolean | null;
	review_model?: string | null;
	review_input_mode?: string | null;
	primary_model?: string | null;
	primary_input_mode?: string | null;
	primary_media_input?: string | null;
	review_media_input?: string | null;
	video_contract_satisfied?: boolean | null;
};

export type SourceIdentityRef = {
	source_item_id: string;
	job_id?: string | null;
	platform: string;
	source_origin: string;
	title: string;
	source_url?: string | null;
	published_at?: string | null;
	claim_kinds: string[];
	digest_preview: string;
	subscription_id?: string | null;
	matched_subscription_name?: string | null;
	relation_kind?: string | null;
	affiliation_label?: string | null;
	canonical_source_name?: string | null;
	canonical_author_name?: string | null;
	creator_display_name?: string | null;
	creator_handle?: string | null;
	thumbnail_url?: string | null;
	avatar_url?: string | null;
	avatar_label?: string | null;
	identity_status?: string | null;
	raw_stage_contract?: RawStageContractReceipt | null;
	job_bundle_route?: string | null;
};

export type ReaderDocument = {
	id: string;
	stable_key: string;
	slug: string;
	window_id: string;
	topic_key: string | null;
	topic_label: string | null;
	title: string;
	summary: string | null;
	markdown: string;
	materialization_mode: string;
	version: number;
	publish_status: string;
	published_with_gap: boolean;
	is_current: boolean;
	source_item_count: number;
	consumption_batch_id: string | null;
	cluster_verdict_manifest_id: string | null;
	supersedes_document_id: string | null;
	warning: ReaderDocumentWarning;
	coverage_ledger: Record<string, unknown>;
	traceability_pack: Record<string, unknown>;
	source_refs: SourceIdentityRef[];
	sections: ReaderDocumentSection[];
	repair_history: Record<string, unknown>[];
	created_at: string;
	updated_at: string;
};

export type NavigationBriefItem = {
	document_id: string;
	title: string;
	summary: string | null;
	topic_key: string | null;
	topic_label: string | null;
	published_with_gap: boolean;
	source_item_count: number;
	route: string;
};

export type NavigationBrief = {
	brief_kind: string;
	generated_at: string;
	window_id: string;
	document_count: number;
	published_with_gap_count: number;
	summary: string;
	items: NavigationBriefItem[];
};

export type ReaderBatchMaterialization = {
	consumption_batch_id: string;
	cluster_verdict_manifest_id: string;
	window_id: string;
	published_document_count: number;
	published_with_gap_count: number;
	documents: ReaderDocument[];
	navigation_brief: NavigationBrief;
};

export type ReaderDocumentRepairRequest = {
	repair_mode: "patch" | "section" | "cluster" | string;
	section_ids?: string[];
};

export type Video = {
	id: string;
	platform: Platform;
	video_uid: string;
	source_url: string;
	title: string | null;
	published_at: string | null;
	first_seen_at: string;
	last_seen_at: string;
	status: JobStatus | null;
	last_job_id: string | null;
	content_type?: ContentType;
};

export type VideoProcessRequest = {
	video: {
		platform: Platform;
		url: string;
		video_id?: string | null;
	};
	mode?: VideoProcessMode;
	overrides?: Record<string, unknown>;
	force?: boolean;
};

export type VideoProcessResponse = {
	job_id: string;
	video_db_id: string;
	video_uid: string;
	status: JobStatus;
	idempotency_key: string;
	mode: VideoProcessMode;
	overrides: Record<string, unknown>;
	force: boolean;
	reused: boolean;
	workflow_id: string | null;
};

export type JobStepSummary = {
	name: string;
	status: string;
	attempt: number;
	started_at: string | null;
	finished_at: string | null;
	error: unknown;
};

export type JobStepDetail = JobStepSummary & {
	error_kind: string | null;
	retry_meta: Record<string, unknown> | null;
	result: Record<string, unknown> | null;
	thought_metadata: Record<string, unknown>;
	cache_key: string | null;
};

export type JobDegradation = {
	step: string | null;
	status: string | null;
	reason: string | null;
	error: unknown;
	error_kind: string | null;
	retry_meta: Record<string, unknown> | null;
	cache_meta: Record<string, unknown> | null;
};

export type Job = {
	id: string;
	video_id: string;
	kind: "video_digest_v1" | "phase2_ingest_stub";
	status: JobStatus;
	idempotency_key: string;
	error_message: string | null;
	artifact_digest_md: string | null;
	artifact_root: string | null;
	llm_required: boolean | null;
	llm_gate_passed: boolean | null;
	hard_fail_reason: string | null;
	created_at: string;
	updated_at: string;
	step_summary: JobStepSummary[];
	steps: JobStepDetail[];
	degradations: JobDegradation[];
	pipeline_final_status: PipelineFinalStatus | null;
	artifacts_index: Record<string, string>;
	mode: VideoProcessMode | null;
	notification_retry: NotificationRetrySummary | null;
};

export type NotificationRetrySummary = {
	delivery_id: string;
	status: string;
	attempt_count: number;
	next_retry_at: string | null;
	last_error_kind: string | null;
};

export type JobCompareStats = {
	added_lines: number;
	removed_lines: number;
	changed: boolean;
};

export type JobCompare = {
	job_id: string;
	previous_job_id: string | null;
	has_previous: boolean;
	current_digest: string | null;
	previous_digest: string | null;
	diff_markdown: string;
	stats: JobCompareStats;
};

export type KnowledgeCard = {
	id?: string;
	job_id?: string;
	video_id?: string;
	card_type: string;
	title: string | null;
	body: string;
	source_section: string;
	order_index: number;
	metadata_json?: Record<string, unknown>;
	created_at?: string;
	updated_at?: string;
};

export type FeedFeedback = {
	job_id: string;
	saved: boolean;
	feedback_label: "useful" | "noisy" | "dismissed" | "archived" | null;
	exists: boolean;
	created_at: string | null;
	updated_at: string | null;
};

export type ArtifactMarkdownWithMeta = {
	markdown: string;
	meta: Record<string, unknown> | null;
};

export type NotificationConfig = {
	enabled: boolean;
	to_email: string | null;
	daily_digest_enabled: boolean;
	daily_digest_hour_utc: number | null;
	failure_alert_enabled: boolean;
	category_rules: Record<string, unknown>;
	created_at: string;
	updated_at: string;
};

export type NotificationConfigUpdateRequest = {
	enabled: boolean;
	to_email: string | null;
	daily_digest_enabled: boolean;
	daily_digest_hour_utc: number | null;
	failure_alert_enabled: boolean;
	category_rules?: Record<string, unknown>;
};

export type NotificationTestRequest = {
	to_email?: string | null;
	subject?: string | null;
	body?: string | null;
};

export type NotificationSendResponse = {
	delivery_id: string;
	status: string;
	provider_message_id: string | null;
	error_message: string | null;
	recipient_email: string;
	subject: string;
	sent_at: string | null;
	created_at: string;
};

export type ProviderHealthSummary = {
	provider: string;
	ok: number;
	warn: number;
	fail: number;
	last_status: string | null;
	last_checked_at: string | null;
	last_error_kind: string | null;
	last_message: string | null;
};

export type ProviderHealthResponse = {
	window_hours: number;
	providers: ProviderHealthSummary[];
};

export type OpsListSection<T> = {
	status: string;
	total: number;
	error: string | null;
	items: T[];
};

export type OpsJobIssue = {
	id: string;
	title: string;
	platform: string;
	status: string;
	pipeline_final_status: string | null;
	error_message: string | null;
	degradation_count: number;
	updated_at: string | null;
};

export type OpsIngestIssue = {
	id: string;
	platform: string;
	status: string;
	error_message: string | null;
	jobs_created: number;
	candidates_count: number;
	created_at: string | null;
};

export type OpsNotificationDelivery = {
	id: string;
	kind: string;
	status: string;
	recipient_email: string;
	subject: string;
	attempt_count: number;
	next_retry_at: string | null;
	last_error_kind: string | null;
	error_message: string | null;
	created_at: string | null;
};

export type OpsGate = {
	status: string;
	summary: string;
	next_step: string;
	details: Record<string, unknown>;
};

export type OpsInboxItem = {
	kind: string;
	severity: string;
	title: string;
	detail: string;
	status_label: string;
	last_seen_at: string | null;
	href: string;
	action_label: string;
};

export type OpsInboxResponse = {
	generated_at: string;
	overview: {
		attention_items: number;
		failed_jobs: number;
		failed_ingest_runs: number;
		notification_or_gate_issues: number;
	};
	failed_jobs: OpsListSection<OpsJobIssue>;
	failed_ingest_runs: OpsListSection<OpsIngestIssue>;
	notification_deliveries: OpsListSection<OpsNotificationDelivery>;
	provider_health: ProviderHealthResponse;
	gates: {
		retrieval: OpsGate;
		notifications: OpsGate;
		disk_governance: OpsGate;
		ui_audit: OpsGate;
		computer_use: OpsGate;
	};
	inbox_items: OpsInboxItem[];
};

export type WatchlistMatcherType =
	| "topic_key"
	| "claim_kind"
	| "platform"
	| "source_match";

export type WatchlistDeliveryChannel = "dashboard" | "email";

export type Watchlist = {
	id: string;
	name: string;
	matcher_type: WatchlistMatcherType;
	matcher_value: string;
	delivery_channel: WatchlistDeliveryChannel;
	enabled: boolean;
	created_at: string;
	updated_at: string;
};

export type WatchlistUpsertRequest = {
	id?: string | null;
	name: string;
	matcher_type: WatchlistMatcherType;
	matcher_value: string;
	delivery_channel?: WatchlistDeliveryChannel;
	enabled?: boolean;
};

export type WatchlistTrendCard = {
	card_id: string;
	job_id: string;
	video_id: string;
	platform: string;
	video_title: string | null;
	source_url: string | null;
	created_at: string;
	card_type: string;
	card_title: string | null;
	card_body: string;
	source_section: string;
	topic_key: string | null;
	topic_label: string | null;
	claim_kind: string | null;
};

export type WatchlistTrendRun = {
	job_id: string;
	video_id: string;
	platform: string;
	title: string;
	source_url: string | null;
	created_at: string;
	matched_card_count: number;
	cards: WatchlistTrendCard[];
	topics: string[];
	claim_kinds: string[];
	added_topics: string[];
	removed_topics: string[];
	added_claim_kinds: string[];
	removed_claim_kinds: string[];
};

export type WatchlistTrendResponse = {
	watchlist: Watchlist;
	summary: {
		recent_runs: number;
		matched_cards: number;
		matcher_type: string;
		matcher_value: string;
	};
	timeline: WatchlistTrendRun[];
	merged_stories?: WatchlistMergedStory[];
	source_coverage?: WatchlistTrendSourceCoverage[];
};

export type WatchlistMergedStory = {
	id: string;
	story_key: string;
	headline: string;
	topic_key: string | null;
	topic_label: string | null;
	latest_created_at: string;
	matched_card_count: number;
	platforms: string[];
	claim_kinds: string[];
	source_urls: string[];
	run_ids: string[];
	cards: WatchlistTrendCard[];
};

export type WatchlistTrendSourceCoverage = {
	platform: string;
	run_count: number;
	card_count: number;
	latest_created_at: string | null;
};

export type WatchlistBriefingSignal = {
	story_key: string;
	headline: string;
	matched_card_count: number;
	latest_run_job_id: string | null;
	reason: string;
};

export type WatchlistBriefingSummary = {
	overview: string;
	source_count: number;
	run_count: number;
	story_count: number;
	matched_cards: number;
	primary_story_headline: string | null;
	signals: WatchlistBriefingSignal[];
};

export type WatchlistBriefingCompare = {
	job_id: string;
	has_previous: boolean;
	previous_job_id: string | null;
	changed: boolean;
	added_lines: number;
	removed_lines: number;
	diff_excerpt: string | null;
	compare_route: string;
};

export type WatchlistBriefingDifferences = {
	latest_job_id: string | null;
	previous_job_id: string | null;
	added_topics: string[];
	removed_topics: string[];
	added_claim_kinds: string[];
	removed_claim_kinds: string[];
	new_story_keys: string[];
	removed_story_keys: string[];
	compare: WatchlistBriefingCompare | null;
};

export type WatchlistBriefingRoutes = {
	watchlist_trend: string;
	briefing: string | null;
	ask: string | null;
	job_compare: string | null;
	job_bundle: string | null;
	job_knowledge_cards: string | null;
};

export type WatchlistBriefingStoryEvidence = {
	story_id: string;
	story_key: string;
	headline: string;
	topic_key: string | null;
	topic_label: string | null;
	source_count: number;
	run_count: number;
	matched_card_count: number;
	platforms: string[];
	claim_kinds: string[];
	source_urls: string[];
	latest_run_job_id: string | null;
	evidence_cards: WatchlistTrendCard[];
	routes: WatchlistBriefingRoutes;
};

export type WatchlistBriefingRunEvidence = {
	job_id: string;
	video_id: string;
	platform: string;
	title: string;
	source_url: string | null;
	created_at: string;
	matched_card_count: number;
	routes: WatchlistBriefingRoutes;
};

export type WatchlistBriefingEvidence = {
	suggested_story_id: string | null;
	stories: WatchlistBriefingStoryEvidence[];
	featured_runs: WatchlistBriefingRunEvidence[];
};

export type WatchlistBriefingSelection = {
	selected_story_id: string | null;
	selection_basis: AskStorySelectionBasis;
	story: WatchlistBriefingStoryEvidence | null;
};

export type WatchlistBriefing = {
	watchlist: Watchlist;
	summary: WatchlistBriefingSummary;
	differences: WatchlistBriefingDifferences;
	evidence: WatchlistBriefingEvidence;
	selection?: WatchlistBriefingSelection | null;
};

export type AskAnswerConfidence = "grounded" | "limited";

export type AskStorySelectionBasis =
	| "requested_story_id"
	| "query_match"
	| "suggested_story_id"
	| "first_story"
	| "none";

export type WatchlistBriefingPageContext = {
	watchlist_id: string;
	watchlist_name: string | null;
	story_id: string | null;
	selected_story_id: string | null;
	story_headline: string | null;
	topic_key: string | null;
	topic_label: string | null;
	selection_basis: AskStorySelectionBasis;
	question_seed: string | null;
};

export type WatchlistBriefingPage = {
	context: WatchlistBriefingPageContext;
	briefing: WatchlistBriefing;
	selected_story: WatchlistBriefingStoryEvidence | null;
	story_change_summary: string | null;
	citations: AskAnswerContractCitation[];
	routes: WatchlistBriefingRoutes;
	ask_route: string | null;
	compare_route: string | null;
	fallback_reason: string | null;
	fallback_next_step: string | null;
	fallback_actions: AskAnswerFallbackAction[];
};

export type AskAnswerContractContext = {
	watchlist_id: string | null;
	watchlist_name: string | null;
	story_id: string | null;
	selected_story_id: string | null;
	story_headline: string | null;
	topic_key: string | null;
	topic_label: string | null;
	selection_basis: AskStorySelectionBasis;
	mode: RetrievalSearchMode;
	filters: Record<string, string>;
	briefing_available: boolean;
};

export type AskAnswerContractAnswer = {
	direct_answer: string;
	summary: string;
	reason: string | null;
	confidence: AskAnswerConfidence;
};

export type AskAnswerContractChanges = {
	summary: string;
	story_focus_summary: string | null;
	latest_job_id: string | null;
	previous_job_id: string | null;
	added_topics: string[];
	removed_topics: string[];
	added_claim_kinds: string[];
	removed_claim_kinds: string[];
	new_story_keys: string[];
	removed_story_keys: string[];
	compare_excerpt: string | null;
	compare_route: string | null;
	has_previous: boolean;
};

export type AskAnswerCitationKind =
	| "briefing_story"
	| "briefing_card"
	| "retrieval_hit"
	| "job_compare";

export type AskAnswerContractCitation = {
	kind: AskAnswerCitationKind;
	label: string;
	snippet: string;
	source_url: string | null;
	job_id: string | null;
	route: string | null;
	route_label: string | null;
};

export type AskAnswerSelectedStory = {
	story_id: string;
	story_key: string;
	headline: string;
	topic_key: string | null;
	topic_label: string | null;
	source_count: number;
	run_count: number;
	matched_card_count: number;
	platforms: string[];
	claim_kinds: string[];
	source_urls: string[];
	latest_run_job_id: string | null;
	routes: WatchlistBriefingRoutes;
};

export type AskAnswerEvidenceCard = {
	card_id: string | null;
	job_id: string | null;
	platform: string | null;
	source_url: string | null;
	title: string | null;
	body: string;
	source_section: string | null;
};

export type AskAnswerContractEvidence = {
	briefing_overview: string | null;
	selected_story_id: string | null;
	selected_story_headline: string | null;
	latest_job_id: string | null;
	citation_count: number;
	retrieval_hit_count: number;
	retrieval_items: RetrievalHit[];
	story_cards: AskAnswerEvidenceCard[];
};

export type AskAnswerFallbackStatus =
	| "grounded"
	| "limited"
	| "briefing_unavailable"
	| "story_not_found"
	| "insufficient_evidence";

export type AskAnswerContractFallback = {
	status: AskAnswerFallbackStatus;
	reason: string | null;
	suggested_next_step: string | null;
	actions: AskAnswerFallbackAction[];
};

export type AskAnswerFallbackAction = {
	kind:
		| "open_briefing"
		| "open_story"
		| "open_job"
		| "open_knowledge"
		| "open_search";
	label: string;
	route: string | null;
};

export type AskAnswerContractResponse = {
	query: string;
	context: AskAnswerContractContext;
	selected_story: AskAnswerSelectedStory | null;
	answer: AskAnswerContractAnswer;
	changes: AskAnswerContractChanges;
	citations: AskAnswerContractCitation[];
	evidence: AskAnswerContractEvidence;
	fallback: AskAnswerContractFallback;
};

export type AskAnswerState =
	| "briefing_grounded"
	| "missing_context"
	| "briefing_unavailable"
	| "no_confident_answer";

export type AskContext = {
	watchlist_id: string | null;
	watchlist_name: string | null;
	story_id: string | null;
	selected_story_id: string | null;
	story_headline: string | null;
	topic_key: string | null;
	topic_label: string | null;
	selection_basis: AskStorySelectionBasis;
	mode: RetrievalSearchMode;
	filters: Record<string, string>;
	briefing_available: boolean;
};

export type AskAnswerResponse = {
	question: string;
	mode: RetrievalSearchMode;
	top_k: number;
	context: AskContext;
	answer_state: AskAnswerState;
	answer_headline: string | null;
	answer_summary: string | null;
	answer_reason: string | null;
	answer_confidence: AskAnswerConfidence;
	story_change_summary: string | null;
	story_page: WatchlistBriefingPage | null;
	retrieval: RetrievalSearchResponse | null;
	citations: AskAnswerContractCitation[];
	fallback_reason: string | null;
	fallback_next_step: string | null;
	fallback_actions: AskAnswerFallbackAction[];
};

export type JobEvidenceBundle = {
	bundle_kind: string;
	sharing_scope: string;
	sample: boolean;
	generated_at: string;
	proof_boundary: string;
	job: Record<string, unknown>;
	trace_summary: Record<string, unknown>;
	digest: string | null;
	digest_meta: Record<string, unknown> | null;
	comparison: Record<string, unknown> | null;
	knowledge_cards: Record<string, unknown>[];
	artifact_manifest: Record<string, string>;
	step_summary: Record<string, unknown>[];
};

export type ContentType = "video" | "article";

export type DigestFeedItem = {
	feed_id: string;
	job_id: string;
	video_url: string;
	title: string;
	source: Platform | string;
	source_name: string;
	canonical_source_name?: string | null;
	canonical_author_name?: string | null;
	subscription_id?: string | null;
	source_item_id?: string | null;
	affiliation_label?: string | null;
	relation_kind?: string | null;
	thumbnail_url?: string | null;
	avatar_url?: string | null;
	avatar_label?: string | null;
	identity_status?: string | null;
	published_document_id?: string | null;
	published_document_slug?: string | null;
	published_document_title?: string | null;
	published_document_publish_status?: string | null;
	published_with_gap?: boolean | null;
	reader_route?: string | null;
	category: SubscriptionCategory;
	published_at: string;
	summary_md: string;
	artifact_type: "digest" | "outline";
	content_type?: ContentType;
	saved?: boolean;
	feedback_label?: "useful" | "noisy" | "dismissed" | "archived" | null;
};

export type DigestFeedResponse = {
	items: DigestFeedItem[];
	has_more: boolean;
	next_cursor: string | null;
};

export type FeedFeedbackUpdateRequest = {
	job_id: string;
	saved: boolean;
	feedback_label?: "useful" | "noisy" | "dismissed" | "archived" | null;
};

export type RetrievalSearchMode = "keyword" | "semantic" | "hybrid";

export type RetrievalHitSource =
	| "digest"
	| "transcript"
	| "outline"
	| "knowledge_cards"
	| "comments"
	| "meta";

export type RetrievalHit = {
	job_id: string;
	video_id: string;
	platform: string;
	video_uid: string;
	source_url: string;
	title: string | null;
	kind: string;
	mode: string | null;
	source: RetrievalHitSource;
	snippet: string;
	score: number;
};

export type RetrievalSearchResponse = {
	query: string;
	top_k: number;
	filters: Record<string, string>;
	items: RetrievalHit[];
};
