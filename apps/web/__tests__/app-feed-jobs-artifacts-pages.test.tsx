import {
	fireEvent,
	render,
	screen,
	waitFor,
	within,
} from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import FeedPage from "@/app/feed/page";
import IngestRunsPage from "@/app/ingest-runs/page";
import JobsPage from "@/app/jobs/page";
import KnowledgePage from "@/app/knowledge/page";

const mockGetDigestFeed = vi.fn();
const mockGetFeedFeedback = vi.fn();
const mockListSubscriptions = vi.fn();
const mockGetJob = vi.fn();
const mockGetJobCompare = vi.fn();
const mockGetJobKnowledgeCards = vi.fn();
const mockGetArtifactMarkdown = vi.fn();
const mockGetIngestRun = vi.fn();
const mockListIngestRuns = vi.fn();
const mockListKnowledgeCards = vi.fn();

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

vi.mock("@/components/markdown-preview", () => ({
	MarkdownPreview: ({ markdown }: { markdown: string }) => (
		<div data-testid="markdown-preview">{markdown}</div>
	),
}));

vi.mock("@/components/relative-time", () => ({
	RelativeTime: ({ dateTime }: { dateTime: string }) => (
		<time data-testid="relative-time">{dateTime}</time>
	),
}));

vi.mock("@/components/sync-now-button", () => ({
	SyncNowButton: () => <button type="button">Refresh list</button>,
}));

vi.mock("@/lib/api/client", () => ({
	apiClient: {
		getDigestFeed: (...args: unknown[]) => mockGetDigestFeed(...args),
		getFeedFeedback: (...args: unknown[]) => mockGetFeedFeedback(...args),
		listSubscriptions: (...args: unknown[]) => mockListSubscriptions(...args),
		getJob: (...args: unknown[]) => mockGetJob(...args),
		getJobCompare: (...args: unknown[]) => mockGetJobCompare(...args),
		getJobKnowledgeCards: (...args: unknown[]) =>
			mockGetJobKnowledgeCards(...args),
		getIngestRun: (...args: unknown[]) => mockGetIngestRun(...args),
		listKnowledgeCards: (...args: unknown[]) => mockListKnowledgeCards(...args),
		listIngestRuns: (...args: unknown[]) => mockListIngestRuns(...args),
		getArtifactMarkdown: (...args: unknown[]) =>
			mockGetArtifactMarkdown(...args),
	},
}));

