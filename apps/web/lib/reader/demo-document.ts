import type { ReaderDocument } from "@sourceharbor/sdk";

export const DEMO_READER_DOCUMENT_ID = "demo";

export function buildDemoReaderDocument(): ReaderDocument {
	return {
		id: DEMO_READER_DOCUMENT_ID,
		stable_key: "preview-reader-demo",
		slug: DEMO_READER_DOCUMENT_ID,
		window_id: "preview@SourceHarbor",
		topic_key: "reader-preview",
		topic_label: "Preview detail",
		title: "Reader detail preview",
		summary:
			"Preview how one reading unit keeps the body in front and evidence backstage before your first live document lands.",
		markdown: [
			"# Reader detail preview",
			"",
			"Use this sample like a showroom copy. The body stays primary, while warnings and provenance stay available without taking over the reading flow.",
			"",
			"## What to notice",
			"",
			"- The reader body is the first surface you absorb.",
			"- Yellow warning explains risk without collapsing the page into an error state.",
			"- The evidence drawer behaves like a footnote cabinet, not a permanent dashboard rail.",
			"",
			"## Why a preview exists",
			"",
			"When there are no published reader documents yet, this page still lets you inspect the detail-state information hierarchy before the first batch is materialized.",
		].join("\n"),
		materialization_mode: "preview_demo",
		version: 1,
		published_with_gap: true,
		is_current: true,
		source_item_count: 3,
		consumption_batch_id: null,
		cluster_verdict_manifest_id: null,
		supersedes_document_id: null,
		warning: {
			warning_kind: "preview_demo_warning",
			published_with_gap: true,
			reasons: [
				"Preview sample only. This page demonstrates the reading contract before a live batch is materialized.",
				"Evidence links are illustrative and should not be quoted as a final proof packet.",
			],
			failed_source_count: 0,
			degraded_source_count: 1,
			missing_digest_count: 1,
			generated_at: "2026-04-10T00:00:00Z",
		},
		coverage_ledger: {
			ledger_kind: "sourceharbor_preview_coverage_v1",
			covered_source_count: 2,
			gap_source_count: 1,
			summary:
				"Preview ledger showing the distinction between a readable body and a not-yet-sealed proof packet.",
		},
		traceability_pack: {
			pack_kind: "sourceharbor_reader_preview_traceability_v1",
		},
		source_refs: [
			{
				source_item_id: "preview-source-1",
				title: "Reading desk principle",
				platform: "preview",
				source_origin: "frontstage",
				source_url: "https://example.com/sourceharbor/preview/frontstage",
				digest_preview:
					"The body should answer the primary question before the reader opens supporting provenance lanes.",
			},
			{
				source_item_id: "preview-source-2",
				title: "Yellow warning contract",
				platform: "preview",
				source_origin: "warning",
				source_url: "https://example.com/sourceharbor/preview/warning",
				digest_preview:
					"Yellow warnings preserve readability while making incomplete proof boundaries explicit.",
			},
			{
				source_item_id: "preview-source-3",
				title: "Evidence drawer contract",
				platform: "preview",
				source_origin: "backstage",
				source_url: "https://example.com/sourceharbor/preview/evidence",
				digest_preview:
					"Evidence should feel available on demand, not like a dashboard shouting over the main narrative.",
			},
		],
		sections: [
			{
				section_id: "body-pass",
				title: "Body-first pass",
				markdown:
					"Read the narrative deck as one unit before you inspect provenance.",
				source_item_ids: ["preview-source-1"],
			},
			{
				section_id: "warning-contract",
				title: "Warning contract",
				markdown:
					"The page stays readable while keeping caveats explicit and close to the body.",
				source_item_ids: ["preview-source-2"],
			},
			{
				section_id: "evidence-drawer",
				title: "Evidence drawer",
				markdown:
					"Open backstage evidence only when you need to inspect source lineage or quote safely.",
				source_item_ids: ["preview-source-3"],
			},
		],
		repair_history: [],
		created_at: "2026-04-10T00:00:00Z",
		updated_at: "2026-04-10T00:00:00Z",
	};
}
