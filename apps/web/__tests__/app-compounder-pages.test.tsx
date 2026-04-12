import { render, screen, within } from "@testing-library/react";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BriefingsPage from "@/app/briefings/page";
import PlaygroundPage from "@/app/playground/page";
import TrendsPage from "@/app/trends/page";
import {
	generateMetadata as generateUseCaseMetadata,
	default as UseCasePage,
} from "@/app/use-cases/[slug]/page";
import WatchlistsPage from "@/app/watchlists/page";

const mockListWatchlists = vi.fn();
const mockGetWatchlistBriefing = vi.fn();
const mockGetWatchlistBriefingPage = vi.fn();
const mockGetWatchlistTrend = vi.fn();
const mockGetJobEvidenceBundle = vi.fn();
const mockGetOpsInbox = vi.fn();

vi.mock("next/link", () => ({
	default: ({
		href,
		children,
		...rest
	}: AnchorHTMLAttributes<HTMLAnchorElement> & {
		href: string;
		children: ReactNode;
	}) => (
		<a href={href} {...rest}>
			{children}
		</a>
	),
}));

vi.mock("@/lib/api/client", () => ({
	apiClient: {
		listWatchlists: (...args: unknown[]) => mockListWatchlists(...args),
		getWatchlistBriefing: (...args: unknown[]) =>
			mockGetWatchlistBriefing(...args),
		getWatchlistBriefingPage: (...args: unknown[]) =>
			mockGetWatchlistBriefingPage(...args),
		getWatchlistTrend: (...args: unknown[]) => mockGetWatchlistTrend(...args),
		getJobEvidenceBundle: (...args: unknown[]) =>
			mockGetJobEvidenceBundle(...args),
		getOpsInbox: (...args: unknown[]) => mockGetOpsInbox(...args),
	},
}));