describe("feed/jobs/artifacts pages", () => {
	const PAGE_TEST_TIMEOUT_MS = 15000;

	beforeEach(() => {
		vi.clearAllMocks();
		mockListSubscriptions.mockResolvedValue([]);
		mockGetArtifactMarkdown.mockResolvedValue({
			markdown: "# Preview",
			source_title: "Preview",
			source_url: null,
			published_at: null,
		});
	});

	it(
		"renders feed list with filters and next page link",
		async () => {
			mockGetDigestFeed.mockResolvedValue({
				items: [
					{
						feed_id: "feed-1",
						job_id: "job-abcdef123",
						video_url: "https://www.youtube.com/watch?v=abc",
						title: "AI Weekly",
						source: "youtube",
						source_name: "Tech Channel",
						category: "tech",
						published_at: "2026-02-01T00:00:00Z",
						summary_md: "## summary",
						artifact_type: "digest",
						published_document_title: "AI Weekly edition",
						saved: true,
						feedback_label: "useful",
					},
				],
				has_more: true,
				next_cursor: "cursor-2",
			});

			render(
				await FeedPage({
					searchParams: { source: " youtube ", category: "tech", limit: "50" },
				}),
			);

			expect(mockGetDigestFeed).toHaveBeenCalledWith({
				source: "youtube",
				category: "tech",
				limit: 50,
				cursor: undefined,
			});

			expect(
				screen.getAllByRole("heading", { name: "AI Weekly" }).length,
			).toBeGreaterThanOrEqual(1);
			expect(
				screen.getAllByText("YouTube · Tech Channel").length,
			).toBeGreaterThanOrEqual(1);
			expect(
				screen.getAllByText("Reader edition ready · AI Weekly edition").length,
			).toBeGreaterThanOrEqual(1);
			expect(screen.getAllByText("Saved").length).toBeGreaterThan(0);
			expect(screen.getByText("useful")).toBeInTheDocument();
			expect(screen.getAllByText("Tech").length).toBeGreaterThan(0);
			expect(screen.getByRole("link", { name: /AI Weekly/ })).toHaveAttribute(
				"href",
				expect.stringContaining("item=job-abcdef123"),
			);
			expect(screen.getByRole("link", { name: "Next page →" })).toHaveAttribute(
				"href",
				"/feed?source=youtube&category=tech&limit=50&page=2&cursor=cursor-2&item=job-abcdef123",
			);
			expect(screen.getByText("Page 1")).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: "Filter" }),
			).toBeInTheDocument();
			expect(screen.getByRole("button", { name: "Filter" })).toHaveAttribute(
				"data-variant",
				"outline",
			);
			expect(screen.getByRole("link", { name: "Next page →" })).toHaveAttribute(
				"data-variant",
				"surface",
			);
			const sourceSelect = screen.getByRole("combobox", { name: "Source" });
			expect(sourceSelect).toHaveTextContent("YouTube");
			const filterForm = screen
				.getByRole("button", { name: "Filter" })
				.closest("form");
			expect(filterForm).not.toBeNull();
			expect(
				(filterForm as HTMLElement).querySelector(
					'input[type="hidden"][name="source"]',
				),
			).toHaveValue("youtube");
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"passes curated sort to api and preserves it in pagination links",
		async () => {
			mockGetDigestFeed.mockResolvedValue({
				items: [
					{
						feed_id: "feed-curated-1",
						job_id: "job-curated-1",
						video_url: "https://www.youtube.com/watch?v=curated1",
						title: "Curated digest",
						source: "youtube",
						source_name: "Tech Channel",
						category: "tech",
						published_at: "2026-02-04T00:00:00Z",
						summary_md: "## curated summary",
						artifact_type: "digest",
						saved: true,
						feedback_label: "useful",
					},
				],
				has_more: true,
				next_cursor: "4__2026-02-04T00:00:00Z__job-curated-1",
			});

			render(
				await FeedPage({
					searchParams: {
						source: "youtube",
						sort: "curated",
						page: "2",
						cursor: "4__2026-02-03T00:00:00Z__job-curated-0",
					},
				}),
			);

			expect(mockGetDigestFeed).toHaveBeenCalledWith({
				source: "youtube",
				sort: "curated",
				limit: 20,
				cursor: "4__2026-02-03T00:00:00Z__job-curated-0",
			});
			expect(screen.getAllByText("Curated first").length).toBeGreaterThan(0);
			expect(screen.getByRole("link", { name: "Next page →" })).toHaveAttribute(
				"href",
				"/feed?source=youtube&sort=curated&page=3&cursor=4__2026-02-04T00%3A00%3A00Z__job-curated-1&prev_cursor=4__2026-02-03T00%3A00%3A00Z__job-curated-0&item=job-curated-1",
			);
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"defaults the reading preview to the first visible item when no explicit item is selected",
		async () => {
			mockGetDigestFeed.mockResolvedValue({
				items: [
					{
						feed_id: "feed-default-1",
						job_id: "job-default-1",
						video_url: "https://www.youtube.com/watch?v=default1",
						title: "Default preview article",
						source: "youtube",
						source_name: "Tech Channel",
						category: "tech",
						published_at: "2026-02-05T00:00:00Z",
						summary_md: "# default preview",
						artifact_type: "digest",
						published_document_title: "Default preview edition",
					},
				],
				has_more: false,
				next_cursor: null,
			});
			mockGetFeedFeedback.mockResolvedValue({
				job_id: "job-default-1",
				state: null,
				notes: null,
			});

			render(await FeedPage({ searchParams: {} }));

			expect(mockGetFeedFeedback).toHaveBeenCalledWith("job-default-1");
			expect(
				screen.getByRole("heading", {
					name: "Default preview article",
					level: 2,
				}),
			).toBeInTheDocument();
			expect(
				screen.getByRole("link", { name: "Start with this story" }),
			).toHaveAttribute("href", "/feed?item=job-default-1");
			expect(screen.getByText("February 5, 2026")).toBeInTheDocument();
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"passes feedback filter to api and preserves it in pagination links",
		async () => {
			mockGetDigestFeed.mockResolvedValue({
				items: [
					{
						feed_id: "feed-feedback-1",
						job_id: "job-feedback-1",
						video_url: "https://www.youtube.com/watch?v=feedback1",
						title: "Saved digest",
						source: "youtube",
						source_name: "Tech Channel",
						category: "tech",
						published_at: "2026-02-03T00:00:00Z",
						summary_md: "## summary",
						artifact_type: "digest",
						saved: true,
						feedback_label: "useful",
					},
				],
				has_more: true,
				next_cursor: "cursor-feedback-2",
			});

			render(
				await FeedPage({
					searchParams: {
						source: "youtube",
						category: "tech",
						feedback: "useful",
						page: "2",
						cursor: "cursor-feedback-1",
					},
				}),
			);

			expect(mockGetDigestFeed).toHaveBeenCalledWith({
				source: "youtube",
				category: "tech",
				feedback: "useful",
				limit: 20,
				cursor: "cursor-feedback-1",
			});
			expect(screen.getAllByText("Useful").length).toBeGreaterThan(0);
			expect(screen.getByRole("link", { name: "Next page →" })).toHaveAttribute(
				"href",
				"/feed?source=youtube&category=tech&feedback=useful&page=3&cursor=cursor-feedback-2&prev_cursor=cursor-feedback-1&item=job-feedback-1",
			);
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders feed previous page link and explicit page state on non-first page",
		async () => {
			mockGetDigestFeed.mockResolvedValue({
				items: [
					{
						feed_id: "feed-2",
						job_id: "job-zxyw9876",
						video_url: "https://www.youtube.com/watch?v=def",
						title: "AI Deep Dive",
						source: "youtube",
						source_name: "Tech Channel",
						category: "tech",
						published_at: "2026-02-02T00:00:00Z",
						summary_md: "## summary 2",
						artifact_type: "digest",
					},
				],
				has_more: true,
				next_cursor: "cursor-3",
			});

			render(
				await FeedPage({
					searchParams: {
						source: "youtube",
						category: "tech",
						cursor: "cursor-2",
						prev_cursor: "cursor-1",
						page: "3",
					},
				}),
			);

			expect(
				screen.getByRole("link", { name: "← Previous page" }),
			).toHaveAttribute(
				"href",
				"/feed?source=youtube&category=tech&page=2&cursor=cursor-1&item=job-zxyw9876",
			);
			expect(
				screen.getByRole("link", { name: "← Previous page" }),
			).toHaveAttribute("data-variant", "surface");
			expect(screen.getByText("Page 3")).toBeInTheDocument();
			expect(screen.getByRole("link", { name: "Next page →" })).toHaveAttribute(
				"href",
				"/feed?source=youtube&category=tech&page=4&cursor=cursor-3&prev_cursor=cursor-2&item=job-zxyw9876",
			);
			expect(screen.getByRole("link", { name: "Next page →" })).toHaveAttribute(
				"data-variant",
				"surface",
			);
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders main reading flow when feed item is selected",
		async () => {
			mockGetDigestFeed.mockResolvedValue({
				items: [
					{
						feed_id: "feed-reading-1",
						job_id: "job-reading-1",
						video_url: "https://www.youtube.com/watch?v=reading1",
						title: "Digest One",
						source: "youtube",
						source_name: "Creator One",
						subscription_id: "sub-reader-1",
						category: "creator",
						published_at: "2026-02-10T00:00:00Z",
						summary_md: "## summary 1",
						artifact_type: "digest",
						published_document_title: "Reader edition one",
						published_document_publish_status: "published",
						reader_route: "/reader/doc-1",
					},
					{
						feed_id: "feed-reading-2",
						job_id: "job-reading-2",
						video_url: "https://www.youtube.com/watch?v=reading2",
						title: "Digest Two",
						source: "youtube",
						source_name: "Creator Two",
						category: "creator",
						published_at: "2026-02-11T00:00:00Z",
						summary_md: "## summary 2",
						artifact_type: "digest",
					},
				],
				has_more: false,
				next_cursor: null,
			});
			mockGetArtifactMarkdown.mockResolvedValue({
				markdown: "# Digest One\n\nMain reading body",
				meta: { job: { id: "job-reading-1" }, frame_files: [] },
			});
			mockGetFeedFeedback.mockResolvedValue({
				job_id: "job-reading-1",
				saved: true,
				feedback_label: "useful",
				exists: true,
				created_at: "2026-03-29T00:00:00Z",
				updated_at: "2026-03-29T00:00:00Z",
			});

			render(await FeedPage({ searchParams: { item: "job-reading-1" } }));

			expect(
				screen.getByRole("complementary", { name: "Entry list" }),
			).toBeInTheDocument();
			expect(screen.getByRole("link", { name: /Digest One/ })).toHaveAttribute(
				"aria-current",
				"true",
			);
			expect(screen.getByRole("link", { name: /Digest Two/ })).toHaveAttribute(
				"href",
				expect.stringContaining("item=job-reading-2"),
			);

			await waitFor(() => {
				expect(mockGetArtifactMarkdown).toHaveBeenCalledWith({
					job_id: "job-reading-1",
					include_meta: true,
				});
			});

			expect(await screen.findByTestId("markdown-preview")).toHaveTextContent(
				"Main reading body",
			);
			expect(screen.getByText("Feed curation")).toBeInTheDocument();
			expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: "Useful" }),
			).toBeInTheDocument();
			expect(
				screen.getByText("Marked as saved and useful."),
			).toBeInTheDocument();
			const storyNotes = screen.getByText("Story notes");
			fireEvent.click(storyNotes);
			expect(
				screen.getByRole("link", { name: "Inspect job trace" }),
			).toHaveAttribute("href", "/jobs?job_id=job-reading-1");
			expect(
				screen.getByRole("link", { name: /Open original/ }),
			).toHaveAttribute("href", "https://www.youtube.com/watch?v=reading1");
			expect(
				screen.getByRole("link", { name: "Open reader edition" }),
			).toHaveAttribute("href", "/reader/doc-1");
			expect(
				screen.getByRole("link", { name: "Open source desk" }),
			).toHaveAttribute("href", "/feed?sub=sub-reader-1");
			expect(
				screen.getByText(
					"Reader edition ready · Reader edition one · published",
				),
			).toBeInTheDocument();
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"passes subscription filter through feed query and preserves it in pagination urls",
		async () => {
			mockListSubscriptions.mockResolvedValue([
				{
					id: "sub-123",
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
				},
			]);
			mockGetDigestFeed.mockResolvedValue({
				items: [
					{
						feed_id: "feed-sub",
						job_id: "job-sub",
						video_url: "https://example.com/article",
						title: "Article Digest",
						source: "rss",
						source_name: "Macro Blog",
						category: "macro",
						published_at: "2026-02-05T00:00:00Z",
						summary_md: "## article",
						artifact_type: "digest",
						content_type: "article",
					},
				],
				has_more: true,
				next_cursor: "cursor-sub",
			});

			render(
				await FeedPage({
					searchParams: { sub: "sub-123", page: "2", cursor: "cursor-1" },
				}),
			);

			expect(mockGetDigestFeed).toHaveBeenCalledWith({
				source: undefined,
				category: undefined,
				subscription_id: "sub-123",
				limit: 20,
				cursor: "cursor-1",
			});
			expect(mockListSubscriptions).toHaveBeenCalledWith({
				enabled_only: false,
			});
			expect(screen.getByText("Article")).toBeInTheDocument();
			expect(screen.getByText("Pinned source")).toBeInTheDocument();
			expect(screen.getAllByText("Macro Universe").length).toBeGreaterThan(0);
			expect(screen.getByText(/Open one item and read/i)).toBeInTheDocument();
			expect(
				screen.getByRole("link", { name: "← Previous page" }),
			).toHaveAttribute("href", "/feed?sub=sub-123&item=job-sub");
			expect(screen.getByRole("link", { name: "Next page →" })).toHaveAttribute(
				"href",
				"/feed?sub=sub-123&page=3&cursor=cursor-sub&prev_cursor=cursor-1&item=job-sub",
			);
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"keeps legacy source query executable and falls back source selector safely",
		async () => {
			mockGetDigestFeed.mockResolvedValue({
				items: [
					{
						feed_id: "feed-legacy",
						job_id: "job-legacy",
						video_url: "https://example.com/video",
						title: "Legacy Source Digest",
						source: "legacy_platform",
						source_name: "",
						category: "misc",
						published_at: "2026-02-01T00:00:00Z",
						summary_md: "legacy",
						artifact_type: "digest",
					},
				],
				has_more: true,
				next_cursor: "cursor-legacy",
			});

			render(await FeedPage({ searchParams: { source: " legacy_platform " } }));

			expect(mockGetDigestFeed).toHaveBeenCalledWith({
				source: "legacy_platform",
				category: undefined,
				limit: 20,
				cursor: undefined,
			});
			expect(
				screen.getByRole("combobox", { name: "Source" }),
			).toHaveTextContent("All sources");
			expect(screen.getAllByText("legacy_platform").length).toBeGreaterThan(0);
			expect(screen.getByRole("link", { name: "Next page →" })).toHaveAttribute(
				"href",
				"/feed?source=legacy_platform&page=2&cursor=cursor-legacy&item=job-legacy",
			);
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders feed empty state and clear filter entry",
		async () => {
			mockGetDigestFeed.mockResolvedValue({
				items: [],
				has_more: false,
				next_cursor: null,
			});

			render(await FeedPage({ searchParams: { source: "bilibili" } }));

			expect(screen.getByText("No AI digest entries yet")).toBeInTheDocument();
			expect(screen.getByRole("link", { name: "Clear" })).toHaveAttribute(
				"href",
				"/feed",
			);
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders feed empty state subscription management link when no filters are active",
		async () => {
			mockGetDigestFeed.mockResolvedValue({
				items: [],
				has_more: false,
				next_cursor: null,
			});

			render(await FeedPage({ searchParams: {} }));

			expect(
				screen.getByRole("link", { name: "Go to subscriptions" }),
			).toHaveAttribute("href", "/subscriptions");
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders semantic disabled end-page control on last page",
		async () => {
			mockGetDigestFeed.mockResolvedValue({
				items: [
					{
						feed_id: "feed-last",
						job_id: "job-last",
						video_url: "https://www.youtube.com/watch?v=last",
						title: "Last Page Digest",
						source: "youtube",
						source_name: "Channel",
						category: "tech",
						published_at: "2026-02-03T00:00:00Z",
						summary_md: "last",
						artifact_type: "digest",
					},
				],
				has_more: false,
				next_cursor: null,
			});

			render(
				await FeedPage({ searchParams: { page: "2", cursor: "cursor-last" } }),
			);

			const disabledEndControl = screen.queryByRole("button", {
				name: "已到末页",
			});
			expect(disabledEndControl).toBeNull();
			expect(screen.getByText("Page 2")).toBeInTheDocument();
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders feed error message when api fails",
		async () => {
			mockGetDigestFeed.mockRejectedValue(new Error("ERR_INVALID_INPUT:bad"));

			render(await FeedPage({ searchParams: {} }));

			expect(screen.getByRole("alert")).toHaveTextContent(
				"The input is invalid. Review the fields and try again.",
			);
			expect(
				screen.getByRole("link", { name: "Retry current page" }),
			).toHaveAttribute("href", "/feed");
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders jobs page details and artifact links",
		async () => {
			mockGetJob.mockResolvedValue({
				id: "job-1",
				video_id: "video-1",
				kind: "video_digest_v1",
				status: "running",
				idempotency_key: "idem",
				error_message: null,
				artifact_digest_md: null,
				artifact_root: null,
				llm_required: true,
				llm_gate_passed: true,
				hard_fail_reason: null,
				created_at: "2026-02-01T00:00:00Z",
				updated_at: "2026-02-01T00:02:00Z",
				step_summary: [
					{
						name: "fetch_video",
						status: "succeeded",
						attempt: 1,
						started_at: "2026-02-01T00:00:00Z",
						finished_at: "2026-02-01T00:00:10Z",
						error: null,
					},
				],
				steps: [],
				degradations: [
					{
						step: "llm_digest",
						status: "degraded",
						reason: "timeout",
						error: null,
						error_kind: null,
						retry_meta: null,
						cache_meta: null,
					},
				],
				pipeline_final_status: "degraded",
				artifacts_index: { digest: "digest.md" },
				mode: "full",
			});
			mockGetJobCompare.mockResolvedValue({
				job_id: "job-1",
				previous_job_id: "job-0",
				has_previous: true,
				current_digest: "# Current",
				previous_digest: "# Previous",
				diff_markdown: "--- old\n+++ new\n@@\n-- before\n+- after",
				stats: { added_lines: 1, removed_lines: 1, changed: true },
			});
			mockGetJobKnowledgeCards.mockResolvedValue([
				{
					card_type: "takeaway",
					title: "Key takeaway",
					body: "This run produced a reusable takeaway.",
					source_section: "highlights",
					order_index: 1,
				},
			]);

			const { container } = render(
				await JobsPage({ searchParams: { job_id: "job-1" } }),
			);

			expect(mockGetJob).toHaveBeenCalledWith("job-1");
			expect(mockGetJobCompare).toHaveBeenCalledWith("job-1");
			expect(mockGetJobKnowledgeCards).toHaveBeenCalledWith("job-1");
			expect(container.querySelector(".folo-page-shell")).not.toBeNull();
			expect(
				container.querySelectorAll('[data-slot="card"]').length,
			).toBeGreaterThanOrEqual(4);
			expect(
				screen.getByRole("button", { name: "Search" }),
			).toBeInTheDocument();
			const lookupInput = screen.getByRole("textbox", { name: "Job ID *" });
			expect(lookupInput).toHaveValue("job-1");
			expect(lookupInput).toBeRequired();
			const lookupForm = lookupInput.closest("form");
			expect(lookupForm).not.toBeNull();
			expect(lookupForm).toHaveAttribute("data-auto-disable-required", "true");
			expect(
				(lookupForm as HTMLElement).getAttribute("method")?.toLowerCase(),
			).toBe("get");
			expect(
				within(lookupForm as HTMLElement).getByRole("button", {
					name: "Search",
				}),
			).toHaveAttribute("type", "submit");
			expect(screen.getByText("Job overview")).toBeInTheDocument();
			expect(screen.getByText("job-1")).toBeInTheDocument();
			const overviewSection = screen
				.getByText("Job overview")
				.closest('[data-slot="card"]');
			expect(overviewSection).not.toBeNull();
			expect(
				within(overviewSection as HTMLElement).getByText("Job ID"),
			).toBeInTheDocument();
			expect(
				within(overviewSection as HTMLElement).getByText("Video ID"),
			).toBeInTheDocument();
			expect(
				within(overviewSection as HTMLElement).getByText(
					"Final pipeline status",
				),
			).toBeInTheDocument();
			expect(
				within(overviewSection as HTMLElement).getByText("Created at"),
			).toBeInTheDocument();
			expect(
				within(overviewSection as HTMLElement).getByText("Updated at"),
			).toBeInTheDocument();
			expect(
				within(overviewSection as HTMLElement).getByText("Running"),
			).toBeInTheDocument();
			expect(
				within(overviewSection as HTMLElement).getByText("Degraded"),
			).toBeInTheDocument();
			expect(
				screen.getByRole("link", { name: "recent videos on the home page" }),
			).toHaveAttribute("href", "/");
			expect(
				screen.getByRole("link", { name: "the digest feed" }),
			).toHaveAttribute("href", "/feed");
			expect(screen.getByText("Job step summary table")).toBeInTheDocument();
			expect(
				screen.getByText("Job step summary table").closest(".overflow-x-auto"),
			).not.toBeNull();
			expect(screen.getByText("fetch_video")).toBeInTheDocument();
			expect(screen.getByText("llm_digest")).toBeInTheDocument();
			expect(screen.getByText("Succeeded")).toBeInTheDocument();
			expect(screen.getByText("Artifact index")).toBeInTheDocument();
			expect(screen.getByText("Compare to previous run")).toBeInTheDocument();
			expect(screen.getByText("job-0")).toBeInTheDocument();
			expect(
				screen.getByText((_, element) =>
					Boolean(
						element?.tagName === "CODE" &&
							element.textContent?.includes("--- old") &&
							element.textContent?.includes("+++ new"),
					),
				),
			).toBeInTheDocument();
			expect(screen.getByText("Knowledge cards")).toBeInTheDocument();
			expect(screen.getByText("Key takeaway")).toBeInTheDocument();
			expect(
				screen.getByText("This run produced a reusable takeaway."),
			).toBeInTheDocument();
			expect(
				screen.getByText("(opens in a new tab)", { exact: false }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("link", { name: "View in digest feed" }),
			).toHaveAttribute("href", "/feed?item=job-1");
			expect(screen.getByRole("link", { name: /digest\.md/ })).toHaveAttribute(
				"href",
				"http://127.0.0.1:9000/api/v1/artifacts/assets?job_id=job-1&path=digest.md",
			);
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders jobs error when lookup fails",
		async () => {
			mockGetJob.mockRejectedValue(new Error("ERR_REQUEST_FAILED"));
			mockGetJobCompare.mockResolvedValue(null);
			mockGetJobKnowledgeCards.mockResolvedValue([]);

			render(await JobsPage({ searchParams: { job_id: "job-missing" } }));

			expect(screen.getByRole("alert")).toHaveTextContent(
				"The request failed. Please try again later.",
			);
			expect(
				screen.getByRole("link", { name: "Retry current page" }),
			).toHaveAttribute("href", "/jobs?job_id=job-missing");
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"shows compare fallback when no previous job exists",
		async () => {
			mockGetJob.mockResolvedValue({
				id: "job-2",
				video_id: "video-2",
				kind: "video_digest_v1",
				status: "succeeded",
				idempotency_key: "idem-2",
				error_message: null,
				artifact_digest_md: null,
				artifact_root: null,
				llm_required: true,
				llm_gate_passed: true,
				hard_fail_reason: null,
				created_at: "2026-02-01T00:00:00Z",
				updated_at: "2026-02-01T00:02:00Z",
				step_summary: [],
				steps: [],
				degradations: [],
				pipeline_final_status: "succeeded",
				artifacts_index: {},
				mode: "full",
			});
			mockGetJobCompare.mockResolvedValue({
				job_id: "job-2",
				previous_job_id: null,
				has_previous: false,
				current_digest: null,
				previous_digest: null,
				diff_markdown: "",
				stats: { added_lines: 0, removed_lines: 0, changed: false },
			});
			mockGetJobKnowledgeCards.mockResolvedValue([]);

			render(await JobsPage({ searchParams: { job_id: "job-2" } }));

			expect(
				screen.getByText(
					"No previous successful job is available for comparison yet.",
				),
			).toBeInTheDocument();
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders ingest runs page summary table and selected run detail",
		async () => {
			mockListIngestRuns.mockResolvedValue([
				{
					id: "run-1",
					subscription_id: null,
					workflow_id: "wf-1",
					platform: "youtube",
					max_new_videos: 10,
					status: "running",
					jobs_created: 3,
					candidates_count: 4,
					feeds_polled: 1,
					entries_fetched: 4,
					entries_normalized: 4,
					ingest_events_created: 3,
					ingest_event_duplicates: 1,
					job_duplicates: 0,
					error_message: null,
					created_at: "2026-03-29T00:00:00Z",
					updated_at: "2026-03-29T00:01:00Z",
					completed_at: null,
				},
			]);
			mockGetIngestRun.mockResolvedValue({
				id: "run-1",
				subscription_id: null,
				workflow_id: "wf-1",
				platform: "youtube",
				max_new_videos: 10,
				status: "running",
				jobs_created: 3,
				candidates_count: 4,
				feeds_polled: 1,
				entries_fetched: 4,
				entries_normalized: 4,
				ingest_events_created: 3,
				ingest_event_duplicates: 1,
				job_duplicates: 0,
				error_message: null,
				created_at: "2026-03-29T00:00:00Z",
				updated_at: "2026-03-29T00:01:00Z",
				completed_at: null,
				requested_by: "system",
				requested_trace_id: "trace-1",
				filters_json: { platform: "youtube", max_new_videos: 10 },
				items: [
					{
						id: "item-1",
						subscription_id: null,
						video_id: "video-1",
						job_id: "job-1",
						ingest_event_id: "event-1",
						platform: "youtube",
						video_uid: "yt-1",
						source_url: "https://www.youtube.com/watch?v=yt-1",
						title: "Video One",
						published_at: "2026-03-28T23:00:00Z",
						entry_hash: "hash-1",
						pipeline_mode: "full",
						content_type: "video",
						item_status: "queued",
						created_at: "2026-03-29T00:00:00Z",
						updated_at: "2026-03-29T00:01:00Z",
					},
				],
			});

			render(await IngestRunsPage({ searchParams: { run_id: "run-1" } }));

			expect(mockListIngestRuns).toHaveBeenCalledWith({ limit: 10 });
			expect(mockGetIngestRun).toHaveBeenCalledWith("run-1");
			expect(
				screen.getByRole("heading", { name: "Recent ingest runs" }),
			).toBeInTheDocument();
			expect(screen.getByRole("link", { name: "run-1" })).toHaveAttribute(
				"href",
				"/ingest-runs?run_id=run-1",
			);
			expect(screen.getByText("Run detail")).toBeInTheDocument();
			expect(screen.getByText("wf-1")).toBeInTheDocument();
			expect(screen.getByText("Video One")).toBeInTheDocument();
			expect(screen.getByRole("link", { name: "job-1" })).toHaveAttribute(
				"href",
				"/jobs?job_id=job-1",
			);
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders knowledge page filters, summaries, and job trace links",
		async () => {
			mockListKnowledgeCards.mockResolvedValue([
				{
					id: "card-1",
					job_id: "job-1",
					video_id: "video-1",
					card_type: "takeaway",
					title: "Key takeaway",
					body: "A durable knowledge note.",
					source_section: "highlights",
					order_index: 0,
					metadata_json: {
						confidence: "high",
						topic_key: "agent-workflows",
						topic_label: "Agent / Workflows",
						claim_kind: "takeaway",
					},
				},
				{
					id: "card-2",
					job_id: "job-2",
					video_id: "video-2",
					card_type: "risk",
					title: "Watch this",
					body: "A concrete risk reminder.",
					source_section: "risks",
					order_index: 1,
					metadata_json: {
						topic_key: "risk-control",
						topic_label: "Risk / Control",
						claim_kind: "risk",
					},
				},
			]);

			render(
				await KnowledgePage({
					searchParams: {
						job_id: "job-1",
						video_id: "video-1",
						card_type: "takeaway",
						topic_key: "agent-workflows",
						claim_kind: "takeaway",
						limit: "10",
					},
				}),
			);

			expect(mockListKnowledgeCards).toHaveBeenCalledWith({
				job_id: "job-1",
				video_id: "video-1",
				card_type: "takeaway",
				topic_key: "agent-workflows",
				claim_kind: "takeaway",
				limit: 10,
			});
			expect(
				screen.getByRole("heading", { name: "Filter knowledge cards" }),
			).toBeInTheDocument();
			expect(screen.getByLabelText("Job ID")).toHaveValue("job-1");
			expect(screen.getByLabelText("Video ID")).toHaveValue("video-1");
			expect(screen.getByLabelText("Card type")).toHaveTextContent("Takeaway");
			expect(screen.getByLabelText("Topic")).toHaveTextContent(
				"Agent / Workflows",
			);
			expect(screen.getByLabelText("Claim kind")).toHaveTextContent("Takeaway");
			expect(screen.getByLabelText("Limit")).toHaveValue(10);
			expect(screen.getByText("Knowledge cards")).toBeInTheDocument();
			const totalCardsPanel = screen
				.getByText("Total cards")
				.closest('[data-slot="card"]');
			expect(totalCardsPanel).not.toBeNull();
			expect(
				within(totalCardsPanel as HTMLElement).getByText("2"),
			).toBeInTheDocument();
			expect(screen.getByText("Key takeaway")).toBeInTheDocument();
			expect(screen.getByText("A durable knowledge note.")).toBeInTheDocument();
			expect(screen.getByText("Confidence: high")).toBeInTheDocument();
			expect(screen.getAllByText("Agent / Workflows").length).toBeGreaterThan(
				0,
			);
			expect(
				screen.getByRole("link", { name: "Open job trace for job-1" }),
			).toHaveAttribute("href", "/jobs?job_id=job-1");
			expect(
				screen.getByRole("link", { name: /Takeaway \(1\)/ }),
			).toHaveAttribute(
				"href",
				"/knowledge?job_id=job-1&video_id=video-1&card_type=takeaway&topic_key=agent-workflows&claim_kind=takeaway&limit=10",
			);
			expect(
				screen.getAllByRole("link", { name: "Same type" })[0],
			).toHaveAttribute(
				"href",
				"/knowledge?job_id=job-1&video_id=video-1&card_type=takeaway&topic_key=agent-workflows&claim_kind=takeaway&limit=10",
			);
			expect(screen.getByText("Job: job-1")).toBeInTheDocument();
			expect(screen.getByText("Video: video-1")).toBeInTheDocument();
			expect(screen.getByText("Order: 1")).toBeInTheDocument();
			expect(screen.getByText("Topic: Agent / Workflows")).toBeInTheDocument();
			expect(screen.getByRole("link", { name: "Job Trace" })).toHaveAttribute(
				"href",
				"/jobs",
			);
		},
		PAGE_TEST_TIMEOUT_MS,
	);
});
