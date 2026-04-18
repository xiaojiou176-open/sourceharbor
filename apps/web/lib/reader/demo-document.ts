import type { ReaderDocument } from "@sourceharbor/sdk";

export const DEMO_READER_DOCUMENT_ID = "demo";

export function buildDemoReaderDocument(): ReaderDocument {
	return {
		id: DEMO_READER_DOCUMENT_ID,
		stable_key: "preview-reader-demo",
		slug: DEMO_READER_DOCUMENT_ID,
		window_id: "preview@SourceHarbor",
		topic_key: "reader-preview",
		topic_label: "Prototype lessons",
		title: "What happens after the first prototype",
		summary:
			"A sample story about the work that begins after a promising first demo, shaped to feel like a real article instead of a product tour.",
		markdown: [
			"Teams rarely stall because the first prototype is bad. They stall because the second move is unclear. A convincing demo creates excitement, but it also exposes every part of the product that still feels like a tool instead of a finished experience.",
			"",
			"Once the first wave of excitement fades, the strongest products usually do three things at the same time: they reduce explanation, make the primary action obvious, and move proof details into the background until the reader actually asks for them.",
			"",
			"## The second move is almost never more explanation",
			"",
			"When a product still feels unfinished, the instinct is often to add more labels, more onboarding text, and more guidance rails. That usually makes the problem worse. Readers do not need more orientation before the first sentence lands; they need one clear place to begin.",
			"",
			"## Why calm surfaces feel more trustworthy",
			"",
			"A calm reading surface does not hide complexity. It simply delays it. Source notes, warnings, and evidence still matter, but they work better as optional layers. The page earns trust by letting the main story carry the first interaction.",
		].join("\n"),
		materialization_mode: "preview_demo",
		version: 1,
		publish_status: "published_with_gap",
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
				canonical_author_name: "SourceHarbor Editorial Desk",
				affiliation_label: "Tracked specimen universe",
				relation_kind: "matched_subscription",
				identity_status: "matched_subscription_identity",
				claim_kinds: ["body-first-reading", "specimen-frontstage"],
				platform: "preview",
				source_origin: "frontstage",
				source_url: "https://example.com/sourceharbor/preview/frontstage",
				raw_stage_contract: {
					analysis_mode: "advanced",
					review_required: true,
					primary_media_input: "video_text",
					review_media_input: "video_text",
					video_contract_satisfied: true,
				},
				digest_preview:
					"The body should answer the primary question before the reader opens supporting provenance lanes.",
			},
			{
				source_item_id: "preview-source-2",
				title: "Yellow warning contract",
				canonical_author_name: "Proof Boundary Desk",
				affiliation_label: "Warning universe",
				relation_kind: "manual_injected",
				identity_status: "derived_identity",
				claim_kinds: ["warning-contract"],
				platform: "preview",
				source_origin: "warning",
				source_url: "https://example.com/sourceharbor/preview/warning",
				raw_stage_contract: {
					analysis_mode: "economy",
					review_required: false,
					primary_media_input: "text",
					video_contract_satisfied: false,
				},
				digest_preview:
					"Yellow warnings preserve readability while making incomplete proof boundaries explicit.",
			},
			{
				source_item_id: "preview-source-3",
				title: "Source notes contract",
				canonical_author_name: "Evidence Desk",
				affiliation_label: "Backstage universe",
				relation_kind: "subscription_tracked",
				identity_status: "matched_subscription_identity",
				claim_kinds: ["evidence-drawer"],
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
				title: "Source notes",
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
