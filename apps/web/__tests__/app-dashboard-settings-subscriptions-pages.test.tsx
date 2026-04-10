import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import IngestRunsPage from "@/app/ingest-runs/page";
import DashboardPage from "@/app/page";
import SettingsPage from "@/app/settings/page";
import SubscriptionsPage from "@/app/subscriptions/page";

const mockListSubscriptions = vi.fn();
const mockListSubscriptionTemplates = vi.fn();
const mockListVideos = vi.fn();
const mockListIngestRuns = vi.fn();
const mockGetIngestRun = vi.fn();
const mockGetNotificationConfig = vi.fn();

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

vi.mock("@/app/action-security", () => ({
	getActionSessionTokenForForm: () => "test-session-token",
}));

vi.mock("@/components/subscription-batch-panel", () => ({
	SubscriptionBatchPanel: ({
		subscriptions,
	}: {
		subscriptions: Array<{ id: string }>;
	}) => (
		<div data-testid="subscription-batch-panel">
			count:{subscriptions.length}
		</div>
	),
}));

vi.mock("@/lib/api/client", () => ({
	apiClient: {
		listSubscriptions: (...args: unknown[]) => mockListSubscriptions(...args),
		listSubscriptionTemplates: (...args: unknown[]) =>
			mockListSubscriptionTemplates(...args),
		listVideos: (...args: unknown[]) => mockListVideos(...args),
		listIngestRuns: (...args: unknown[]) => mockListIngestRuns(...args),
		getIngestRun: (...args: unknown[]) => mockGetIngestRun(...args),
		getNotificationConfig: (...args: unknown[]) =>
			mockGetNotificationConfig(...args),
	},
}));

class ResizeObserverMock {
	observe() {}
	unobserve() {}
	disconnect() {}
}

vi.stubGlobal("ResizeObserver", ResizeObserverMock);

