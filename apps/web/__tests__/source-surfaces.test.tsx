import {
	fireEvent,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { FeedFeedbackPanel } from "@/components/feed-feedback-panel";
import { ManualSourceIntakePanel } from "@/components/manual-source-intake-panel";
import { SourceContributionDrawer } from "@/components/source-contribution-drawer";
import { SourceIdentityCard } from "@/components/source-identity-card";
import { formatCountPattern, getLocaleMessages } from "@/lib/i18n/messages";
import {
	buildThumbnailUrl,
	resolveFeedIdentity,
	resolveManualIntakeIdentity,
	resolveReaderSourceIdentity,
	resolveSubscriptionIdentity,
} from "@/lib/source-identity";
import {
	decorateAskRoute,
	preferRoute,
	resolveBriefingSelection,
} from "@/lib/story-routes";

const mockSubmitManualSourceIntake = vi.fn();
const mockUpdateFeedFeedback = vi.fn();

vi.mock("next/image", () => ({
	default: ({ alt, src, ...rest }: { alt: string; src: string }) => (
		<span aria-label={alt} data-mock-image={src} role="img" {...rest} />
	),
}));

vi.mock("next/link", () => ({
	default: ({
		href,
		children,
		...rest
	}: {
		href: string;
		children: React.ReactNode;
	}) => (
		<a href={href} {...rest}>
			{children}
		</a>
	),
}));

vi.mock("@/lib/api/client", () => ({
	apiClient: {
		submitManualSourceIntake: (...args: unknown[]) =>
			mockSubmitManualSourceIntake(...args),
		updateFeedFeedback: (...args: unknown[]) => mockUpdateFeedFeedback(...args),
	},
}));

const manualCopy = {
	title: "Manual intake",
	description: "Bring handles, feeds, or direct video links.",
	placeholder: "https://www.youtube.com/watch?v=demo",
	hint: "One line per source.",
	categoryLabel: "Category",
	tagsLabel: "Tags",
	enabledLabel: "Enabled",
	submitButton: "Submit",
	submitPending: "Submitting",
	resultsTitle: "Intake results",
	resultsDescription:
		"The intake summary keeps reader, universe, and job links together.",
	summaryPrefix: "Processed",
	legend: {
		saveSubscription: "Save subscription",
		addToToday: "Add to today",
		unsupported: "Unsupported",
	},
	statusLabels: {
		created: "Created",
		updated: "Updated",
		queued: "Queued",
		reused: "Reused",
		rejected: "Rejected",
	},
	emptyState: "No description yet",
};

describe("source surfaces", () => {
	it("renders manual intake results with reader, universe, and job deep links", async () => {
		mockSubmitManualSourceIntake.mockResolvedValueOnce({
			processed_count: 2,
			created_subscriptions: 1,
			updated_subscriptions: 0,
			queued_manual_items: 1,
			reused_manual_items: 0,
			rejected_count: 1,
			results: [
				{
					line_number: 1,
					raw_input: "https://www.youtube.com/watch?v=demo",
					status: "queued",
					applied_action: "add_to_today",
					recommended_action: "add_to_today",
					platform: "youtube",
					source_type: "url",
					source_value: "https://www.youtube.com/watch?v=demo",
					source_url: "https://www.youtube.com/watch?v=demo",
					rsshub_route: null,
					content_profile: "video",
					support_tier: "strong_supported",
					display_name: "Deep Source",
					relation_kind: "matched_subscription",
					matched_subscription_id: "sub-manual-1",
					matched_subscription_name: "Deep Source Universe",
					matched_by: "source_url",
					match_confidence: "high",
					source_universe_label: "Deep Source Universe",
					creator_display_name: "Deep Source",
					creator_handle: "@deep-source",
					thumbnail_url: null,
					avatar_url: null,
					avatar_label: "DS",
					published_document_title: "Reader edition one",
					published_document_publish_status: "published",
					reader_route: "/reader/doc-1",
					message:
						"Added to today and matched back to an existing tracked universe.",
					subscription_id: "sub-manual-1",
					job_id: "job-manual-1",
				},
				{
					line_number: 2,
					raw_input: "https://example.com/article",
					status: "rejected",
					applied_action: null,
					recommended_action: "unsupported",
					platform: null,
					source_type: null,
					source_value: null,
					source_url: "https://example.com/article",
					rsshub_route: null,
					content_profile: null,
					support_tier: null,
					display_name: null,
					relation_kind: "unmatched_source",
					matched_subscription_id: null,
					matched_subscription_name: null,
					matched_by: null,
					match_confidence: null,
					source_universe_label: null,
					creator_display_name: null,
					creator_handle: null,
					thumbnail_url: null,
					avatar_url: null,
					avatar_label: null,
					published_document_title: null,
					published_document_publish_status: null,
					reader_route: null,
					message: "",
					subscription_id: null,
					job_id: null,
				},
			],
		});

		render(
			<ManualSourceIntakePanel
				copy={manualCopy}
				sessionToken="session-token"
			/>,
		);

		fireEvent.change(screen.getByLabelText("URLs / handles / pages"), {
			target: { value: "https://www.youtube.com/watch?v=demo" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Submit" }));

		await waitFor(() => {
			expect(mockSubmitManualSourceIntake).toHaveBeenCalledTimes(1);
		});

		expect(screen.getByText("Intake results")).toBeInTheDocument();
		expect(
			screen.getByText(
				/Processed 2 · subscriptions \+1\/~0 · today \+1\/=0 · rejected 1/i,
			),
		).toBeInTheDocument();
		expect(
			screen.getByRole("link", { name: "Open reader edition" }),
		).toHaveAttribute("href", "/reader/doc-1");
		expect(
			screen.getByRole("link", { name: "Open tracked universe" }),
		).toHaveAttribute("href", "/feed?sub=sub-manual-1");
		expect(
			screen.getByRole("link", { name: "Open job trace" }),
		).toHaveAttribute("href", "/jobs?job_id=job-manual-1");
		expect(
			screen.getByText(/Published unit · Reader edition one · published/),
		).toBeInTheDocument();
		expect(screen.getByText("No description yet")).toBeInTheDocument();
	});

	it("renders the source contribution drawer with source, job bundle, and universe links", () => {
		render(
			<SourceContributionDrawer
				document={{
					id: "doc-1",
					title: "Reader edition",
					window_id: "window-1",
					version: 1,
					published_with_gap: true,
					source_item_count: 1,
					summary: "Reader summary",
					document_md: "# Reader edition",
					topic_label: "AI",
					published_at: "2026-04-12T00:00:00Z",
					source_refs: [
						{
							source_item_id: "source-1",
							title: "Deep Source",
							platform: "youtube",
							source_origin: "subscription_tracked",
							source_url: "https://www.youtube.com/watch?v=demo",
							job_bundle_route: "/api/v1/jobs/job-1/bundle",
							subscription_id: "sub-doc-1",
							matched_subscription_name: "Deep Source Universe",
							affiliation_label: "Tracked universe",
							digest_preview: "Digest preview",
							raw_stage_contract: {
								analysis_mode: "advanced",
								video_contract_satisfied: true,
							},
							identity_status: "derived_identity",
							claim_kinds: ["summary"],
						},
					],
					sections: [
						{
							section_id: "section-1",
							title: "Section one",
							source_item_ids: ["source-1"],
						},
					],
				}}
			/>,
		);

		expect(screen.getByText("Evidence drawer")).toBeInTheDocument();
		expect(screen.getByText("Warning context available")).toBeInTheDocument();

		fireEvent.click(screen.getByText("Open footnotes by source"));
		expect(screen.getByRole("link", { name: "Open source" })).toHaveAttribute(
			"href",
			"https://www.youtube.com/watch?v=demo",
		);
		expect(
			screen.getByRole("link", { name: "Open job bundle" }),
		).toHaveAttribute("href", "/api/v1/jobs/job-1/bundle");
		expect(
			screen.getByRole("link", { name: "Open tracked universe" }),
		).toHaveAttribute("href", "/feed?sub=sub-doc-1");

		fireEvent.click(screen.getByText("Open section trace map"));
		const sectionCard = screen.getByText("Section one").closest("div");
		expect(sectionCard).not.toBeNull();
		expect(
			within(sectionCard as HTMLElement).getByText(/Section id: section-1/),
		).toBeInTheDocument();
		expect(
			within(sectionCard as HTMLElement).getByText(
				/Linked source items: source-1/,
			),
		).toBeInTheDocument();
	});

	it("covers the source contribution drawer fallback branches when optional links are absent", () => {
		render(
			<SourceContributionDrawer
				document={{
					id: "doc-2",
					title: "Reader edition two",
					window_id: "window-2",
					version: 2,
					published_with_gap: false,
					source_item_count: 1,
					summary: "Reader summary",
					document_md: "# Reader edition two",
					topic_label: null,
					published_at: "2026-04-12T00:00:00Z",
					source_refs: [
						{
							source_item_id: "source-2",
							title: "Fallback Source",
							platform: "generic",
							source_origin: "manual_injected",
							source_url: null,
							job_bundle_route: null,
							subscription_id: "",
							matched_subscription_name: "",
							affiliation_label: "",
							digest_preview: "",
							raw_stage_contract: {
								analysis_mode: "economy",
								video_contract_satisfied: null,
							},
							identity_status: null,
							claim_kinds: [],
							avatar_url: null,
							avatar_label: "FS",
							thumbnail_url: null,
							creator_display_name: "",
							canonical_author_name: "",
						},
					],
					sections: [
						{
							section_id: "section-2",
							title: "Section two",
							source_item_ids: [],
						},
					],
				}}
			/>,
		);

		expect(screen.getByText("Clear provenance map")).toBeInTheDocument();
		fireEvent.click(screen.getByText("Open footnotes by source"));
		expect(
			screen.queryByRole("link", { name: "Open source" }),
		).not.toBeInTheDocument();
		expect(
			screen.queryByRole("link", { name: "Open job bundle" }),
		).not.toBeInTheDocument();
		expect(
			screen.queryByRole("link", { name: "Open tracked universe" }),
		).not.toBeInTheDocument();

		fireEvent.click(screen.getByText("Open section trace map"));
		expect(screen.getByText(/Linked source items: none/)).toBeInTheDocument();
	});

	it("covers source identity helpers and story routes across edge branches", () => {
		expect(
			buildThumbnailUrl({
				platform: "youtube",
				url: "https://youtu.be/demo",
				title: "Demo",
			}),
		).toContain("i.ytimg.com");
		expect(
			buildThumbnailUrl({
				platform: "generic",
				url: "not-a-url",
				title: "Fallback",
			}),
		).toContain("data:image/svg+xml");

		const subscriptionIdentity = resolveSubscriptionIdentity({
			id: "sub-1",
			platform: "rss_generic",
			source_type: "url",
			source_value: "https://example.com/feed.xml",
			source_url: "https://example.com/feed.xml",
			rsshub_route: null,
			source_name: "Macro Universe",
			source_universe_label: "Macro Universe",
			creator_display_name: "Macro Universe",
			content_profile: "article",
			category: "macro",
			priority: 50,
			support_tier: "general_supported",
			identity_status: "derived_identity",
			thumbnail_url: null,
			avatar_url: null,
			avatar_label: "MU",
			source_homepage_url: "https://example.com",
		});
		expect(subscriptionIdentity.relationLabel).toBe("Tracked universe");
		expect(subscriptionIdentity.meta).toContain("RSS");

		const manualIdentity = resolveManualIntakeIdentity({
			line_number: 1,
			raw_input: "https://example.com/feed.xml",
			status: "created",
			applied_action: "save_subscription",
			recommended_action: "save_subscription",
			platform: "youtube",
			source_type: "youtube_user",
			source_value: "@deep-source",
			source_url: "https://www.youtube.com/@deep-source",
			rsshub_route: "/youtube/user/@deep-source",
			content_profile: "video",
			support_tier: "strong_supported",
			display_name: "Deep Source",
			relation_kind: "subscription_candidate",
			matched_subscription_id: null,
			matched_subscription_name: null,
			matched_by: "rsshub_route",
			match_confidence: "high",
			source_universe_label: "Deep Source Universe",
			creator_display_name: "Deep Source",
			creator_handle: "@deep-source",
			thumbnail_url: null,
			avatar_url: null,
			avatar_label: "DS",
			published_document_title: null,
			published_document_publish_status: null,
			reader_route: null,
			message: "saved",
			subscription_id: null,
			job_id: null,
		});
		expect(manualIdentity.eyebrow).toBe("Universe intake");
		expect(manualIdentity.relationLabel).toBe("Deep Source Universe");

		const feedIdentity = resolveFeedIdentity({
			feed_id: "feed-1",
			job_id: "job-1",
			video_url: "https://www.youtube.com/watch?v=demo",
			title: "Digest Title",
			source: "youtube",
			source_name: "Source Name",
			canonical_source_name: "Canonical Name",
			canonical_author_name: "",
			category: "creator",
			published_at: "2026-04-12T00:00:00Z",
			summary_md: "Summary",
			artifact_type: "digest",
			subscription_id: "sub-1",
			affiliation_label: "",
			relation_kind: "manual_one_off",
			thumbnail_url: null,
			avatar_url: null,
			avatar_label: "",
			published_document_title: null,
			published_document_publish_status: null,
			published_with_gap: false,
			reader_route: null,
			content_type: "article",
			saved: true,
			feedback_label: "useful",
			identity_status: "derived_identity",
		});
		expect(feedIdentity.eyebrow).toBe("Article lane");
		expect(feedIdentity.meta).toEqual(
			expect.arrayContaining(["Derived identity", "Saved", "useful"]),
		);

		const readerIdentity = resolveReaderSourceIdentity({
			source_item_id: "source-1",
			title: "Reader Source",
			platform: "youtube",
			source_origin: "manual_injected",
			source_url: "https://www.youtube.com/watch?v=demo",
			digest_preview: "Preview",
			relation_kind: "manual_injected",
			affiliation_label: "",
			matched_subscription_name: "",
			canonical_author_name: "",
			creator_display_name: "Reader Source",
			thumbnail_url: null,
			avatar_url: null,
			avatar_label: "",
			raw_stage_contract: {
				analysis_mode: "advanced",
				video_contract_satisfied: false,
			},
			identity_status: "derived_identity",
			claim_kinds: ["summary", "quote"],
		});
		expect(readerIdentity.eyebrow).toBe("Manual evidence");
		expect(readerIdentity.meta).toEqual(
			expect.arrayContaining(["Video contract gap", "2 claim kinds"]),
		);

		expect(
			decorateAskRoute("/ask#evidence", {
				question: "What changed?",
				top_k: 5,
			}),
		).toBe("/ask?question=What+changed%3F&top_k=5#evidence");
		expect(preferRoute("  ", "/fallback")).toBe("/fallback");
		expect(
			resolveBriefingSelection(
				{
					evidence: {
						stories: [
							{ story_id: "story-1", title: "Story 1" },
							{ story_id: "story-2", title: "Story 2" },
						],
						suggested_story_id: "story-2",
					},
					selection: null,
				} as never,
				"story-1",
			),
		).toMatchObject({
			selectedStoryId: "story-1",
			selectionBasis: "requested_story_id",
		});
		expect(
			resolveBriefingSelection(
				{
					evidence: {
						stories: [{ story_id: "story-3", title: "Story 3" }],
						suggested_story_id: "story-3",
					},
					selection: {
						story: { story_id: "story-server", title: "Server story" },
						selected_story_id: "story-server",
						selection_basis: "server_selection",
					},
				} as never,
				"story-3",
			),
		).toMatchObject({
			selectedStoryId: "story-server",
			selectionBasis: "server_selection",
		});
		expect(
			resolveBriefingSelection(
				{
					evidence: {
						stories: [
							{ story_id: "story-2", title: "Story 2" },
							{ story_id: "story-4", title: "Story 4" },
						],
						suggested_story_id: "story-4",
					},
					selection: null,
				} as never,
				"",
			),
		).toMatchObject({
			selectedStoryId: "story-4",
			selectionBasis: "suggested_story_id",
		});
		expect(
			resolveBriefingSelection(
				{
					evidence: { stories: [{ story_id: "story-5", title: "Story 5" }] },
					selection: null,
				} as never,
				"",
			),
		).toMatchObject({
			selectedStoryId: "story-5",
			selectionBasis: "first_story",
		});
		expect(resolveBriefingSelection(undefined, null)).toMatchObject({
			selectedStoryId: null,
			selectionBasis: "none",
		});
		expect(decorateAskRoute("   ", { question: "ignored" })).toBeNull();
		expect(getLocaleMessages("en").feedPage.subscriptionFilterLabel).toBe(
			"Tracked universe",
		);
		expect(
			getLocaleMessages("zh-CN").feedPage.activeTrackedUniverseTitle,
		).toContain("tracked universe");
		expect(formatCountPattern("{count} item|{count} items", 1)).toBe("1 item");
		expect(formatCountPattern("{count} item|{count} items", 2)).toBe("2 items");
	});

	it("renders source identity card fallbacks and feedback panel success and error states", async () => {
		mockUpdateFeedFeedback
			.mockResolvedValueOnce({
				job_id: "job-1",
				saved: true,
				feedback_label: "useful",
				exists: true,
			})
			.mockRejectedValueOnce(new Error("failed"));

		const { rerender } = render(
			<div>
				<SourceIdentityCard
					identity={{
						title: "Fallback Source",
						subtitle: "Fallback subtitle",
						description: "Fallback description",
						eyebrow: "Fallback eyebrow",
						thumbnailUrl: null,
						avatarUrl: null,
						avatarLabel: "FS",
						relationKind: "manual_injected",
						relationLabel: "Manual injected",
						meta: ["Generic"],
					}}
				/>
				<FeedFeedbackPanel
					initialFeedback={null}
					jobId="job-1"
					sessionToken="token"
				/>
			</div>,
		);

		expect(screen.getByText("Fallback Source")).toBeInTheDocument();
		expect(screen.getAllByText("FS").length).toBeGreaterThan(0);
		expect(
			screen.getByText("No curation signal recorded yet."),
		).toBeInTheDocument();

		fireEvent.click(screen.getByRole("button", { name: "Useful" }));
		await waitFor(() => {
			expect(mockUpdateFeedFeedback).toHaveBeenCalledWith(
				{ job_id: "job-1", saved: true, feedback_label: "useful" },
				{ webSessionToken: "token" },
			);
		});
		await waitFor(() => {
			expect(
				screen.getByText("Marked as saved and useful."),
			).toBeInTheDocument();
		});

		rerender(
			<FeedFeedbackPanel
				initialFeedback={{
					job_id: "job-1",
					saved: true,
					feedback_label: "useful",
					exists: true,
				}}
				jobId="job-1"
				sessionToken="token"
			/>,
		);
		fireEvent.click(screen.getByRole("button", { name: "Noisy" }));
		await waitFor(() => {
			expect(
				screen.getByText("Feedback update failed. Please retry."),
			).toBeInTheDocument();
		});

		rerender(
			<FeedFeedbackPanel
				key="dismissed"
				initialFeedback={{
					job_id: "job-1",
					saved: false,
					feedback_label: "dismissed",
					exists: true,
				}}
				jobId="job-1"
			/>,
		);
		expect(screen.getByText("Marked as dismissed.")).toBeInTheDocument();

		rerender(
			<FeedFeedbackPanel
				key="archived"
				initialFeedback={{
					job_id: "job-1",
					saved: false,
					feedback_label: "archived",
					exists: true,
				}}
				jobId="job-1"
			/>,
		);
		expect(screen.getByText("Marked as archived.")).toBeInTheDocument();
	});

	it("surfaces manual intake submission failures without leaving stale results behind", async () => {
		mockSubmitManualSourceIntake.mockRejectedValueOnce(
			new Error("submission failed"),
		);

		render(<ManualSourceIntakePanel copy={manualCopy} />);

		fireEvent.change(screen.getByLabelText("URLs / handles / pages"), {
			target: { value: "https://www.youtube.com/watch?v=demo" },
		});
		fireEvent.click(screen.getByRole("button", { name: "Submit" }));

		await waitFor(() => {
			expect(screen.getByRole("alert")).toHaveTextContent(
				"The request failed. Please try again later.",
			);
		});
		expect(screen.queryByText("Intake results")).not.toBeInTheDocument();
	});
});