describe("compounder pages", () => {
	beforeEach(() => {
		vi.clearAllMocks();
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
		mockGetWatchlistTrend.mockResolvedValue({
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
				recent_runs: 2,
				matched_cards: 4,
				matcher_type: "topic_key",
				matcher_value: "retry-policy",
			},
			source_coverage: [
				{
					platform: "youtube",
					run_count: 1,
					card_count: 2,
					latest_created_at: "2026-03-31T10:00:00Z",
				},
				{
					platform: "bilibili",
					run_count: 1,
					card_count: 1,
					latest_created_at: "2026-03-31T11:00:00Z",
				},
				{
					platform: "rss",
					run_count: 1,
					card_count: 1,
					latest_created_at: "2026-03-31T12:00:00Z",
				},
			],
			timeline: [
				{
					job_id: "job-1",
					video_id: "video-1",
					platform: "youtube",
					title: "AI Weekly",
					source_url: "https://example.com",
					created_at: "2026-03-31T10:00:00Z",
					matched_card_count: 2,
					cards: [],
					topics: ["retry-policy"],
					claim_kinds: ["recommendation"],
					added_topics: ["retry-policy"],
					removed_topics: [],
					added_claim_kinds: ["recommendation"],
					removed_claim_kinds: [],
				},
				{
					job_id: "job-2",
					video_id: "video-2",
					platform: "bilibili",
					title: "Bili Update",
					source_url: "https://bilibili.com/video/xyz",
					created_at: "2026-03-31T11:00:00Z",
					matched_card_count: 1,
					cards: [],
					topics: ["retry-policy"],
					claim_kinds: ["recommendation"],
					added_topics: [],
					removed_topics: [],
					added_claim_kinds: [],
					removed_claim_kinds: [],
				},
				{
					job_id: "job-3",
					video_id: "video-3",
					platform: "rss",
					title: "RSS Digest",
					source_url: "https://example.com/feed.xml",
					created_at: "2026-03-31T12:00:00Z",
					matched_card_count: 1,
					cards: [],
					topics: ["retry-policy"],
					claim_kinds: [],
					added_topics: [],
					removed_topics: [],
					added_claim_kinds: [],
					removed_claim_kinds: [],
				},
			],
		});
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
				overview:
					"Retry policy keeps surfacing across YouTube, Bilibili, and RSS sources.",
				source_count: 3,
				run_count: 4,
				matched_cards: 6,
				story_count: 2,
				primary_story_headline:
					"Retries moved from recommendation to default posture",
				signals: [
					{
						story_key: "topic:retry-policy",
						headline: "Retry policy is becoming a stable default",
						matched_card_count: 6,
						latest_run_job_id: "job-3",
						reason:
							"Recent runs now describe retry handling as the baseline safe path.",
					},
				],
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
				compare: {
					job_id: "job-3",
					has_previous: true,
					previous_job_id: "job-2",
					changed: true,
					added_lines: 12,
					removed_lines: 4,
					diff_excerpt:
						"Retry guidance moved from optional to default posture.",
					compare_route: "/jobs?job_id=job-3&via=briefing-compare",
				},
			},
			evidence: {
				suggested_story_id: "story-1",
				stories: [
					{
						story_id: "story-1",
						story_key: "topic:retry-policy",
						headline: "Retries moved from recommendation to default posture",
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
							briefing:
								"/briefings?watchlist_id=wl-1&story_id=story-1&via=briefing-story",
							ask: "/ask?watchlist_id=wl-1&question=Retries+moved+from+recommendation+to+default+posture&story_id=story-1&topic_key=retry-policy&via=briefing-story",
							job_compare: "/jobs?job_id=job-1&via=briefing-compare",
							job_bundle: "/api/v1/jobs/job-1/bundle",
							job_knowledge_cards: "/knowledge?job_id=job-1",
						},
					},
				],
				featured_runs: [
					{
						job_id: "job-3",
						video_id: "video-3",
						platform: "rss",
						title: "RSS Digest",
						source_url: "https://example.com/feed.xml",
						created_at: "2026-03-31T12:00:00Z",
						matched_card_count: 1,
						routes: {
							watchlist_trend: "/trends?watchlist_id=wl-1",
							briefing: "/briefings?watchlist_id=wl-1&via=briefing-run",
							ask: "/ask?watchlist_id=wl-1&via=briefing-run",
							job_compare: "/jobs?job_id=job-3&via=briefing-run",
							job_bundle: "/api/v1/jobs/job-3/bundle",
							job_knowledge_cards: "/knowledge?job_id=job-3",
						},
					},
				],
			},
			selection: {
				selected_story_id: "story-1",
				selection_basis: "suggested_story_id",
				story: {
					story_id: "story-1",
					story_key: "topic:retry-policy",
					headline: "Retries moved from recommendation to default posture",
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
						briefing:
							"/briefings?watchlist_id=wl-1&story_id=story-1&via=briefing-story",
						ask: "/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy&via=briefing-story",
						job_compare: "/jobs?job_id=job-1&via=briefing-compare",
						job_bundle: "/api/v1/jobs/job-1/bundle",
						job_knowledge_cards: "/knowledge?job_id=job-1",
					},
				},
			},
		};
		mockGetWatchlistBriefing.mockResolvedValue(briefing);
		mockGetWatchlistBriefingPage.mockResolvedValue({
			context: {
				watchlist_id: "wl-1",
				watchlist_name: "Retry policy",
				story_id: null,
				selected_story_id: "story-1",
				story_headline: "Retries moved from recommendation to default posture",
				topic_key: "retry-policy",
				topic_label: "Retry policy",
				selection_basis: "suggested_story_id",
				question_seed: "Retry policy",
			},
			briefing,
			selected_story: briefing.selection.story,
			ask_route:
				"/ask?watchlist_id=wl-1&question=Retries+moved+from+recommendation+to+default+posture&story_id=story-1&topic_key=retry-policy&via=briefing-story",
			compare_route: "/jobs?job_id=job-3&via=briefing-compare",
		});
		mockGetJobEvidenceBundle.mockResolvedValue({
			bundle_kind: "sourceharbor_job_evidence_bundle_v1",
			sharing_scope: "internal",
			sample: false,
			generated_at: "2026-03-31T12:00:00Z",
			proof_boundary:
				"Internal evidence bundle only. Do not treat this as hosted proof.",
			job: { id: "job-1" },
			trace_summary: { step_count: 4 },
			digest: "# Digest",
			digest_meta: null,
			comparison: null,
			knowledge_cards: [{ id: "card-1" }],
			artifact_manifest: {},
			step_summary: [],
		});
		mockGetOpsInbox.mockResolvedValue({
			gates: {
				notifications: {
					status: "blocked",
					summary:
						"Notification send paths exist, but live delivery is blocked by missing Resend secrets.",
					next_step: "Provide RESEND_API_KEY.",
					details: {},
				},
			},
		});
	});

	it("renders watchlists page with persistent objects and readiness hint", async () => {
		render(
			await WatchlistsPage({
				searchParams: { watchlist_id: "wl-1" },
			}),
		);

		expect(
			screen.getByRole("heading", { name: "Watchlists" }),
		).toBeInTheDocument();
		expect(screen.getByText("Retry policy")).toBeInTheDocument();
		expect(
			screen
				.getAllByRole("link", { name: "Open briefing" })
				.map((element) => element.getAttribute("href")),
		).toEqual(
			expect.arrayContaining([
				"/briefings?watchlist_id=wl-1",
				"/briefings?watchlist_id=wl-1",
			]),
		);
		expect(
			screen.getByText(
				/Notification send paths exist, but live delivery is blocked/i,
			),
		).toBeInTheDocument();
		expect(
			screen.getAllByRole("heading", { name: "Continue this watchlist" })
				.length,
		).toBeGreaterThan(0);
		expect(
			screen
				.getAllByRole("link", { name: "Open compounder front door" })
				.map((element) => element.getAttribute("href")),
		).toContain("/trends?watchlist_id=wl-1");
		expect(
			screen.getByRole("link", { name: "Ask about this story" }),
		).toHaveAttribute(
			"href",
			"/ask?watchlist_id=wl-1&question=Retries+moved+from+recommendation+to+default+posture&story_id=story-1&topic_key=retry-policy&via=briefing-story",
		);
		expect(
			screen.getByRole("link", { name: "Review sample-proof boundary" }),
		).toHaveAttribute("href", "/playground");
	});

	it("renders trend page as merged story plus source coverage", async () => {
		render(
			await TrendsPage({
				searchParams: { watchlist_id: "wl-1" },
			}),
		);

		expect(
			screen.getByRole("heading", { name: "Merged source stories" }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("heading", { name: "Compounder front door" }),
		).toBeInTheDocument();
		expect(screen.getByText("Source coverage")).toBeInTheDocument();
		expect(screen.getByText("Merged stories")).toBeInTheDocument();
		expect(screen.getByText("Latest lead-story bundle")).toBeInTheDocument();
		expect(
			screen.getByText(
				/Internal evidence bundle only\. Do not treat this as hosted proof/i,
			),
		).toBeInTheDocument();
		expect(screen.getAllByText("AI Weekly").length).toBeGreaterThan(0);
		expect(screen.getAllByText("Bili Update").length).toBeGreaterThan(0);
		expect(screen.getAllByText("RSS Digest").length).toBeGreaterThan(0);
		expect(screen.getByRole("link", { name: "Open briefing" })).toHaveAttribute(
			"href",
			"/briefings?watchlist_id=wl-1",
		);
		expect(screen.getAllByText("retry-policy").length).toBeGreaterThan(0);
		expect(screen.getByText(/Added topics: retry-policy/i)).toBeInTheDocument();
		expect(
			screen.getByRole("link", { name: "Open evidence bundle" }),
		).toHaveAttribute("href", "/api/v1/jobs/job-1/bundle");
		expect(
			screen.getByRole("link", { name: "Open unified briefing" }),
		).toHaveAttribute("href", "/briefings?watchlist_id=wl-1&story_id=story-1");
		expect(
			within(screen.getAllByText("AI Weekly")[0].closest("article")!).getByRole(
				"link",
				{ name: "Open bundle" },
			),
		).toHaveAttribute("href", "/api/v1/jobs/job-1/bundle");
		expect(() =>
			within(screen.getAllByText("AI Weekly")[0].closest("article")!).getByRole(
				"link",
				{ name: "Open knowledge" },
			),
		).toThrow();
		expect(
			within(
				screen.getAllByText("AI Weekly")[0].closest("article")!,
			).getAllByRole("link", { name: "Open knowledge" })[0],
		).toHaveAttribute("href", "/knowledge?job_id=job-1");
		expect(
			screen.getByRole("link", { name: "Open sample playground" }),
		).toHaveAttribute("href", "/playground");
		expect(
			screen.getByRole("link", { name: "Open watchlists" }),
		).toHaveAttribute("href", "/watchlists");
		expect(
			screen.getByRole("link", { name: "Open research use case" }),
		).toHaveAttribute("href", "/use-cases/research-pipeline");
	});

	it("renders story-card CTA labels for merged trends", async () => {
		mockGetWatchlistTrend.mockResolvedValueOnce({
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
				recent_runs: 2,
				matched_cards: 4,
				matcher_type: "topic_key",
				matcher_value: "retry-policy",
			},
			source_coverage: [
				{
					platform: "youtube",
					run_count: 1,
					card_count: 2,
					latest_created_at: "2026-03-31T10:00:00Z",
				},
			],
			timeline: [
				{
					job_id: "job-1",
					video_id: "video-1",
					platform: "youtube",
					title: "AI Weekly",
					source_url: "https://example.com",
					created_at: "2026-03-31T10:00:00Z",
					matched_card_count: 2,
					cards: [],
					topics: ["retry-policy"],
					claim_kinds: ["recommendation"],
					added_topics: ["retry-policy"],
					removed_topics: [],
					added_claim_kinds: ["recommendation"],
					removed_claim_kinds: [],
				},
			],
			merged_stories: [
				{
					id: "story-1",
					story_key: "topic:retry-policy",
					headline: "Retries moved from recommendation to default posture",
					topic_key: "retry-policy",
					topic_label: "Retry policy",
					source_urls: ["https://example.com"],
					run_ids: ["job-1"],
					platforms: ["youtube"],
					claim_kinds: ["recommendation"],
					latest_created_at: "2026-03-31T10:00:00Z",
					cards: [
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
				},
			],
		});

		render(
			await TrendsPage({
				searchParams: { watchlist_id: "wl-1" },
			}),
		);

		expect(
			screen.getByRole("link", { name: "Ask this story" }),
		).toHaveAttribute(
			"href",
			"/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy&question=Retries+moved+from+recommendation+to+default+posture",
		);
	});

	it("renders briefing page as summary first, then differences, then evidence", async () => {
		render(
			await BriefingsPage({
				searchParams: { watchlist_id: "wl-1" },
			}),
		);

		expect(
			screen.getByRole("heading", { name: "Unified briefings" }),
		).toBeInTheDocument();
		expect(
			screen.getByText("What the story is saying now"),
		).toBeInTheDocument();
		expect(screen.getByText("What changed recently")).toBeInTheDocument();
		expect(screen.getByText("Evidence drill-down")).toBeInTheDocument();
		expect(
			screen.getByText(/Retry policy keeps surfacing across YouTube/i),
		).toBeInTheDocument();
		expect(
			screen.getByText(/Retry guidance moved from optional/i),
		).toBeInTheDocument();
		expect(
			screen.getByText("Retry policy is becoming a stable default"),
		).toBeInTheDocument();
		expect(
			screen.getByRole("link", { name: "Ask this briefing" }),
		).toHaveAttribute(
			"href",
			"/ask?watchlist_id=wl-1&question=Retries+moved+from+recommendation+to+default+posture&story_id=story-1&topic_key=retry-policy&via=briefing-story",
		);
		expect(
			screen.getByRole("link", { name: "Ask about this story" }),
		).toHaveAttribute(
			"href",
			"/ask?watchlist_id=wl-1&question=Retries+moved+from+recommendation+to+default+posture&story_id=story-1&topic_key=retry-policy&via=briefing-story",
		);
		expect(screen.getByRole("link", { name: "Open briefing" })).toHaveAttribute(
			"href",
			"/briefings?watchlist_id=wl-1&story_id=story-1&via=briefing-story",
		);
		expect(screen.getByRole("link", { name: "Open compare" })).toHaveAttribute(
			"href",
			"/jobs?job_id=job-3&via=briefing-compare",
		);
		expect(
			screen
				.getAllByRole("link", { name: "Open knowledge" })
				.map((element) => element.getAttribute("href")),
		).toEqual(
			expect.arrayContaining([
				"/knowledge?job_id=job-1",
				"/knowledge?job_id=job-3",
			]),
		);
	});

	it("renders read-only playground as sample-labeled surface", async () => {
		render(await PlaygroundPage());

		expect(
			screen.getByRole("heading", { name: "Read-only sample playground" }),
		).toBeInTheDocument();
		expect(screen.getByText(/Sample boundary/i)).toBeInTheDocument();
		expect(screen.getByText(/Sharing scope:/i)).toBeInTheDocument();
		expect(
			screen.getByRole("link", { name: "Open compounder front door" }),
		).toHaveAttribute("href", "/trends");
		expect(
			screen.getByRole("link", { name: "Open live watchlists" }),
		).toHaveAttribute("href", "/watchlists");
		expect(
			screen.getByRole("link", { name: "Open research use case" }),
		).toHaveAttribute("href", "/use-cases/research-pipeline");
	});

	it("renders truthful use-case page", async () => {
		render(
			await UseCasePage({
				params: { slug: "youtube" },
			}),
		);

		expect(
			screen.getByRole("heading", { name: "YouTube to AI digest" }),
		).toBeInTheDocument();
		expect(
			screen.getByText(/evidence bundle keep the output reviewable/i),
		).toBeInTheDocument();
		expect(screen.getByText("Current action path")).toBeInTheDocument();
		expect(
			screen.getByRole("link", { name: "Open builders guide" }),
		).toHaveAttribute("href", "/builders");
		expect(
			screen.getByRole("link", { name: "Open starter packs" }),
		).toHaveAttribute(
			"href",
			"https://github.com/xiaojiou176-open/sourceharbor/blob/main/starter-packs/README.md",
		);
	});

	it("supports promised params for use-case runtime and metadata generation", async () => {
		const params = Promise.resolve({ slug: "codex" });

		const metadata = await generateUseCaseMetadata({ params });
		render(await UseCasePage({ params }));

		expect(metadata.title).toBe("Codex operator workflow");
		expect(metadata.description).toMatch(/Codex through MCP or HTTP/i);
		expect(
			screen.getByRole("heading", { name: "Codex operator workflow" }),
		).toBeInTheDocument();
	});
});
