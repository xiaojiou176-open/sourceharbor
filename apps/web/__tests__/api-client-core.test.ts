import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "@/lib/api/client";

describe("apiClient core behavior", () => {
	const envSnapshot = { ...process.env };

	beforeEach(() => {
		process.env = {
			...envSnapshot,
			NEXT_PUBLIC_API_BASE_URL: "https://api.example.com",
		};
	});

	afterEach(() => {
		process.env = { ...envSnapshot };
		vi.restoreAllMocks();
	});

	it("maps auth errors to ERR_AUTH_REQUIRED", async () => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValueOnce(new Response("denied", { status: 401 }))
			.mockResolvedValueOnce(
				new Response(JSON.stringify({ error_code: "ERR_AUTH_REQUIRED" }), {
					status: 403,
				}),
			);

		await expect(apiClient.listVideos()).rejects.toThrow("ERR_AUTH_REQUIRED");
		await expect(apiClient.listVideos()).rejects.toThrow("ERR_AUTH_REQUIRED");
		expect(fetchSpy).toHaveBeenCalledTimes(2);
	});

	it("maps bad request to ERR_INVALID_INPUT", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response("bad", { status: 400 }),
		);

		await expect(
			apiClient.sendNotificationTest({ subject: "x" }),
		).rejects.toThrow("ERR_INVALID_INPUT");
	});

	it("maps unprocessable entity to ERR_INVALID_INPUT", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(JSON.stringify({ detail: "validation failed" }), {
				status: 422,
			}),
		);

		await expect(
			apiClient.sendNotificationTest({ subject: "x" }),
		).rejects.toThrow("ERR_INVALID_INPUT");
	});

	it("maps server errors and not found to ERR_REQUEST_FAILED", async () => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValueOnce(new Response("missing", { status: 404 }))
			.mockResolvedValueOnce(new Response("oops", { status: 503 }));

		await expect(apiClient.getNotificationConfig()).rejects.toThrow(
			"ERR_REQUEST_FAILED",
		);
		await expect(apiClient.getNotificationConfig()).rejects.toThrow(
			"ERR_REQUEST_FAILED",
		);
		expect(fetchSpy).toHaveBeenCalledTimes(2);
	});

	it("maps upstream body codes before generic status fallbacks", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({ message: "ERR_REQUEST_FAILED upstream exploded" }),
				{
					status: 500,
				},
			),
		);

		await expect(apiClient.getNotificationConfig()).rejects.toThrow(
			"ERR_REQUEST_FAILED",
		);
	});

	it("maps explicit body error codes before status fallback for bad requests", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(JSON.stringify({ error_code: "ERR_INVALID_INPUT" }), {
				status: 400,
			}),
		);

		await expect(
			apiClient.sendNotificationTest({ subject: "x" }),
		).rejects.toThrow("ERR_INVALID_INPUT");
	});

	it("throws ERR_PROTOCOL_EMPTY_BODY for 200 responses with empty body", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(null, { status: 200 }),
		);

		await expect(apiClient.getNotificationConfig()).rejects.toThrow(
			"ERR_PROTOCOL_EMPTY_BODY",
		);
	});

	it("sends JSON payload with no-store caching", async () => {
		const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({
					run_id: "run-1",
					workflow_id: "wf-1",
					status: "queued",
					enqueued: 0,
					candidates: [],
				}),
				{ status: 200 },
			),
		);

		await apiClient.pollIngest({ max_new_videos: 20 });

		const [, options] = fetchSpy.mock.calls[0];
		const headers =
			options?.headers instanceof Headers
				? Object.fromEntries(options.headers.entries())
				: options?.headers;
		expect(options).toMatchObject({
			method: "POST",
			cache: "no-store",
			body: JSON.stringify({ max_new_videos: 20 }),
		});
		expect(headers).toMatchObject({ "content-type": "application/json" });
	});

	it("loads Ask from the server-owned page payload route", async () => {
		const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({
					question: "retry policy",
					mode: "keyword",
					top_k: 6,
					context: {
						watchlist_id: "wl-1",
						watchlist_name: "Retry policy",
						story_id: "story-1",
						selected_story_id: "story-1",
						story_headline: "Retry Policy",
						topic_key: "retry-policy",
						topic_label: "Retry policy",
						selection_basis: "requested_story_id",
						mode: "keyword",
						filters: {},
						briefing_available: true,
					},
					answer_state: "briefing_grounded",
					answer_headline: "Retry Policy",
					answer_summary:
						"Retry policy currently converges across recent sources.",
					answer_reason: "The newest runs keep repeating the retry baseline.",
					answer_confidence: "grounded",
					story_change_summary:
						"Retry policy keeps tightening into the default path.",
					story_page: null,
					retrieval: null,
					citations: [],
					fallback_reason: null,
					fallback_next_step: null,
					fallback_actions: [],
				}),
				{ status: 200 },
			),
		);

		const payload = await apiClient.getAskAnswer({
			question: "retry policy",
			watchlist_id: "wl-1",
			story_id: "story-1",
			topic_key: "retry-policy",
			top_k: 6,
			mode: "keyword",
		});

		expect(payload.context.selected_story_id).toBe("story-1");
		const [url, options] = fetchSpy.mock.calls[0] ?? [];
		expect(String(url)).toContain("/api/v1/retrieval/answer/page");
		expect(options).toMatchObject({
			method: "POST",
			cache: "no-store",
			body: JSON.stringify({
				query: "retry policy",
				watchlist_id: "wl-1",
				story_id: "story-1",
				topic_key: "retry-policy",
				top_k: 6,
				mode: "keyword",
				filters: {},
			}),
		});
	});

	it("loads briefing page from the server-owned page payload route", async () => {
		const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({
					context: {
						watchlist_id: "wl-1",
						watchlist_name: "Retry policy",
						story_id: "story-1",
						selected_story_id: "story-1",
						story_headline:
							"Retries moved from optional advice to default posture",
						topic_key: "retry-policy",
						topic_label: "Retry policy",
						selection_basis: "requested_story_id",
						question_seed:
							"Retries moved from optional advice to default posture",
					},
					briefing: {
						watchlist: {
							id: "wl-1",
							name: "Retry policy",
							matcher_type: "topic_key",
							matcher_value: "retry-policy",
							delivery_channel: "dashboard",
							enabled: true,
							created_at: "2026-03-31T10:00:00Z",
							updated_at: "2026-03-31T10:00:00Z",
						},
						summary: {
							overview:
								"Retry policy currently converges across recent sources.",
							source_count: 3,
							run_count: 4,
							story_count: 1,
							matched_cards: 6,
							primary_story_headline:
								"Retries moved from optional advice to default posture",
							signals: [],
						},
						differences: {
							latest_job_id: "job-3",
							previous_job_id: "job-2",
							added_topics: ["retry-policy"],
							removed_topics: [],
							added_claim_kinds: ["recommendation"],
							removed_claim_kinds: [],
							new_story_keys: ["topic:retry-policy"],
							removed_story_keys: [],
							compare: null,
						},
						evidence: {
							suggested_story_id: "story-1",
							stories: [],
							featured_runs: [],
						},
						selection: {
							selected_story_id: "story-1",
							selection_basis: "requested_story_id",
							story: null,
						},
					},
					selected_story: null,
					story_change_summary: null,
					citations: [],
					routes: {
						watchlist_trend: "/trends?watchlist_id=wl-1",
						briefing: "/briefings?watchlist_id=wl-1&story_id=story-1",
						ask: "/ask?watchlist_id=wl-1&question=Retries+moved+from+optional+advice+to+default+posture&story_id=story-1&topic_key=retry-policy",
						job_compare: "/jobs?job_id=job-3",
						job_bundle: "/api/v1/jobs/job-3/bundle",
						job_knowledge_cards: "/knowledge?job_id=job-3",
					},
					ask_route:
						"/ask?watchlist_id=wl-1&question=Retries+moved+from+optional+advice+to+default+posture&story_id=story-1&topic_key=retry-policy",
					compare_route: "/jobs?job_id=job-3",
					fallback_reason: null,
					fallback_next_step: null,
					fallback_actions: [],
				}),
				{ status: 200 },
			),
		);

		const payload = await apiClient.getWatchlistBriefingPage("wl-1", {
			story_id: "story-1",
		});

		expect(payload.context.selected_story_id).toBe("story-1");
		expect(payload.ask_route).toContain(
			"question=Retries+moved+from+optional+advice+to+default+posture",
		);
		const [url] = fetchSpy.mock.calls[0] ?? [];
		expect(String(url)).toContain("/api/v1/watchlists/wl-1/briefing/page");
		expect(String(url)).toContain("story_id=story-1");
	});

	it("loads one ingest run by id", async () => {
		const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({
					id: "run-1",
					subscription_id: null,
					workflow_id: "wf-1",
					platform: "youtube",
					max_new_videos: 10,
					status: "queued",
					jobs_created: 0,
					candidates_count: 0,
					feeds_polled: 0,
					entries_fetched: 0,
					entries_normalized: 0,
					ingest_events_created: 0,
					ingest_event_duplicates: 0,
					job_duplicates: 0,
					error_message: null,
					created_at: "2026-03-29T00:00:00Z",
					updated_at: "2026-03-29T00:00:00Z",
					completed_at: null,
					requested_by: null,
					requested_trace_id: null,
					filters_json: null,
					items: [],
				}),
				{ status: 200 },
			),
		);

		const payload = await apiClient.getIngestRun("run-1");

		expect(payload.id).toBe("run-1");
		expect(payload.workflow_id).toBe("wf-1");
		expect(fetchSpy.mock.calls[0]?.[0]).toContain("/api/v1/ingest/runs/run-1");
	});

	it("lists ingest runs with query params", async () => {
		const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify([
					{
						id: "run-2",
						subscription_id: null,
						workflow_id: "wf-2",
						platform: "youtube",
						max_new_videos: 5,
						status: "succeeded",
						jobs_created: 2,
						candidates_count: 2,
						feeds_polled: 1,
						entries_fetched: 2,
						entries_normalized: 2,
						ingest_events_created: 2,
						ingest_event_duplicates: 0,
						job_duplicates: 0,
						error_message: null,
						created_at: "2026-03-29T00:00:00Z",
						updated_at: "2026-03-29T00:00:00Z",
						completed_at: "2026-03-29T00:01:00Z",
					},
				]),
				{ status: 200 },
			),
		);

		const payload = await apiClient.listIngestRuns({
			platform: "youtube",
			status: "succeeded",
			limit: 5,
		});

		expect(payload[0]?.id).toBe("run-2");
		const requestUrl = String(fetchSpy.mock.calls[0]?.[0] ?? "");
		expect(requestUrl).toContain("/api/v1/ingest/runs?");
		expect(requestUrl).toContain("status=succeeded");
		expect(requestUrl).toContain("platform=youtube");
		expect(requestUrl).toContain("limit=5");
	});

	it("adds write access token headers for mutating requests", async () => {
		const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({
					job_id: "job-3",
					video_db_id: "video-3",
					video_uid: "uid-3",
					status: "queued",
					idempotency_key: "idem-3",
					mode: "full",
					overrides: {},
					force: false,
					reused: false,
					workflow_id: null,
				}),
				{ status: 200 },
			),
		);

		await apiClient.processVideo(
			{ video: { platform: "youtube", url: "https://example.com/watch?v=1" } },
			{ writeAccessToken: "token-123" },
		);

		const [, options] = fetchSpy.mock.calls[0];
		const headers =
			options?.headers instanceof Headers
				? Object.fromEntries(options.headers.entries())
				: options?.headers;
		expect(headers).toMatchObject({
			authorization: "Bearer token-123",
			"x-api-key": "token-123",
		});
	});

	it("adds web session header for mutating requests when write token is absent", async () => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValue(
				new Response(JSON.stringify({ updated: 2 }), { status: 200 }),
			);

		await apiClient.batchUpdateSubscriptionCategory(
			{ ids: ["sub-1"], category: "tech" },
			{ webSessionToken: "session-123" },
		);

		const [, options] = fetchSpy.mock.calls[0];
		const headers =
			options?.headers instanceof Headers
				? Object.fromEntries(options.headers.entries())
				: options?.headers;
		expect(headers).toMatchObject({ "x-web-session": "session-123" });
		expect(headers).not.toHaveProperty("authorization");
	});

	it("normalizes malformed job payload arrays and maps", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({
					id: "job-1",
					video_id: "video-1",
					kind: "video_digest_v1",
					status: "running",
					idempotency_key: "idem-1",
					error_message: null,
					artifact_digest_md: null,
					artifact_root: null,
					llm_required: null,
					llm_gate_passed: null,
					hard_fail_reason: null,
					created_at: "2026-02-26T00:00:00Z",
					updated_at: "2026-02-26T00:00:00Z",
					step_summary: null,
					steps: "broken",
					degradations: { x: 1 },
					pipeline_final_status: null,
					artifacts_index: { digest: "a.md", bad: 123 },
					mode: undefined,
					notification_retry: undefined,
				}),
				{ status: 200 },
			),
		);

		const job = await apiClient.getJob("job-1");
		expect(job.step_summary).toEqual([]);
		expect(job.steps).toEqual([]);
		expect(job.degradations).toEqual([]);
		expect(job.artifacts_index).toEqual({ digest: "a.md" });
		expect(job.mode).toBeNull();
		expect(job.notification_retry).toBeNull();
	});

	it("loads job compare payload", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({
					job_id: "job-1",
					previous_job_id: "job-0",
					has_previous: true,
					current_digest: "# Current",
					previous_digest: "# Previous",
					diff_markdown: "--- old\n+++ new",
					stats: { added_lines: 1, removed_lines: 1, changed: true },
				}),
				{ status: 200 },
			),
		);

		const payload = await apiClient.getJobCompare("job-1");

		expect(payload.job_id).toBe("job-1");
		expect(payload.previous_job_id).toBe("job-0");
		expect(payload.stats.changed).toBe(true);
	});

	it("gets and updates feed feedback", async () => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						job_id: "job-1",
						saved: true,
						feedback_label: "useful",
						exists: true,
						created_at: "2026-03-29T00:00:00Z",
						updated_at: "2026-03-29T00:00:00Z",
					}),
					{ status: 200 },
				),
			)
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						job_id: "job-1",
						saved: false,
						feedback_label: "dismissed",
						exists: true,
						created_at: "2026-03-29T00:00:00Z",
						updated_at: "2026-03-29T00:05:00Z",
					}),
					{ status: 200 },
				),
			);

		const current = await apiClient.getFeedFeedback("job-1");
		const updated = await apiClient.updateFeedFeedback(
			{ job_id: "job-1", saved: false, feedback_label: "dismissed" },
			{ webSessionToken: "session-1" },
		);

		expect(current.feedback_label).toBe("useful");
		expect(updated.feedback_label).toBe("dismissed");
		expect(String(fetchSpy.mock.calls[0]?.[0])).toContain(
			"/api/v1/feed/feedback?job_id=job-1",
		);
	});

	it("loads job knowledge cards payload", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify([
					{
						card_type: "takeaway",
						title: "Key takeaway",
						body: "This is reusable.",
						source_section: "highlights",
						order_index: 1,
					},
				]),
				{ status: 200 },
			),
		);

		const payload = await apiClient.getJobKnowledgeCards("job-1");

		expect(payload[0]?.card_type).toBe("takeaway");
		expect(payload[0]?.title).toBe("Key takeaway");
	});

	it("normalizes knowledge card list payloads that use ordinal", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify([
					{
						id: "card-1",
						job_id: "job-1",
						video_id: "video-1",
						card_type: "summary",
						source_section: "overview",
						title: null,
						body: "Long-lived fact",
						ordinal: 3,
						metadata_json: { confidence: "high" },
						created_at: "2026-03-29T00:00:00Z",
						updated_at: "2026-03-29T00:00:00Z",
					},
				]),
				{ status: 200 },
			),
		);

		const payload = await apiClient.listKnowledgeCards({ limit: 5 });

		expect(payload).toEqual([
			{
				id: "card-1",
				job_id: "job-1",
				video_id: "video-1",
				card_type: "summary",
				title: null,
				body: "Long-lived fact",
				source_section: "overview",
				order_index: 3,
				metadata_json: { confidence: "high" },
				created_at: "2026-03-29T00:00:00Z",
				updated_at: "2026-03-29T00:00:00Z",
			},
		]);
	});

	it("normalizes retrieval search responses and filters malformed hits", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({
					query: "agent workflows",
					top_k: 8,
					filters: { platform: "youtube", ignored: 2 },
					items: [
						{
							job_id: "job-1",
							video_id: "video-1",
							platform: "youtube",
							video_uid: "vid-1",
							source_url: "https://www.youtube.com/watch?v=abc",
							title: "AI Weekly",
							kind: "video_digest_v1",
							mode: "full",
							source: "knowledge_cards",
							snippet: "Agent workflows with retry loops.",
							score: 1.8,
						},
						{
							job_id: "",
							video_id: "video-2",
							source: "digest",
							snippet: "bad row",
						},
					],
				}),
				{ status: 200 },
			),
		);

		const payload = await apiClient.searchRetrieval({
			query: "agent workflows",
			mode: "keyword",
			top_k: 8,
			filters: { platform: "youtube" },
		});

		expect(payload.query).toBe("agent workflows");
		expect(payload.filters).toEqual({ platform: "youtube" });
		expect(payload.items).toHaveLength(1);
		expect(payload.items[0]?.source).toBe("knowledge_cards");
		expect(payload.items[0]?.snippet).toContain("Agent workflows");
	});

	it("supports plain text artifact markdown endpoint", async () => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValue(new Response("# hello", { status: 200 }));

		await expect(
			apiClient.getArtifactMarkdown({ job_id: "job-1" }),
		).resolves.toBe("# hello");
		const [url] = fetchSpy.mock.calls[0];
		expect(String(url)).toContain("/api/v1/artifacts/markdown");
		expect(String(url)).toContain("job_id=job-1");
	});

	it("returns undefined for successful 204 delete responses", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(null, { status: 204 }),
		);

		await expect(
			apiClient.deleteSubscription("sub-1"),
		).resolves.toBeUndefined();
	});

	it("returns plain text bodies from text endpoints even when empty", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response("", { status: 200 }),
		);

		await expect(
			apiClient.getArtifactMarkdown({ job_id: "job-1" }),
		).resolves.toBe("");
	});

	it("maps auth errors for text endpoints", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response("denied", { status: 403 }),
		);

		await expect(
			apiClient.getArtifactMarkdown({ job_id: "job-1" }),
		).rejects.toThrow("ERR_AUTH_REQUIRED");
	});

	it("maps malformed JSON response bodies to ERR_REQUEST_FAILED", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response("not-json", { status: 200 }),
		);

		await expect(apiClient.getNotificationConfig()).rejects.toThrow(
			"ERR_REQUEST_FAILED",
		);
	});

	it("maps network errors to ERR_REQUEST_FAILED for text endpoints", async () => {
		vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network down"));

		await expect(
			apiClient.getArtifactMarkdown({ job_id: "job-1" }),
		).rejects.toThrow("ERR_REQUEST_FAILED");
	});

	it("preserves local query validation error code from buildApiUrl", async () => {
		const fetchSpy = vi.spyOn(globalThis, "fetch");

		await expect(
			apiClient.getDigestFeed({
				limit: 20,
				session_token: "abc",
			} as unknown as Parameters<typeof apiClient.getDigestFeed>[0]),
		).rejects.toThrow("ERR_SENSITIVE_QUERY_KEY:session_token");
		expect(fetchSpy).not.toHaveBeenCalled();
	});

	it("normalizes malformed feed payload to keep page rendering safe", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({
					items: [
						null,
						{
							feed_id: "feed-1",
							job_id: "job-1",
							video_url: 1,
							title: null,
							source: "youtube",
							source_name: null,
							category: "",
							published_at: 123,
							summary_md: { x: 1 },
							artifact_type: "unknown",
						},
						{ feed_id: "", job_id: "missing" },
					],
					has_more: "unknown",
					next_cursor: 123,
				}),
				{ status: 200 },
			),
		);

		const feed = await apiClient.getDigestFeed();
		expect(feed.has_more).toBe(false);
		expect(feed.next_cursor).toBeNull();
		expect(feed.items).toEqual([
			{
				feed_id: "feed-1",
				job_id: "job-1",
				video_url: "",
				title: "",
				source: "youtube",
				source_name: "",
				category: "misc",
				published_at: "",
				summary_md: "",
				artifact_type: "digest",
				content_type: "video",
				saved: false,
				feedback_label: null,
			},
		]);
	});

	it("normalizes article feed items and preserves known artifact type", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({
					items: [
						{
							feed_id: "feed-2",
							job_id: "job-2",
							source: "rss",
							category: "ops",
							artifact_type: "outline",
							content_type: "article",
						},
					],
					has_more: true,
					next_cursor: "cursor-2",
				}),
				{ status: 200 },
			),
		);

		const feed = await apiClient.getDigestFeed();
		expect(feed.has_more).toBe(true);
		expect(feed.next_cursor).toBe("cursor-2");
		expect(feed.items[0]?.content_type).toBe("article");
		expect(feed.items[0]?.artifact_type).toBe("outline");
		expect(feed.items[0]?.category).toBe("ops");
	});

	it("normalizes artifact markdown meta response shape", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(JSON.stringify({ markdown: 1, meta: [] }), { status: 200 }),
		);

		await expect(
			apiClient.getArtifactMarkdown({ job_id: "job-1", include_meta: true }),
		).resolves.toEqual({
			markdown: "",
			meta: null,
		});
	});

	it("covers additional client endpoints with query/body wiring", async () => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						job_id: "job-2",
						video_db_id: "video-2",
						video_uid: "uid-2",
						status: "queued",
						idempotency_key: "idem-2",
						mode: "full",
						overrides: {},
						force: false,
						reused: false,
						workflow_id: null,
					}),
					{ status: 200 },
				),
			)
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						enabled: true,
						to_email: "a@example.com",
						daily_digest_enabled: false,
						daily_digest_hour_utc: null,
						failure_alert_enabled: true,
						category_rules: {},
						created_at: "2026-02-26T00:00:00Z",
						updated_at: "2026-02-26T00:00:00Z",
					}),
					{ status: 200 },
				),
			)
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({ items: [], has_more: false, next_cursor: null }),
					{
						status: 200,
					},
				),
			);

		await apiClient.processVideo({
			video: { platform: "youtube", url: "https://example.com/v/1" },
			force: false,
		});
		await apiClient.updateNotificationConfig({
			enabled: true,
			to_email: "a@example.com",
			daily_digest_enabled: false,
			daily_digest_hour_utc: null,
			failure_alert_enabled: true,
			category_rules: {},
		});
		await apiClient.getDigestFeed({
			source: "youtube",
			sort: "curated",
			subscription_id: "sub-1",
			limit: 20,
		});

		expect(fetchSpy).toHaveBeenCalledTimes(3);
		const [processUrl, processOpts] = fetchSpy.mock.calls[0];
		expect(String(processUrl)).toContain("/api/v1/videos/process");
		expect(processOpts).toMatchObject({ method: "POST" });

		const [feedUrl] = fetchSpy.mock.calls[2];
		expect(String(feedUrl)).toContain("/api/v1/feed/digests");
		expect(String(feedUrl)).toContain("source=youtube");
		expect(String(feedUrl)).toContain("sort=curated");
		expect(String(feedUrl)).toContain("sub=sub-1");
		expect(String(feedUrl)).toContain("limit=20");
	});

	it("covers subscription endpoints and artifact markdown error path", async () => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify([
						{
							id: "sub-1",
							platform: "youtube",
							source_type: "url",
							source_value: "https://www.youtube.com/@x",
							adapter_type: "rsshub_route",
							source_url: null,
							rsshub_route: "/youtube/channel/abc",
							category: "tech",
							tags: [],
							priority: 50,
							enabled: true,
							created_at: "2026-02-01T00:00:00Z",
							updated_at: "2026-02-01T00:00:00Z",
						},
					]),
					{ status: 200 },
				),
			)
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						ok: true,
						subscription_id: "sub-1",
						action: "created",
					}),
					{
						status: 200,
					},
				),
			)
			.mockResolvedValueOnce(
				new Response(JSON.stringify({ updated: 1 }), { status: 200 }),
			)
			.mockResolvedValueOnce(new Response(null, { status: 204 }))
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						processed_count: 1,
						created_subscriptions: 0,
						updated_subscriptions: 1,
						queued_manual_items: 0,
						reused_manual_items: 0,
						rejected_count: 0,
						results: [],
					}),
					{ status: 200 },
				),
			)
			.mockResolvedValueOnce(new Response("server down", { status: 503 }));

		await apiClient.listSubscriptions({
			platform: "youtube",
			enabled_only: true,
		});
		await apiClient.upsertSubscription({
			platform: "youtube",
			source_type: "url",
			source_value: "https://www.youtube.com/@x",
			adapter_type: "rsshub_route",
			category: "tech",
		});
		await apiClient.batchUpdateSubscriptionCategory({
			ids: ["sub-1"],
			category: "creator",
		});
		await apiClient.deleteSubscription("sub-1");
		await apiClient.submitManualSourceIntake({
			raw_input: "https://www.youtube.com/@x",
		});
		await expect(
			apiClient.getArtifactMarkdown({ job_id: "job-2" }),
		).rejects.toThrow("ERR_REQUEST_FAILED");

		expect(fetchSpy).toHaveBeenCalledTimes(6);
		expect(String(fetchSpy.mock.calls[0][0])).toContain(
			"/api/v1/subscriptions",
		);
		expect(String(fetchSpy.mock.calls[0][0])).toContain("platform=youtube");
		expect(String(fetchSpy.mock.calls[0][0])).toContain("enabled_only=true");
		expect(fetchSpy.mock.calls[1][1]).toMatchObject({ method: "POST" });
		expect(String(fetchSpy.mock.calls[3][0])).toContain(
			"/api/v1/subscriptions/sub-1",
		);
		expect(fetchSpy.mock.calls[3][1]).toMatchObject({ method: "DELETE" });
		expect(String(fetchSpy.mock.calls[4][0])).toContain(
			"/api/v1/subscriptions/manual-intake",
		);
		expect(fetchSpy.mock.calls[4][1]).toMatchObject({ method: "POST" });
	});

	it("normalizes digest booleans and cursor from non-string payloads", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({
					items: [],
					has_more: 1,
					next_cursor: 123,
				}),
				{ status: 200 },
			),
		);

		const result = await apiClient.getDigestFeed();
		expect(result.has_more).toBe(true);
		expect(result.next_cursor).toBeNull();
	});

	it("calls reader pipeline routes through the shared api client", async () => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						consumption_batch_id: "batch-1",
						cluster_verdict_manifest_id: "manifest-1",
						window_id: "2026-04-09@America/Los_Angeles",
						published_document_count: 1,
						published_with_gap_count: 0,
						documents: [],
						navigation_brief: {
							brief_kind: "sourceharbor_navigation_brief_v1",
							generated_at: "2026-04-09T00:00:00Z",
							window_id: "2026-04-09@America/Los_Angeles",
							document_count: 1,
							published_with_gap_count: 0,
							summary: "Read 1 published reader documents.",
							items: [],
						},
					}),
					{ status: 200 },
				),
			)
			.mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						id: "doc-1",
						stable_key: "topic-ai-agents-2026-04-09",
						slug: "ai-agents-2026-04-09-v1",
						window_id: "2026-04-09@America/Los_Angeles",
						title: "AI Agents",
						summary: "Merged reader doc",
						markdown: "# AI Agents",
						materialization_mode: "merge_then_polish",
						version: 1,
						published_with_gap: false,
						is_current: true,
						source_item_count: 2,
						consumption_batch_id: "batch-1",
						cluster_verdict_manifest_id: "manifest-1",
						supersedes_document_id: null,
						warning: {},
						coverage_ledger: {},
						traceability_pack: {},
						source_refs: [],
						sections: [],
						repair_history: [],
						created_at: "2026-04-09T00:00:00Z",
						updated_at: "2026-04-09T00:00:00Z",
					}),
					{ status: 200 },
				),
			)
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						id: "doc-1",
						stable_key: "topic-ai-agents-2026-04-09",
						slug: "ai-agents-2026-04-09-v2",
						window_id: "2026-04-09@America/Los_Angeles",
						title: "AI Agents",
						summary: "Merged reader doc",
						markdown: "# AI Agents",
						materialization_mode: "repair_patch",
						version: 2,
						published_with_gap: true,
						is_current: true,
						source_item_count: 2,
						consumption_batch_id: "batch-1",
						cluster_verdict_manifest_id: "manifest-1",
						supersedes_document_id: "doc-0",
						warning: {
							warning_kind: "coverage_gap",
							published_with_gap: true,
							reasons: ["1 source missing digest output"],
							failed_source_count: 1,
							degraded_source_count: 0,
							missing_digest_count: 1,
							generated_at: "2026-04-09T00:00:00Z",
						},
						coverage_ledger: {},
						traceability_pack: {},
						source_refs: [],
						sections: [],
						repair_history: [],
						created_at: "2026-04-09T00:00:00Z",
						updated_at: "2026-04-09T00:00:00Z",
					}),
					{ status: 200 },
				),
			)
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						brief_kind: "sourceharbor_navigation_brief_v1",
						generated_at: "2026-04-09T00:00:00Z",
						window_id: "2026-04-09@America/Los_Angeles",
						document_count: 1,
						published_with_gap_count: 1,
						summary: "Read 1 published reader documents.",
						items: [],
					}),
					{ status: 200 },
				),
			);

		await apiClient.materializeConsumptionBatch("batch-1");
		await apiClient.listPublishedReaderDocuments({
			limit: 5,
			window_id: "2026-04-09@America/Los_Angeles",
		});
		await apiClient.getPublishedReaderDocument("doc-1");
		await apiClient.repairPublishedReaderDocument("doc-1", {
			repair_mode: "patch",
		});
		await apiClient.getNavigationBrief({ limit: 3 });

		expect(fetchSpy).toHaveBeenCalledTimes(5);
		expect(String(fetchSpy.mock.calls[0][0])).toContain(
			"/api/v1/reader/batches/batch-1/materialize",
		);
		expect(fetchSpy.mock.calls[0][1]).toMatchObject({ method: "POST" });
		expect(String(fetchSpy.mock.calls[1][0])).toContain(
			"/api/v1/reader/documents",
		);
		expect(String(fetchSpy.mock.calls[1][0])).toContain("limit=5");
		expect(String(fetchSpy.mock.calls[1][0])).toContain(
			"window_id=2026-04-09%40America%2FLos_Angeles",
		);
		expect(String(fetchSpy.mock.calls[2][0])).toContain(
			"/api/v1/reader/documents/doc-1",
		);
		expect(String(fetchSpy.mock.calls[3][0])).toContain(
			"/api/v1/reader/documents/doc-1/repair",
		);
		expect(fetchSpy.mock.calls[3][1]).toMatchObject({ method: "POST" });
		expect(String(fetchSpy.mock.calls[4][0])).toContain(
			"/api/v1/reader/navigation-brief",
		);
		expect(String(fetchSpy.mock.calls[4][0])).toContain("limit=3");
	});

	it("extracts structured error code from JSON body fields", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({ message: "prefix ERR_RATE_LIMITED suffix" }),
				{
					status: 429,
				},
			),
		);

		await expect(apiClient.getNotificationConfig()).rejects.toThrow(
			"ERR_RATE_LIMITED",
		);
	});

	it("falls back to ERR_REQUEST_FAILED for unmapped status with non-object JSON body", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response("[]", { status: 418 }),
		);

		await expect(apiClient.getNotificationConfig()).rejects.toThrow(
			"ERR_REQUEST_FAILED",
		);
	});

	it("maps requestJson network failures to ERR_REQUEST_FAILED", async () => {
		vi.spyOn(globalThis, "fetch").mockRejectedValue(
			new Error("network offline"),
		);

		await expect(apiClient.listVideos()).rejects.toThrow("ERR_REQUEST_FAILED");
	});

	it("rejects invalid identifiers before issuing network requests", async () => {
		const fetchSpy = vi.spyOn(globalThis, "fetch");

		expect(() => apiClient.getJob("../unsafe")).toThrow(
			"ERR_INVALID_IDENTIFIER",
		);
		expect(() => apiClient.deleteSubscription("unsafe id")).toThrow(
			"ERR_INVALID_IDENTIFIER",
		);
		expect(fetchSpy).not.toHaveBeenCalled();
	});

	it("rejects unsafe external artifact URLs before network calls", async () => {
		const fetchSpy = vi.spyOn(globalThis, "fetch");

		expect(() =>
			apiClient.getArtifactMarkdown({ video_url: "javascript:alert(1)" }),
		).toThrow("ERR_INVALID_INPUT");
		expect(fetchSpy).not.toHaveBeenCalled();
	});

	it("falls back to web session auth when write token is blank after trim", async () => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValue(
				new Response(JSON.stringify({ updated: 1 }), { status: 200 }),
			);

		await apiClient.batchUpdateSubscriptionCategory(
			{ ids: ["sub-1"], category: "ops" },
			{ writeAccessToken: "   ", webSessionToken: "session-fallback" },
		);

		const [, options] = fetchSpy.mock.calls[0];
		const headers =
			options?.headers instanceof Headers
				? Object.fromEntries(options.headers.entries())
				: options?.headers;
		expect(headers).toMatchObject({ "x-web-session": "session-fallback" });
		expect(headers).not.toHaveProperty("authorization");
		expect(headers).not.toHaveProperty("x-api-key");
	});

	it("extracts ERR_ code from code and detail fields in error payload", async () => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValueOnce(
				new Response(JSON.stringify({ code: "ERR_THROTTLED" }), {
					status: 429,
				}),
			)
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({ detail: "upstream ERR_BACKEND_UNAVAILABLE" }),
					{
						status: 502,
					},
				),
			);

		await expect(apiClient.getNotificationConfig()).rejects.toThrow(
			"ERR_THROTTLED",
		);
		await expect(apiClient.getNotificationConfig()).rejects.toThrow(
			"ERR_BACKEND_UNAVAILABLE",
		);
		expect(fetchSpy).toHaveBeenCalledTimes(2);
	});

	it("normalizes string booleans and infers article content type for non-video sources", async () => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						items: [
							{
								feed_id: "feed-3",
								job_id: "job-3",
								source: "newsletter",
								category: "tech",
							},
						],
						has_more: "yes",
						next_cursor: null,
					}),
					{ status: 200 },
				),
			)
			.mockResolvedValueOnce(
				new Response(
					JSON.stringify({
						items: [],
						has_more: "off",
						next_cursor: null,
					}),
					{ status: 200 },
				),
			);

		const yesResult = await apiClient.getDigestFeed();
		const offResult = await apiClient.getDigestFeed();
		expect(fetchSpy).toHaveBeenCalledTimes(2);
		expect(yesResult.has_more).toBe(true);
		expect(yesResult.items[0]?.content_type).toBe("article");
		expect(yesResult.items[0]?.category).toBe("tech");
		expect(offResult.has_more).toBe(false);
	});

	it("does not attach auth headers to read requests even when tokens are provided", async () => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValue(
				new Response(
					JSON.stringify({ items: [], has_more: false, next_cursor: null }),
					{ status: 200 },
				),
			);

		await apiClient.getDigestFeed({ source: "youtube" });

		const [, options] = fetchSpy.mock.calls[0];
		const headers =
			options?.headers instanceof Headers
				? Object.fromEntries(options.headers.entries())
				: options?.headers;
		expect(headers).not.toHaveProperty("authorization");
		expect(headers).not.toHaveProperty("x-api-key");
		expect(headers).not.toHaveProperty("x-web-session");
	});

	it("prefers write token over web session token for mutating requests", async () => {
		const fetchSpy = vi
			.spyOn(globalThis, "fetch")
			.mockResolvedValue(
				new Response(JSON.stringify({ updated: 1 }), { status: 200 }),
			);

		await apiClient.batchUpdateSubscriptionCategory(
			{ ids: ["sub-1"], category: "creator" },
			{ writeAccessToken: "write-token", webSessionToken: "session-token" },
		);

		const [, options] = fetchSpy.mock.calls[0];
		const headers =
			options?.headers instanceof Headers
				? Object.fromEntries(options.headers.entries())
				: options?.headers;
		expect(headers).toMatchObject({
			authorization: "Bearer write-token",
			"x-api-key": "write-token",
		});
		expect(headers).not.toHaveProperty("x-web-session");
	});

	it("normalizes empty artifacts_index and malformed step records safely", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({
					id: "job-2",
					video_id: "video-2",
					kind: "video_digest_v1",
					status: "succeeded",
					idempotency_key: "idem-2",
					error_message: null,
					artifact_digest_md: null,
					artifact_root: null,
					llm_required: null,
					llm_gate_passed: null,
					hard_fail_reason: null,
					created_at: "2026-02-26T00:00:00Z",
					updated_at: "2026-02-26T00:00:00Z",
					step_summary: [],
					steps: [
						null,
						{
							name: "outline",
							thought_metadata: [],
						},
					],
					degradations: [],
					pipeline_final_status: null,
					artifacts_index: [],
					mode: null,
					notification_retry: null,
				}),
				{ status: 200 },
			),
		);

		const job = await apiClient.getJob("job-2");
		expect(job.artifacts_index).toEqual({});
		expect(job.steps).toHaveLength(1);
		expect(job.steps[0]?.thought_metadata).toEqual({});
	});

	it("normalizes object thought metadata and absent metadata while dropping non-object steps", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({
					id: "job-steps",
					video_id: "video-steps",
					kind: "video_digest_v1",
					status: "running",
					idempotency_key: "idem-steps",
					error_message: null,
					artifact_digest_md: null,
					artifact_root: null,
					llm_required: null,
					llm_gate_passed: null,
					hard_fail_reason: null,
					created_at: "2026-02-26T00:00:00Z",
					updated_at: "2026-02-26T00:00:00Z",
					step_summary: [],
					steps: [
						"bad-step",
						{ name: "extract", thought_metadata: { attempt: 1 } },
						{ name: "publish" },
					],
					degradations: [],
					pipeline_final_status: null,
					artifacts_index: null,
					mode: null,
					notification_retry: null,
				}),
				{ status: 200 },
			),
		);

		const job = await apiClient.getJob("job-steps");
		expect(job.steps).toHaveLength(2);
		expect(job.steps[0]?.thought_metadata).toEqual({ attempt: 1 });
		expect(job.steps[1]?.thought_metadata).toEqual({});
		expect(job.artifacts_index).toEqual({});
	});

	it("treats non-primitive digest has_more payload as false", async () => {
		vi.spyOn(globalThis, "fetch").mockResolvedValue(
			new Response(
				JSON.stringify({
					items: [],
					has_more: { next: true },
					next_cursor: null,
				}),
				{ status: 200 },
			),
		);

		const feed = await apiClient.getDigestFeed();
		expect(feed.has_more).toBe(false);
	});
});
