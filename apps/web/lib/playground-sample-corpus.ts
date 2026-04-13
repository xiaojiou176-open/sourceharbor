export const PLAYGROUND_SAMPLE_CORPUS = {
	label: "SourceHarbor Demo Corpus",
	sample: true,
	description:
		"Curated sample data for read-only demos, playgrounds, and landing pages. Not live operator state.",
	sources: [
		{
			platform: "youtube",
			title: "AI Weekly Ops",
			url: "https://example.com/sample/youtube-ai-weekly-ops",
		},
		{
			platform: "bilibili",
			title: "Bilibili Agent Notes",
			url: "https://example.com/sample/bilibili-agent-notes",
		},
		{
			platform: "rss",
			title: "Research Feed Daily",
			url: "https://example.com/sample/rss-research-feed-daily",
		},
	],
	example_jobs: [
		{
			job_id: "sample-job-youtube-001",
			platform: "youtube",
			title: "AI Weekly Ops",
			pipeline_final_status: "succeeded",
			digest_excerpt:
				"This sample digest shows how SourceHarbor turns long-form content into a reusable operator summary.",
		},
		{
			job_id: "sample-job-bilibili-001",
			platform: "bilibili",
			title: "Bilibili Agent Notes",
			pipeline_final_status: "degraded",
			digest_excerpt:
				"This sample run highlights how the trace keeps retries and degraded paths visible.",
		},
	],
	example_retrieval_results: [
		{
			query: "agent workflow",
			source: "knowledge_cards",
			snippet:
				"Agent workflow moved from one-shot summaries to repeatable operating loops.",
			job_id: "sample-job-youtube-001",
		},
		{
			query: "retry policy",
			source: "outline",
			snippet:
				"Retry policy tightened around provider instability and operator review checkpoints.",
			job_id: "sample-job-bilibili-001",
		},
	],
	example_watchlists: [
		{
			name: "Retry policy",
			matcher_type: "topic_key",
			matcher_value: "retry-policy",
		},
		{
			name: "Bilibili source watch",
			matcher_type: "platform",
			matcher_value: "bilibili",
		},
	],
	example_trend: {
		watchlist_name: "Retry policy",
		recent_runs: [
			{
				job_id: "sample-job-youtube-001",
				added_topics: ["retry-policy"],
				removed_topics: [],
				added_claim_kinds: ["recommendation"],
				removed_claim_kinds: [],
			},
			{
				job_id: "sample-job-bilibili-001",
				added_topics: ["provider-health"],
				removed_topics: ["retry-policy"],
				added_claim_kinds: ["warning"],
				removed_claim_kinds: ["recommendation"],
			},
		],
	},
	example_bundle: {
		bundle_kind: "sourceharbor_job_evidence_bundle_v1",
		sharing_scope: "internal",
		proof_boundary: "Sample internal bundle for demos only.",
		contains: [
			"digest excerpt",
			"trace summary",
			"knowledge cards excerpt",
			"artifact manifest",
		],
	},
} as const;