describe("dashboard/settings/subscriptions pages", () => {
	const PAGE_TEST_TIMEOUT_MS = 15000;

	beforeEach(() => {
		vi.clearAllMocks();
		mockListSubscriptionTemplates.mockResolvedValue({
			support_tiers: [
				{
					id: "strong_supported",
					label: "Strong support",
					description:
						"Purpose-built video subscriptions with first-class routing and durable identifiers.",
					content_profile: "video",
					supports_video_pipeline: true,
					verification_status: "verified_for_youtube_bilibili_only",
				},
				{
					id: "generic_supported",
					label: "Generic support",
					description:
						"Generic RSSHub or RSS intake substrate for broad article-style coverage without overclaiming route-by-route verification.",
					content_profile: "article",
					supports_video_pipeline: false,
					verification_status: "substrate_ready_not_route_by_route_verified",
				},
			],
			templates: [
				{
					id: "youtube_channel",
					label: "YouTube channel",
					description:
						"Strong preset for recurring YouTube intake when you already know the channel ID, handle, or landing URL.",
					support_tier: "strong_supported",
					platform: "youtube",
					source_type: "youtube_channel_id",
					adapter_type: "rsshub_route",
					content_profile: "video",
					category: "creator",
					source_value_placeholder: "UCxxxx",
					source_url_placeholder: "https://www.youtube.com/@channel",
					rsshub_route_hint: "/youtube/channel/UCxxxx",
					source_url_required: false,
					supports_video_pipeline: true,
					fill_now:
						"Start with the channel ID or a stable channel URL, then keep the RSSHub route aligned.",
					proof_boundary:
						"YouTube is a strong path today, but route health still matters if you depend on RSSHub for intake.",
					evidence_note: "Strongly supported video lane.",
				},
				{
					id: "generic_rsshub_route",
					label: "Generic RSSHub route",
					description:
						"General preset for wider source coverage when RSSHub can normalize a route into a usable feed.",
					support_tier: "generic_supported",
					platform: "rsshub",
					source_type: "rsshub_route",
					adapter_type: "rsshub_route",
					content_profile: "article",
					category: "misc",
					source_value_placeholder: "/namespace/path",
					source_url_placeholder: "https://example.com/source",
					rsshub_route_hint: "/namespace/path",
					source_url_required: false,
					supports_video_pipeline: false,
					fill_now:
						"Bring the exact RSSHub route you want SourceHarbor to poll, then add a canonical source URL only if it helps operators recognize the feed.",
					proof_boundary:
						"Do not assume every RSSHub route is equally solid. Treat each route as proven only after it survives real runs.",
					evidence_note:
						"Substrate does not block RSSHub universe, but routes are not claimed as individually verified.",
				},
				{
					id: "generic_rss_feed",
					label: "Generic RSS or Atom feed",
					description:
						"General preset for any source that already exposes a clean RSS or Atom feed without a platform-specific shortcut.",
					support_tier: "generic_supported",
					platform: "generic",
					source_type: "url",
					adapter_type: "rss_generic",
					content_profile: "article",
					category: "misc",
					source_value_placeholder: "https://example.com/feed.xml",
					source_url_placeholder: "",
					rsshub_route_hint: "https://example.com/feed.xml",
					source_url_required: false,
					supports_video_pipeline: false,
					fill_now:
						"Paste the exact RSS or Atom feed URL into Source value. Leave Source URL empty unless you want to store the same feed URL explicitly.",
					proof_boundary:
						"Feed quality varies a lot. If the feed is noisy or incomplete, the intake surface should stay honest about that.",
					evidence_note:
						"Use Source value for the exact feed URL; Source URL stays optional unless you want to store the same feed URL explicitly.",
				},
			],
		});
	});

	it(
		"renders dashboard metrics, table rows and failure CTA",
		async () => {
			mockListSubscriptions.mockResolvedValue([
				{ id: "sub-1" },
				{ id: "sub-2" },
			]);
			mockListVideos.mockResolvedValue([
				{
					id: "v1",
					platform: "youtube",
					video_uid: "yt-1",
					source_url: "https://example.com/1",
					title: "Video One",
					published_at: null,
					first_seen_at: "2026-02-01T00:00:00Z",
					last_seen_at: "2026-02-01T00:00:00Z",
					status: "running",
					last_job_id: "job-111",
				},
				{
					id: "v2",
					platform: "bilibili",
					video_uid: "bb-2",
					source_url: "https://example.com/2",
					title: null,
					published_at: null,
					first_seen_at: "2026-02-01T00:00:00Z",
					last_seen_at: "2026-02-01T00:00:00Z",
					status: "failed",
					last_job_id: null,
				},
				{
					id: "v3",
					platform: "rss_generic",
					video_uid: "rss-3",
					source_url: "https://example.com/3",
					title: "Video Three",
					published_at: null,
					first_seen_at: "2026-02-01T00:00:00Z",
					last_seen_at: "2026-02-01T00:00:00Z",
					status: "queued",
					last_job_id: "job-333",
				},
			]);
			mockListIngestRuns.mockResolvedValue([
				{
					id: "run-1",
					subscription_id: null,
					workflow_id: "wf-1",
					platform: "youtube",
					max_new_videos: 5,
					status: "queued",
					jobs_created: 2,
					candidates_count: 2,
					feeds_polled: 1,
					entries_fetched: 3,
					entries_normalized: 3,
					ingest_events_created: 2,
					ingest_event_duplicates: 1,
					job_duplicates: 0,
					error_message: null,
					created_at: "2026-02-01T00:00:00Z",
					updated_at: "2026-02-01T00:00:00Z",
					completed_at: null,
				},
			]);

			render(await DashboardPage({ searchParams: {} }));
			expect(document.querySelector(".folo-page-shell")).not.toBeNull();
			expect(
				document.querySelectorAll('[data-slot="card"]').length,
			).toBeGreaterThanOrEqual(7);
			expect(
				screen.getByText("Build with Codex, Claude Code, and MCP clients"),
			).toBeInTheDocument();
			expect(
				screen.getByRole("heading", {
					name: "Why builders keep reading",
				}),
			).toBeInTheDocument();
			expect(
				screen.getByRole("heading", {
					name: "One truth across Web, API, and MCP",
				}),
			).toBeInTheDocument();
			expect(
				screen.getByRole("heading", {
					name: "Proof sits next to the product story",
				}),
			).toBeInTheDocument();
			expect(
				screen.getByRole("heading", {
					name: "Worth returning to after the first run",
				}),
			).toBeInTheDocument();
			expect(
				screen.getByRole("heading", { name: "Source-universe intake" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("heading", {
					name: "Watchlists are tracking objects",
				}),
			).toBeInTheDocument();
			expect(
				screen.getByRole("heading", {
					name: "Trends are the compounder front door",
				}),
			).toBeInTheDocument();
			expect(
				screen.getByRole("heading", {
					name: "Briefings are the shared story surface",
				}),
			).toBeInTheDocument();
			expect(
				screen.getByRole("heading", { name: "Playground stays sample-proof" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("link", { name: "Open Subscriptions" }),
			).toHaveAttribute("href", "/subscriptions");
			expect(
				screen.getAllByRole("link", { name: "Open Briefings" }).length,
			).toBeGreaterThanOrEqual(2);
			for (const link of screen.getAllByRole("link", {
				name: "Open Briefings",
			})) {
				expect(link).toHaveAttribute("href", "/briefings");
			}
			expect(screen.getByRole("link", { name: "Open Proof" })).toHaveAttribute(
				"href",
				"/proof",
			);
			expect(
				screen.getByRole("link", { name: "Inspect proof ladder" }),
			).toHaveAttribute("href", "/proof");
			expect(
				screen.getByRole("link", { name: "Open research pipeline" }),
			).toHaveAttribute("href", "/use-cases/research-pipeline");
			const buildersGuideLinks = screen.getAllByRole("link", {
				name: "Open builders guide",
			});
			expect(buildersGuideLinks.length).toBeGreaterThanOrEqual(1);
			for (const link of buildersGuideLinks) {
				expect(link).toHaveAttribute("href", "/builders");
			}
			expect(
				screen.getByRole("link", { name: "Open starter packs" }),
			).toHaveAttribute(
				"href",
				"https://github.com/xiaojiou176-open/sourceharbor/blob/main/starter-packs/README.md",
			);
			expect(
				screen.getByRole("link", { name: "Inspect CLI package" }),
			).toHaveAttribute(
				"href",
				"https://github.com/xiaojiou176-open/sourceharbor/blob/main/packages/sourceharbor-cli/README.md",
			);
			expect(
				screen.getByRole("link", { name: "Inspect TypeScript SDK" }),
			).toHaveAttribute(
				"href",
				"https://github.com/xiaojiou176-open/sourceharbor/blob/main/packages/sourceharbor-sdk/README.md",
			);
			expect(
				screen.getByText("One control plane, four real doors"),
			).toBeInTheDocument();
			expect(screen.getByText("Receipts before vibes")).toBeInTheDocument();
			expect(screen.getByText("Worth coming back to")).toBeInTheDocument();
			expect(screen.getByText("Official-surface status")).toBeInTheDocument();
			expect(screen.getByText("Claude Code")).toBeInTheDocument();
			const distributionLedgerLinks = screen.getAllByRole("link", {
				name: "Open distribution ledger",
			});
			expect(distributionLedgerLinks.length).toBeGreaterThanOrEqual(1);
			for (const link of distributionLedgerLinks) {
				expect(link).toHaveAttribute(
					"href",
					"https://github.com/xiaojiou176-open/sourceharbor/blob/main/docs/public-distribution.md",
				);
			}

			const metricRegion = screen.getByRole("region", { name: "Key metrics" });
			const metrics = Array.from(
				metricRegion.querySelectorAll('[data-slot="card"]'),
			);
			expect(metrics).toHaveLength(4);
			expect(
				within(metrics[0] as HTMLElement).getByText("2"),
			).toBeInTheDocument();
			expect(
				within(metrics[1] as HTMLElement).getByText("3"),
			).toBeInTheDocument();
			expect(
				within(metrics[2] as HTMLElement).getByText("2"),
			).toBeInTheDocument();
			expect(
				within(metrics[3] as HTMLElement).getByText("1"),
			).toBeInTheDocument();
			expect(
				screen.getByRole("link", { name: "Open failed jobs →" }),
			).toHaveAttribute("href", "/jobs");

			const recentIngestTable = screen
				.getByText("Recent ingest runs")
				.closest('[data-slot="card"]');
			expect(recentIngestTable).not.toBeNull();
			expect(screen.getByText("run-1")).toBeInTheDocument();
			expect(
				screen.getByRole("link", { name: "Open all ingest runs →" }),
			).toHaveAttribute("href", "/ingest-runs");
			expect(screen.getByText("New jobs").tagName).toBe("TH");
			expect(screen.getByText("Candidates").tagName).toBe("TH");
			expect(screen.getAllByText("Queued").length).toBeGreaterThanOrEqual(1);

			const tables = screen.getAllByRole("table");
			expect(tables).toHaveLength(2);
			const recentVideoTable = tables[1] as HTMLElement;
			expect(
				within(recentVideoTable).getByText("Recent video list"),
			).toBeInTheDocument();
			expect(within(recentVideoTable).getByText("Title").tagName).toBe("TH");
			expect(within(recentVideoTable).getByText("Title")).toHaveAttribute(
				"scope",
				"col",
			);
			expect(within(recentVideoTable).getByText("YouTube")).toBeInTheDocument();
			expect(
				within(recentVideoTable).getByText("Bilibili"),
			).toBeInTheDocument();
			expect(
				within(recentVideoTable).getByText("rss_generic"),
			).toBeInTheDocument();
			expect(within(recentVideoTable).getByText("Running")).toBeInTheDocument();
			expect(within(recentVideoTable).getByText("Queued")).toBeInTheDocument();
			expect(within(recentVideoTable).getByText("Failed")).toBeInTheDocument();

			expect(screen.getByRole("link", { name: "job-111" })).toHaveAttribute(
				"href",
				"/jobs?job_id=job-111",
			);
			expect(screen.getByRole("link", { name: "job-333" })).toHaveAttribute(
				"href",
				"/jobs?job_id=job-333",
			);

			const pollForm = screen
				.getByRole("button", { name: "Run ingest poll" })
				.closest("form");
			expect(pollForm).not.toBeNull();
			expect(pollForm).not.toHaveAttribute("method");
			expect(
				(pollForm as HTMLElement).querySelector(
					'input[type="hidden"][name="platform"]',
				),
			).toHaveValue("");
			expect(
				within(pollForm as HTMLElement).getByRole("spinbutton", {
					name: "Maximum new videos",
				}),
			).toHaveValue(50);
			expect(
				(pollForm as HTMLElement).querySelector(
					'input[type="hidden"][name="session_token"]',
				),
			).toHaveValue("test-session-token");
			expect(
				within(pollForm as HTMLElement).getByRole("button", {
					name: "Run ingest poll",
				}),
			).toHaveAttribute("type", "submit");
			expect(
				screen.getByRole("link", { name: "Open job queue →" }),
			).toHaveAttribute("href", "/jobs");

			const processForm = screen
				.getByRole("button", { name: "Start processing" })
				.closest("form");
			expect(processForm).not.toBeNull();
			expect(processForm).toHaveAttribute("data-auto-disable-required", "true");
			expect(processForm).not.toHaveAttribute("method");
			expect(
				(processForm as HTMLElement).querySelector(
					'input[type="hidden"][name="platform"]',
				),
			).toHaveValue("youtube");
			expect(
				within(processForm as HTMLElement).getByRole("textbox", {
					name: "Source URL *",
				}),
			).toBeRequired();
			expect(
				(processForm as HTMLElement).querySelector(
					'input[type="hidden"][name="mode"]',
				),
			).toHaveValue("full");
			expect(
				within(processForm as HTMLElement).getByRole("checkbox", {
					name: "Force rerun",
				}),
			).not.toBeChecked();
			expect(
				(processForm as HTMLElement).querySelector(
					'input[type="hidden"][name="session_token"]',
				),
			).toHaveValue("test-session-token");
			expect(
				within(processForm as HTMLElement).getByRole("button", {
					name: "Start processing",
				}),
			).toHaveAttribute("type", "submit");
			expect(
				screen.getByRole("link", { name: "Open job detail →" }),
			).toHaveAttribute("href", "/jobs");
			expect(
				screen.getByRole("link", { name: "Open all jobs →" }),
			).toHaveAttribute("href", "/jobs");
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders dashboard load error and empty fallback copy",
		async () => {
			mockListSubscriptions.mockRejectedValue(new Error("network failed"));
			mockListVideos.mockRejectedValue(new Error("network failed"));
			mockListIngestRuns.mockRejectedValue(new Error("network failed"));

			render(await DashboardPage({ searchParams: {} }));

			expect(screen.getByRole("alert")).toHaveTextContent(
				"The request failed. Please try again later.",
			);
			expect(
				screen.getByRole("link", { name: "Retry this page" }),
			).toHaveAttribute("href", "/");
			expect(
				screen.getByText("Unable to load the video list right now."),
			).toBeInTheDocument();
			expect(screen.getAllByText("Data unavailable")).toHaveLength(4);
			expect(
				screen.getByText("Ingest run data is temporarily unavailable."),
			).toBeInTheDocument();

			const metricRegion = screen.getByRole("region", { name: "Key metrics" });
			const metrics = Array.from(
				metricRegion.querySelectorAll('[data-slot="card"]'),
			);
			expect(metrics).toHaveLength(4);
			for (const metric of metrics) {
				expect(
					within(metric as HTMLElement).getByText(/--/),
				).toBeInTheDocument();
				expect(
					within(metric as HTMLElement).queryByText("0"),
				).not.toBeInTheDocument();
			}
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders dashboard flash success from search params",
		async () => {
			mockListSubscriptions.mockResolvedValue([]);
			mockListVideos.mockResolvedValue([]);
			mockListIngestRuns.mockResolvedValue([]);

			render(
				await DashboardPage({
					searchParams: { status: "success", code: "POLL_INGEST_OK" },
				}),
			);

			const successFlash = screen
				.getByText("Ingestion job queued.")
				.closest("output");
			expect(successFlash).not.toBeNull();
			expect(successFlash).toHaveAttribute("aria-live", "polite");
			expect(successFlash).toHaveAttribute("aria-atomic", "true");
			expect(
				screen.getByRole("link", { name: "Add your first subscription →" }),
			).toHaveAttribute("href", "/subscriptions");
			expect(screen.getByText("No videos yet.")).toBeInTheDocument();
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders subscriptions page as a template-driven source intake front door",
		async () => {
			mockListSubscriptions.mockResolvedValue([
				{
					id: "sub-1",
					source_name: "channel-1",
					source_value: "value",
					rsshub_route: "",
					platform: "youtube",
					source_type: "url",
					adapter_type: "rsshub_route",
					source_url: null,
					category: "tech",
					tags: [],
					priority: 50,
					enabled: true,
					created_at: "2026-02-01T00:00:00Z",
					updated_at: "2026-02-01T00:00:00Z",
				},
			]);

			render(
				await SubscriptionsPage({
					searchParams: {
						status: "error",
						code: "ERR_INVALID_INPUT",
						template: "generic_rsshub_route",
					},
				}),
			);

			expect(screen.getByRole("alert")).toHaveTextContent(
				"The input is invalid. Review the fields and try again.",
			);
			expect(screen.getByTestId("subscription-batch-panel")).toHaveTextContent(
				"count:1",
			);
			expect(
				screen.getByText("Support levels at a glance"),
			).toBeInTheDocument();
			expect(screen.getAllByText("Strong support").length).toBeGreaterThan(0);
			expect(screen.getAllByText("Generic support").length).toBeGreaterThan(0);
			expect(
				screen.getAllByText("Generic RSS or Atom feed").length,
			).toBeGreaterThan(0);
			expect(
				screen.getByRole("link", { name: "Open merged stories" }),
			).toHaveAttribute("href", "/trends");
			expect(
				screen.getByRole("button", { name: "Save subscription" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("heading", { name: "Manual source intake" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: "Run manual intake" }),
			).toBeInTheDocument();
			expect(
				screen.getByLabelText("URLs / handles / pages"),
			).toBeInTheDocument();
			expect(
				screen.getByRole("combobox", { name: "Platform" }),
			).toHaveTextContent("RSSHub");
			expect(
				screen.getByRole("combobox", { name: "Source type" }),
			).toHaveTextContent("RSSHub route");
			expect(screen.getByLabelText("Source value")).toBeRequired();
			expect(
				screen.getByRole("combobox", { name: "Adapter type" }),
			).toHaveTextContent("RSSHub route");
			expect(
				screen.getByRole("combobox", { name: "Category" }),
			).toHaveTextContent("Other");
			expect(screen.getByLabelText("Priority (0-100)")).toHaveValue(50);
			expect(screen.getByRole("checkbox", { name: "Enabled" })).toBeChecked();

			const subscriptionsForm = screen
				.getByRole("button", { name: "Save subscription" })
				.closest("form");
			expect(subscriptionsForm).not.toBeNull();
			expect(subscriptionsForm).toHaveAttribute(
				"data-auto-disable-required",
				"true",
			);
			expect(subscriptionsForm).not.toHaveAttribute("method");
			expect(
				(subscriptionsForm as HTMLElement).querySelector(
					'input[type="hidden"][name="platform"]',
				),
			).toHaveValue("rsshub");
			expect(
				(subscriptionsForm as HTMLElement).querySelector(
					'input[type="hidden"][name="source_type"]',
				),
			).toHaveValue("rsshub_route");
			expect(
				(subscriptionsForm as HTMLElement).querySelector(
					'input[type="hidden"][name="adapter_type"]',
				),
			).toHaveValue("rsshub_route");
			expect(
				(subscriptionsForm as HTMLElement).querySelector(
					'input[type="hidden"][name="category"]',
				),
			).toHaveValue("misc");
			expect(
				(subscriptionsForm as HTMLElement).querySelector(
					'input[type="hidden"][name="session_token"]',
				),
			).toHaveValue("test-session-token");
			expect(
				within(subscriptionsForm as HTMLElement).getByRole("button", {
					name: "Save subscription",
				}),
			).toHaveAttribute("type", "submit");
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders generic RSS feed template with feed URL in source value and optional source URL",
		async () => {
			mockListSubscriptions.mockResolvedValue([]);

			render(
				await SubscriptionsPage({
					searchParams: {
						template: "generic_rss_feed",
					},
				}),
			);

			expect(
				screen.getByRole("combobox", { name: "Platform" }),
			).toHaveTextContent("Generic");
			expect(
				screen.getByRole("combobox", { name: "Source type" }),
			).toHaveTextContent("Source URL");
			expect(screen.getByLabelText("Source value")).toHaveAttribute(
				"placeholder",
				"https://example.com/feed.xml",
			);
			expect(screen.getByLabelText("Source URL (optional)")).not.toBeRequired();
			expect(
				screen.getAllByText(
					"Paste the exact RSS or Atom feed URL into Source value. Leave Source URL empty unless you want to store the same feed URL explicitly.",
				).length,
			).toBeGreaterThan(0);
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders ingest runs page with recent table and selected run detail",
		async () => {
			mockListIngestRuns.mockResolvedValue([
				{
					id: "run-1",
					subscription_id: null,
					workflow_id: "wf-1",
					platform: "youtube",
					max_new_videos: 5,
					status: "running",
					jobs_created: 2,
					candidates_count: 3,
					feeds_polled: 1,
					entries_fetched: 4,
					entries_normalized: 4,
					ingest_events_created: 3,
					ingest_event_duplicates: 1,
					job_duplicates: 0,
					error_message: null,
					created_at: "2026-02-01T00:00:00Z",
					updated_at: "2026-02-01T00:05:00Z",
					completed_at: null,
				},
			]);
			mockGetIngestRun.mockResolvedValue({
				id: "run-1",
				subscription_id: null,
				workflow_id: "wf-1",
				platform: "youtube",
				max_new_videos: 5,
				status: "running",
				jobs_created: 2,
				candidates_count: 3,
				feeds_polled: 1,
				entries_fetched: 4,
				entries_normalized: 4,
				ingest_events_created: 3,
				ingest_event_duplicates: 1,
				job_duplicates: 0,
				error_message: null,
				created_at: "2026-02-01T00:00:00Z",
				updated_at: "2026-02-01T00:05:00Z",
				completed_at: null,
				requested_by: "tester",
				requested_trace_id: "trace-1",
				filters_json: { platform: "youtube" },
				items: [
					{
						id: "item-1",
						subscription_id: null,
						video_id: "video-1",
						job_id: "job-1",
						ingest_event_id: "event-1",
						platform: "youtube",
						video_uid: "yt-1",
						source_url: "https://example.com/watch?v=1",
						title: "Video One",
						published_at: "2026-02-01T00:00:00Z",
						entry_hash: "hash-1",
						pipeline_mode: "full",
						content_type: "video",
						item_status: "queued",
						created_at: "2026-02-01T00:00:00Z",
						updated_at: "2026-02-01T00:05:00Z",
					},
				],
			});

			render(await IngestRunsPage({ searchParams: { run_id: "run-1" } }));

			expect(
				screen.getByRole("heading", { name: "Recent ingest runs" }),
			).toBeInTheDocument();
			expect(screen.getByLabelText("Run ID")).toHaveValue("run-1");
			expect(screen.getByRole("link", { name: "run-1" })).toHaveAttribute(
				"href",
				"/ingest-runs?run_id=run-1",
			);
			expect(screen.getByText("Run detail")).toBeInTheDocument();
			expect(screen.getByText("Workflow")).toBeInTheDocument();
			expect(screen.getByText("Jobs created")).toBeInTheDocument();
			expect(screen.getAllByText("Candidates").length).toBeGreaterThanOrEqual(
				2,
			);
			expect(screen.getByText("Video One")).toBeInTheDocument();
			expect(screen.getByText("Ingest run items")).toBeInTheDocument();
			expect(screen.getByRole("link", { name: "job-1" })).toHaveAttribute(
				"href",
				"/jobs?job_id=job-1",
			);
			expect(mockListIngestRuns).toHaveBeenCalledWith({ limit: 10 });
			expect(mockGetIngestRun).toHaveBeenCalledWith("run-1");
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders settings page config values and load failure message",
		async () => {
			mockGetNotificationConfig.mockResolvedValue({
				enabled: true,
				to_email: "ops@example.com",
				daily_digest_enabled: true,
				daily_digest_hour_utc: 8,
				failure_alert_enabled: true,
				category_rules: {},
				created_at: "2026-02-01T00:00:00Z",
				updated_at: "2026-02-02T00:00:00Z",
			});

			render(
				await SettingsPage({
					searchParams: {
						status: "success",
						code: "NOTIFICATION_CONFIG_SAVED",
					},
				}),
			);

			expect(
				screen.getByText("Notification settings saved."),
			).toBeInTheDocument();
			expect(screen.getByLabelText("Recipient email")).toHaveValue(
				"ops@example.com",
			);
			expect(
				screen.getByRole("checkbox", { name: "Enable notifications" }),
			).toBeChecked();
			expect(
				screen.getByRole("checkbox", { name: "Enable daily digest" }),
			).toBeChecked();
			expect(
				screen.getByRole("spinbutton", {
					name: "Daily digest send hour (UTC)",
				}),
			).toHaveValue(8);
			expect(
				screen.getByRole("spinbutton", {
					name: "Daily digest send hour (UTC)",
				}),
			).toBeEnabled();
			expect(
				screen.getByRole("checkbox", { name: "Enable failure alerts" }),
			).toBeChecked();
			expect(screen.getByText(/Local-time preview:/)).toBeInTheDocument();
			expect(
				screen.getByText("Current default recipient: ops@example.com"),
			).toBeInTheDocument();
			expect(
				screen.getByRole("button", { name: "Send test email" }),
			).toBeInTheDocument();

			const configForm = screen
				.getByRole("button", { name: "Save configuration" })
				.closest("form");
			expect(configForm).not.toBeNull();
			expect(configForm).not.toHaveAttribute("method");
			expect(
				(configForm as HTMLElement).querySelector(
					'input[type="hidden"][name="session_token"]',
				),
			).toHaveValue("test-session-token");
			expect(
				within(configForm as HTMLElement).getByRole("button", {
					name: "Save configuration",
				}),
			).toHaveAttribute("type", "submit");

			const sendTestForm = screen
				.getByRole("button", { name: "Send test email" })
				.closest("form");
			expect(sendTestForm).not.toBeNull();
			expect(sendTestForm).not.toHaveAttribute("method");
			expect(
				(sendTestForm as HTMLElement).querySelector(
					'input[type="hidden"][name="session_token"]',
				),
			).toHaveValue("test-session-token");
			expect(
				within(sendTestForm as HTMLElement).getByRole("button", {
					name: "Send test email",
				}),
			).toHaveAttribute("type", "submit");
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders settings load error fallback when API fails",
		async () => {
			mockGetNotificationConfig.mockRejectedValue(new Error("boom"));

			render(await SettingsPage({ searchParams: {} }));

			expect(screen.getByRole("alert")).toHaveTextContent(
				"The request failed. Please try again later.",
			);
			expect(
				screen.getByRole("link", { name: "Retry this page" }),
			).toHaveAttribute("href", "/settings");
			expect(
				screen.getByRole("button", { name: "Save configuration" }),
			).toBeInTheDocument();
			expect(
				screen.getByRole("checkbox", { name: "Enable notifications" }),
			).toBeChecked();
			expect(
				screen.getByRole("checkbox", { name: "Enable daily digest" }),
			).not.toBeChecked();
			expect(
				screen.getByRole("spinbutton", {
					name: "Daily digest send hour (UTC)",
				}),
			).toBeDisabled();
			expect(
				screen.getByRole("checkbox", { name: "Enable failure alerts" }),
			).toBeChecked();
		},
		PAGE_TEST_TIMEOUT_MS,
	);

	it(
		"renders subscriptions load error with retry link when API fails",
		async () => {
			mockListSubscriptions.mockRejectedValue(new Error("boom"));

			render(await SubscriptionsPage({ searchParams: {} }));

			expect(screen.getByRole("alert")).toHaveTextContent(
				"The request failed. Please try again later.",
			);
			expect(
				screen.getByRole("link", { name: "Retry this page" }),
			).toHaveAttribute("href", "/subscriptions");
			expect(
				screen.getByRole("button", { name: "Save subscription" }),
			).toBeInTheDocument();
		},
		PAGE_TEST_TIMEOUT_MS,
	);
});
