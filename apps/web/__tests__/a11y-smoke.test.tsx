import { cleanup, render } from "@testing-library/react";
import { axe } from "jest-axe";
import { beforeEach, describe, expect, it, vi } from "vitest";
import BriefingsPage from "@/app/briefings/page";
import FeedPage from "@/app/feed/page";
import JobsPage from "@/app/jobs/page";
import DashboardPage from "@/app/page";
import SearchPage from "@/app/search/page";
import SettingsPage from "@/app/settings/page";
import SubscriptionsPage from "@/app/subscriptions/page";

const mockListSubscriptions = vi.fn();
const mockListSubscriptionTemplates = vi.fn();
const mockListWatchlists = vi.fn();
const mockListVideos = vi.fn();
const mockListIngestRuns = vi.fn();
const mockGetWatchlistBriefing = vi.fn();
const mockGetWatchlistBriefingPage = vi.fn();
const mockGetJob = vi.fn();
const mockGetDigestFeed = vi.fn();
const mockGetArtifactMarkdown = vi.fn();
const mockGetNotificationConfig = vi.fn();
const mockSearchRetrieval = vi.fn();

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

vi.mock("next/navigation", () => ({
	useRouter: () => ({ refresh: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/app/action-security", () => ({
	getActionSessionTokenForForm: () => "test-session-token",
}));

vi.mock("@/lib/api/client", () => ({
	apiClient: {
		listSubscriptions: (...args: unknown[]) => mockListSubscriptions(...args),
		listSubscriptionTemplates: (...args: unknown[]) =>
			mockListSubscriptionTemplates(...args),
		listWatchlists: (...args: unknown[]) => mockListWatchlists(...args),
		listVideos: (...args: unknown[]) => mockListVideos(...args),
		listIngestRuns: (...args: unknown[]) => mockListIngestRuns(...args),
		getWatchlistBriefing: (...args: unknown[]) =>
			mockGetWatchlistBriefing(...args),
		getWatchlistBriefingPage: (...args: unknown[]) =>
			mockGetWatchlistBriefingPage(...args),
		getJob: (...args: unknown[]) => mockGetJob(...args),
		getDigestFeed: (...args: unknown[]) => mockGetDigestFeed(...args),
		getArtifactMarkdown: (...args: unknown[]) =>
			mockGetArtifactMarkdown(...args),
		getNotificationConfig: (...args: unknown[]) =>
			mockGetNotificationConfig(...args),
		searchRetrieval: (...args: unknown[]) => mockSearchRetrieval(...args),
		pollIngest: vi.fn(),
		deleteSubscription: vi.fn(),
		batchUpdateSubscriptionCategory: vi.fn(),
	},
}));

describe("a11y smoke", () => {
	const A11Y_TIMEOUT_MS = 60000;

	beforeEach(() => {
		vi.clearAllMocks();
		mockListSubscriptions.mockResolvedValue([]);
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
					support_tier: "strong_supported",
					platform: "youtube",
					source_type: "youtube_channel_id",
					adapter_type: "rsshub_route",
					content_profile: "video",
					category: "creator",
					source_value_placeholder: "UCxxxx",
					rsshub_route_hint: "/youtube/channel/UCxxxx",
					source_url_required: false,
					supports_video_pipeline: true,
					evidence_note: "Strongly supported video lane.",
				},
				{
					id: "generic_rsshub_route",
					label: "Generic RSSHub route",
					support_tier: "generic_supported",
					platform: "rsshub",
					source_type: "rsshub_route",
					adapter_type: "rsshub_route",
					content_profile: "article",
					category: "misc",
					source_value_placeholder: "/namespace/path",
					rsshub_route_hint: "/namespace/path",
					source_url_required: false,
					supports_video_pipeline: false,
					evidence_note:
						"Substrate does not block RSSHub universe, but routes are not claimed as individually verified.",
				},
			],
		});
		mockListWatchlists.mockResolvedValue([
			{
				id: "wl-1",
				name: "Retry policy",
				matcher_type: "topic_key",
				matcher_value: "retry-policy",
				delivery_channel: "dashboard",
				enabled: true,
				created_at: "2026-03-31T10:00:00Z",
				updated_at: "2026-03-31T10:00:00Z",
			},
		]);
		mockListVideos.mockResolvedValue([]);
		mockListIngestRuns.mockResolvedValue([]);
		const briefing = {
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
				overview: "Retry policy is converging across sources.",
				source_count: 3,
				run_count: 4,
				matched_cards: 6,
				story_count: 2,
				primary_story_headline: "Retries became default posture",
				signals: [
					{
						story_key: "story.retry-policy",
						headline: "Retry guidance is stabilizing",
						matched_card_count: 6,
						latest_run_job_id: "job-1",
						reason: "More runs now surface the same retry baseline.",
					},
				],
			},
			differences: {
				latest_job_id: "job-1",
				previous_job_id: null,
				added_topics: ["retry-policy"],
				removed_topics: [],
				added_claim_kinds: ["recommendation"],
				removed_claim_kinds: [],
				new_story_keys: ["story.retry-policy"],
				removed_story_keys: [],
				compare: {
					job_id: "job-1",
					has_previous: false,
					previous_job_id: null,
					changed: true,
					added_lines: 3,
					removed_lines: 0,
					diff_excerpt: "Retry guidance appeared in the latest run.",
					compare_route: "/jobs?job_id=job-1",
				},
			},
			evidence: {
				suggested_story_id: "story-1",
				stories: [
					{
						story_id: "story-1",
						story_key: "story.retry-policy",
						headline: "Retries became default posture",
						topic_key: "retry-policy",
						topic_label: "Retry policy",
						source_count: 3,
						run_count: 4,
						matched_card_count: 6,
						platforms: ["youtube", "rss"],
						claim_kinds: ["recommendation"],
						source_urls: ["https://example.com"],
						latest_run_job_id: "job-1",
						evidence_cards: [
							{
								card_id: "card-1",
								job_id: "job-1",
								video_id: "video-1",
								platform: "youtube",
								video_title: "AI Weekly",
								source_url: "https://example.com",
								created_at: "2026-03-31T10:00:00Z",
								card_type: "claim",
								card_title: "Retry policy became explicit",
								card_body:
									"The workflow now treats retries as first-line safety.",
								source_section: "Digest",
								topic_key: "retry-policy",
								topic_label: "Retry policy",
								claim_kind: "recommendation",
							},
						],
						routes: {
							watchlist_trend: "/trends?watchlist_id=wl-1",
							job_compare: "/jobs?job_id=job-1",
							job_bundle: null,
							job_knowledge_cards: "/knowledge?job_id=job-1",
						},
					},
				],
				featured_runs: [
					{
						job_id: "job-1",
						video_id: "video-1",
						platform: "youtube",
						title: "AI Weekly",
						source_url: "https://example.com",
						created_at: "2026-03-31T10:00:00Z",
						matched_card_count: 1,
						routes: {
							watchlist_trend: "/trends?watchlist_id=wl-1",
							job_compare: "/jobs?job_id=job-1",
							job_bundle: null,
							job_knowledge_cards: "/knowledge?job_id=job-1",
						},
					},
				],
			},
		};
		mockGetWatchlistBriefing.mockResolvedValue(briefing);
		mockGetWatchlistBriefingPage.mockResolvedValue({
			context: {
				watchlist_id: "wl-1",
				watchlist_name: "Retry policy",
				story_id: null,
				selected_story_id: "story-1",
				story_headline: "Retries became default posture",
				topic_key: "retry-policy",
				topic_label: "Retry policy",
				selection_basis: "suggested_story_id",
				question_seed: "Retry policy",
			},
			briefing,
			selected_story: briefing.evidence.stories[0],
			ask_route:
				"/ask?watchlist_id=wl-1&question=Retries+became+default+posture&story_id=story-1&topic_key=retry-policy&via=briefing-story",
			compare_route: "/jobs?job_id=job-1",
		});
		mockGetNotificationConfig.mockResolvedValue({
			enabled: true,
			to_email: "ops@example.com",
			daily_digest_enabled: false,
			daily_digest_hour_utc: null,
			failure_alert_enabled: true,
			category_rules: {},
			created_at: "2026-02-01T00:00:00Z",
			updated_at: "2026-02-02T00:00:00Z",
		});
		mockGetJob.mockResolvedValue({
			id: "job-1",
			video_id: "video-1",
			status: "running",
			created_at: "2026-02-01T00:00:00Z",
			updated_at: "2026-02-01T00:00:10Z",
			pipeline_final_status: "running",
			step_summary: [],
			degradations: [],
			artifacts_index: {},
		});
		mockGetDigestFeed.mockResolvedValue({
			items: [
				{
					feed_id: "feed-1",
					job_id: "job-1",
					video_url: "https://www.youtube.com/watch?v=abc",
					title: "AI Weekly",
					source: "youtube",
					source_name: "Tech Channel",
					category: "tech",
					published_at: "2026-02-01T00:00:00Z",
					summary_md: "## summary",
					artifact_type: "digest",
				},
			],
			has_more: false,
			next_cursor: null,
		});
		mockGetArtifactMarkdown.mockResolvedValue({
			markdown: "# artifact",
			meta: {
				frame_files: [],
				job: { id: "job-1" },
			},
		});
		mockSearchRetrieval.mockResolvedValue({
			query: "agent workflows",
			top_k: 8,
			filters: {},
			items: [],
		});
	});

	it(
		"dashboard/subscriptions/settings/feed/jobs/search/briefings pages have no critical accessibility violations",
		async () => {
			const dashboard = render(await DashboardPage());
			const dashboardResults = await axe(dashboard.container);
			expect(dashboardResults.violations).toHaveLength(0);
			dashboard.unmount();
			cleanup();

			const subscriptions = render(
				await SubscriptionsPage({ searchParams: {} }),
			);
			const subscriptionsResults = await axe(subscriptions.container);
			expect(subscriptionsResults.violations).toHaveLength(0);
			subscriptions.unmount();
			cleanup();

			const settings = render(await SettingsPage({ searchParams: {} }));
			const settingsResults = await axe(settings.container);
			expect(settingsResults.violations).toHaveLength(0);
			settings.unmount();
			cleanup();

			const jobs = render(
				await JobsPage({ searchParams: { job_id: "job-1" } }),
			);
			const jobsResults = await axe(jobs.container);
			expect(jobsResults.violations).toHaveLength(0);
			jobs.unmount();
			cleanup();

			const feed = render(await FeedPage({ searchParams: {} }));
			const feedResults = await axe(feed.container);
			expect(feedResults.violations).toHaveLength(0);
			feed.unmount();
			cleanup();

			const search = render(await SearchPage({ searchParams: {} }));
			const searchResults = await axe(search.container);
			expect(searchResults.violations).toHaveLength(0);
			search.unmount();
			cleanup();

			const briefings = render(
				await BriefingsPage({ searchParams: { watchlist_id: "wl-1" } }),
			);
			const briefingsResults = await axe(briefings.container);
			expect(briefingsResults.violations).toHaveLength(0);
			briefings.unmount();
			cleanup();
		},
		A11Y_TIMEOUT_MS,
	);
});
