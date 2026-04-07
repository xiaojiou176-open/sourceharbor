import { describe, expect, expectTypeOf, it } from "vitest";

import type {
	DigestFeedResponse,
	Job,
	NotificationConfigUpdateRequest,
	Subscription,
	VideoProcessMode,
	VideoProcessResponse,
} from "@/lib/api/types";

describe("api type contracts", () => {
	it("keeps subscription and notification request contracts", () => {
		const subscription: Subscription = {
			id: "sub-1",
			platform: "youtube",
			source_type: "youtube_channel_id",
			source_value: "UC123",
			source_name: "Test",
			support_tier: "strong_supported",
			content_profile: "video",
			adapter_type: "rsshub_route",
			source_url: null,
			rsshub_route: "",
			category: "tech",
			tags: ["ai"],
			priority: 80,
			enabled: true,
			created_at: "2026-02-01T00:00:00Z",
			updated_at: "2026-02-01T00:00:00Z",
		};

		const update: NotificationConfigUpdateRequest = {
			enabled: true,
			to_email: "a@example.com",
			daily_digest_enabled: true,
			daily_digest_hour_utc: 8,
			failure_alert_enabled: false,
			category_rules: { tech: true },
		};

		expectTypeOf(subscription.category).toEqualTypeOf<
			"tech" | "creator" | "macro" | "ops" | "misc"
		>();
		expectTypeOf(update.daily_digest_hour_utc).toEqualTypeOf<number | null>();
		expect(subscription.source_type).toBe("youtube_channel_id");
		expect(update.enabled).toBe(true);
	});

	it("keeps process response and digest feed contracts", () => {
		const processResponse: VideoProcessResponse = {
			job_id: "job-1",
			video_db_id: "video-db-1",
			video_uid: "uid-1",
			status: "queued",
			idempotency_key: "idem",
			mode: "full",
			overrides: {},
			force: false,
			reused: false,
			workflow_id: null,
		};

		const feed: DigestFeedResponse = {
			items: [],
			has_more: false,
			next_cursor: null,
		};

		expectTypeOf(processResponse.mode).toEqualTypeOf<VideoProcessMode>();
		expectTypeOf(feed.items).toEqualTypeOf<
			Array<DigestFeedResponse["items"][number]>
		>();
		expect(processResponse.status).toBe("queued");
		expect(feed.has_more).toBe(false);
	});

	it("keeps job contract aligned with backend optional retry and thought metadata", () => {
		const job: Job = {
			id: "job-1",
			video_id: "video-1",
			kind: "video_digest_v1",
			status: "running",
			idempotency_key: "idem-1",
			error_message: null,
			artifact_digest_md: null,
			artifact_root: null,
			llm_required: true,
			llm_gate_passed: true,
			hard_fail_reason: null,
			created_at: "2026-02-01T00:00:00Z",
			updated_at: "2026-02-01T00:00:00Z",
			step_summary: [],
			steps: [
				{
					name: "llm_digest",
					status: "running",
					attempt: 1,
					started_at: null,
					finished_at: null,
					error: null,
					error_kind: null,
					retry_meta: null,
					result: null,
					thought_metadata: {},
					cache_key: null,
				},
			],
			degradations: [],
			pipeline_final_status: null,
			artifacts_index: {},
			mode: "full",
			notification_retry: null,
		};

		expectTypeOf(job.kind).toEqualTypeOf<
			"video_digest_v1" | "phase2_ingest_stub"
		>();
		expectTypeOf(job.steps[0].thought_metadata).toEqualTypeOf<
			Record<string, unknown>
		>();
		expectTypeOf(job.notification_retry).toEqualTypeOf<
			Job["notification_retry"]
		>();
		expect(job.kind).toBe("video_digest_v1");
	});
});
