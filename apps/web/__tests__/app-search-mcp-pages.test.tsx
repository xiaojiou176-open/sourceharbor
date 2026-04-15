import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AskPage from "@/app/ask/page";
import McpPage from "@/app/mcp/page";
import SearchPage from "@/app/search/page";

const mockSearchRetrieval = vi.fn();
const mockListWatchlists = vi.fn();
const mockGetAskAnswer = vi.fn();

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
		searchRetrieval: (...args: unknown[]) => mockSearchRetrieval(...args),
		listWatchlists: (...args: unknown[]) => mockListWatchlists(...args),
		getAskAnswer: (...args: unknown[]) => mockGetAskAnswer(...args),
	},
}));

describe("search and MCP front doors", () => {
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
	});

		it("renders grounded search results with widened source filtering", async () => {
			mockSearchRetrieval.mockResolvedValue({
				query: "agent workflows",
				top_k: 8,
				filters: { platform: "rss" },
				items: [
					{
					job_id: "job-1",
					video_id: "video-1",
					platform: "rss",
					video_uid: "vid-1",
					source_url: "https://example.com/feed.xml",
					title: "AI Weekly",
					kind: "video_digest_v1",
					mode: "full",
					source: "knowledge_cards",
						snippet: "Agent workflows with retry and review loops.",
						score: 2.4,
					},
					{
						job_id: "job-2",
						video_id: "video-2",
						platform: "rss",
						video_uid: "vid-2",
						source_url: "https://example.com/ops.xml",
						title: "Ops Digest",
						kind: "video_digest_v1",
						mode: "full",
						source: "knowledge_cards",
						snippet: "Operational follow-ups after the first reading pass.",
						score: 1.6,
					},
				],
			});

		render(
			await SearchPage({
				searchParams: {
					q: "agent workflows",
					mode: "keyword",
					platform: "rss",
				},
			}),
		);

		expect(mockSearchRetrieval).toHaveBeenCalledWith({
			query: "agent workflows",
			mode: "keyword",
			top_k: 8,
			filters: { platform: "rss" },
		});
		expect(screen.getByRole("heading", { name: "Search" })).toBeInTheDocument();
			expect(
				screen.getByRole("combobox", { name: "Source" }),
			).toHaveTextContent("RSS / web source");
			expect(screen.getByRole("heading", { name: "Start with the best hit" })).toBeInTheDocument();
			expect(screen.getAllByText("AI Weekly")).toHaveLength(1);
			expect(screen.getByRole("heading", { name: "Keep reading" })).toBeInTheDocument();
			expect(screen.getByText("Ops Digest")).toBeInTheDocument();
			expect(
				screen.getAllByRole("link", { name: "See source trail" })[0],
			).toHaveAttribute("href", "/jobs?job_id=job-1");
			expect(
				screen
					.getAllByRole("link", { name: "Open notes" })
					.map((element) => element.getAttribute("href")),
			).toEqual(["/knowledge?job_id=job-2"]);
			expect(
				screen
					.getAllByRole("link", { name: "Open preview" })
					.map((element) => element.getAttribute("href")),
			).toEqual(
				expect.arrayContaining(["/feed?item=job-1", "/feed?item=job-2"]),
			);
			expect(screen.getByRole("link", { name: "Open briefing" })).toHaveAttribute(
				"href",
				"/briefings",
			);
			expect(screen.queryByText(/Search results/i)).not.toBeInTheDocument();
		});

	it("renders Ask as a briefing-aware front door with answer, changes, and evidence", async () => {
		mockGetAskAnswer.mockResolvedValue({
			question: "retry policy",
			mode: "keyword",
			top_k: 6,
			context: {
				watchlist_id: "wl-1",
				watchlist_name: "Retry policy",
				story_id: "story-1",
				selected_story_id: "story-1",
				story_headline: "Retries moved from optional advice to default posture",
				topic_key: "retry-policy",
				topic_label: "Retry policy",
				selection_basis: "query_match",
				filters: {},
				briefing_available: true,
			},
			answer_state: "briefing_grounded",
			answer_headline: "Retries moved from optional advice to default posture",
			answer_summary:
				"Retry policy keeps surfacing across YouTube, Bilibili, and RSS sources.",
			answer_reason:
				"Retries moved from optional advice to default posture is the selected story focus across 4 runs and 6 matched evidence cards.",
			answer_confidence: "grounded",
			story_change_summary:
				"Retries moved from optional advice to default posture is the selected story focus across 4 runs and 6 matched evidence cards.",
			story_page: {
				context: {
					watchlist_id: "wl-1",
					watchlist_name: "Retry policy",
					story_id: "story-1",
					selected_story_id: "story-1",
					story_headline:
						"Retries moved from optional advice to default posture",
					topic_key: "retry-policy",
					topic_label: "Retry policy",
					selection_basis: "query_match",
					question_seed: "retry policy",
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
							"Retry policy keeps surfacing across YouTube, Bilibili, and RSS sources.",
						source_count: 3,
						run_count: 4,
						story_count: 2,
						matched_cards: 6,
						primary_story_headline:
							"Retries moved from optional advice to default posture",
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
								headline:
									"Retries moved from optional advice to default posture",
								topic_key: "retry-policy",
								topic_label: "Retry policy",
								source_count: 3,
								run_count: 4,
								matched_card_count: 6,
								platforms: ["youtube", "rss"],
								claim_kinds: ["recommendation"],
								source_urls: ["https://example.com/retry-policy"],
								latest_run_job_id: "job-1",
								evidence_cards: [],
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
							{
								story_id: "story-2",
								story_key: "topic:failure-budget",
								headline: "Failure budgets became the comparison lens",
								topic_key: "failure-budget",
								topic_label: "Failure budget",
								source_count: 2,
								run_count: 3,
								matched_card_count: 3,
								platforms: ["rss"],
								claim_kinds: ["analysis"],
								source_urls: ["https://example.com/failure-budget"],
								latest_run_job_id: "job-3",
								evidence_cards: [],
								routes: {
									watchlist_trend: "/trends?watchlist_id=wl-1",
									briefing:
										"/briefings?watchlist_id=wl-1&story_id=story-2&via=secondary-story",
									ask: "/ask?watchlist_id=wl-1&story_id=story-2&topic_key=failure-budget&via=secondary-story",
									job_compare: "/jobs?job_id=job-3&via=secondary-story",
									job_bundle: "/api/v1/jobs/job-3/bundle",
									job_knowledge_cards: "/knowledge?job_id=job-3",
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
						story: null,
					},
				},
				selected_story: {
					story_id: "story-1",
					story_key: "topic:retry-policy",
					headline: "Retries moved from optional advice to default posture",
					topic_key: "retry-policy",
					topic_label: "Retry policy",
					source_count: 3,
					run_count: 4,
					matched_card_count: 6,
					platforms: ["youtube", "rss"],
					claim_kinds: ["recommendation"],
					source_urls: ["https://example.com/retry-policy"],
					latest_run_job_id: "job-1",
					evidence_cards: [
						{
							card_id: "card-1",
							job_id: "job-1",
							video_id: "video-1",
							platform: "youtube",
							video_title: "AI Weekly",
							source_url: "https://example.com/retry-policy",
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
				story_change_summary:
					"Retries moved from optional advice to default posture is the selected story focus across 4 runs and 6 matched evidence cards.",
				citations: [
					{
						kind: "briefing_story",
						label: "Retry Policy",
						snippet: "Supported across 3 source families and 4 recent runs.",
						source_url: null,
						job_id: "job-3",
						route:
							"/briefings?watchlist_id=wl-1&story_id=story-1&via=briefing-story",
						route_label: "Open briefing story",
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
				ask_route:
					"/ask?watchlist_id=wl-1&story_id=story-1&topic_key=retry-policy&via=briefing-story",
				compare_route: "/jobs?job_id=job-1&via=briefing-compare",
				fallback_reason: null,
				fallback_next_step: null,
				fallback_actions: [],
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
						"Retry policy keeps surfacing across YouTube, Bilibili, and RSS sources.",
					source_count: 3,
					run_count: 4,
					story_count: 2,
					matched_cards: 6,
					primary_story_headline:
						"Retries moved from optional advice to default posture",
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
							headline: "Retries moved from optional advice to default posture",
							topic_key: "retry-policy",
							topic_label: "Retry policy",
							source_count: 3,
							run_count: 4,
							matched_card_count: 6,
							platforms: ["youtube", "rss"],
							claim_kinds: ["recommendation"],
							source_urls: ["https://example.com/retry-policy"],
							latest_run_job_id: "job-1",
							evidence_cards: [],
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
						{
							story_id: "story-2",
							story_key: "topic:failure-budget",
							headline: "Failure budgets became the comparison lens",
							topic_key: "failure-budget",
							topic_label: "Failure budget",
							source_count: 2,
							run_count: 3,
							matched_card_count: 3,
							platforms: ["rss"],
							claim_kinds: ["analysis"],
							source_urls: ["https://example.com/failure-budget"],
							latest_run_job_id: "job-3",
							evidence_cards: [],
							routes: {
								watchlist_trend: "/trends?watchlist_id=wl-1",
								briefing:
									"/briefings?watchlist_id=wl-1&story_id=story-2&via=secondary-story",
								ask: "/ask?watchlist_id=wl-1&story_id=story-2&topic_key=failure-budget&via=secondary-story",
								job_compare: "/jobs?job_id=job-3&via=secondary-story",
								job_bundle: "/api/v1/jobs/job-3/bundle",
								job_knowledge_cards: "/knowledge?job_id=job-3",
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
					story: null,
				},
			},
			selected_story: {
				story_id: "story-1",
				story_key: "topic:retry-policy",
				headline: "Retries moved from optional advice to default posture",
				topic_key: "retry-policy",
				topic_label: "Retry policy",
				source_count: 3,
				run_count: 4,
				matched_card_count: 6,
				platforms: ["youtube", "rss"],
				claim_kinds: ["recommendation"],
				source_urls: ["https://example.com/retry-policy"],
				latest_run_job_id: "job-1",
				evidence_cards: [
					{
						card_id: "card-1",
						job_id: "job-1",
						video_id: "video-1",
						platform: "youtube",
						video_title: "AI Weekly",
						source_url: "https://example.com/retry-policy",
						created_at: "2026-03-31T10:00:00Z",
						card_type: "claim",
						card_title: "Retry policy became explicit",
						card_body: "The workflow now treats retries as first-line safety.",
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
			retrieval: {
				query: "retry policy",
				top_k: 6,
				filters: {},
				items: [
					{
						job_id: "job-1",
						video_id: "video-1",
						platform: "rss",
						video_uid: "vid-1",
						source_url: "https://example.com/feed.xml",
						title: "AI Weekly",
						kind: "video_digest_v1",
						mode: "full",
						source: "knowledge_cards",
						snippet: "Agent workflows with retry and review loops.",
						score: 2.4,
					},
				],
			},
			citations: [
				{
					kind: "briefing_story",
					label: "Retry Policy",
					snippet: "Supported across 3 source families and 4 recent runs.",
					source_url: null,
					job_id: "job-3",
					route:
						"/briefings?watchlist_id=wl-1&story_id=story-1&via=briefing-story",
					route_label: "Open briefing story",
				},
			],
			fallback_reason: null,
			fallback_next_step: null,
			fallback_actions: [],
		});

		render(
			await AskPage({
				searchParams: {
					question: "retry policy",
					mode: "keyword",
					watchlist_id: "wl-1",
					story_id: "story-1",
					topic_key: "retry-policy",
				},
			}),
		);

		expect(mockGetAskAnswer).toHaveBeenCalledWith({
			question: "retry policy",
			mode: "keyword",
			top_k: 6,
			watchlist_id: "wl-1",
			story_id: "story-1",
			topic_key: "retry-policy",
		});
		expect(
			screen.getByRole("heading", { name: "Ask what you've saved" }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("heading", { name: "Best current answer" }),
		).toBeInTheDocument();
		expect(
			screen.getByRole("heading", { name: "This answer is about" }),
		).toBeInTheDocument();
		expect(
			screen.getAllByText(/Based on: Question match/i).length,
		).toBeGreaterThan(0);
		expect(
			screen.getByRole("heading", { name: "Try another angle" }),
		).toBeInTheDocument();
		expect(
			screen.getAllByText(
				"Retries moved from optional advice to default posture",
			).length,
		).toBeGreaterThan(0);
		expect(screen.getByText("Receipts later")).toBeInTheDocument();
		expect(
			screen
				.getAllByRole("link", { name: "Open selected briefing" })
				.map((element) => element.getAttribute("href")),
		).toContain(
			"/briefings?watchlist_id=wl-1&story_id=story-1&via=briefing-story",
		);
			const answerHeading = screen.getByRole("heading", {
				name: "Best current answer",
			});
			const refineLaterSummary = screen.getByText("Refine later");
			expect(
				answerHeading.compareDocumentPosition(refineLaterSummary) &
					Node.DOCUMENT_POSITION_FOLLOWING,
			).toBeTruthy();
		expect(
			screen.getByRole("link", {
				name: "Failure budgets became the comparison lens",
			}),
		).toHaveAttribute(
			"href",
			"/ask?watchlist_id=wl-1&story_id=story-2&topic_key=failure-budget&via=secondary-story&question=retry+policy&mode=keyword&top_k=6",
		);
	});

	it("keeps Ask honest when no briefing context is attached", async () => {
		mockGetAskAnswer.mockResolvedValue({
			question: "What changed this week?",
			mode: "keyword",
			top_k: 6,
			context: {
				watchlist_id: null,
				watchlist_name: null,
				story_id: null,
				selected_story_id: null,
				story_headline: null,
				topic_key: null,
				topic_label: null,
				selection_basis: "none",
				filters: {},
				briefing_available: false,
			},
			answer_state: "missing_context",
			answer_headline: null,
			answer_summary: null,
			answer_reason: null,
			answer_confidence: "limited",
			story_page: null,
			retrieval: {
				query: "What changed this week?",
				top_k: 6,
				filters: {},
				items: [],
			},
			citations: [],
			fallback_reason: null,
			fallback_next_step: null,
			fallback_actions: [],
		});

		render(
			await AskPage({
				searchParams: {
					question: "What changed this week?",
					mode: "keyword",
				},
			}),
		);

		expect(
			screen.getAllByText(/Pick a saved topic first/i).length,
		).toBeGreaterThan(0);
		expect(
			screen.getAllByText(/Without a watchlist briefing/i)
				.length,
		).toBeGreaterThan(0);
	});

	it("keeps Ask available when the answer route rejects", async () => {
		mockGetAskAnswer.mockRejectedValue(new Error("api down"));

		render(
			await AskPage({
				searchParams: {
					question: "retry policy",
					mode: "keyword",
					watchlist_id: "wl-1",
				},
			}),
		);

		expect(
			screen.getByRole("heading", { name: "Ask what you've saved" }),
		).toBeInTheDocument();
		expect(screen.getByText("Briefing unavailable")).toBeInTheDocument();
		expect(
			screen
				.getAllByRole("link", { name: "Open selected briefing" })
				.map((element) => element.getAttribute("href")),
		).toEqual(
			expect.arrayContaining(["/briefings?watchlist_id=wl-1", "/briefings"]),
		);
		expect(
			screen
				.getAllByRole("link", { name: "Open Search" })
				.map((element) => element.getAttribute("href")),
		).toEqual(
			expect.arrayContaining(["/search"]),
		);
	});

	it("renders MCP quickstart with real startup commands and tool examples", () => {
		render(<McpPage />);

		expect(
			screen.getByRole("heading", { name: "MCP Quickstart" }),
		).toBeInTheDocument();
		const commandBlock = document.querySelector("pre code");
		expect(commandBlock).not.toBeNull();
		expect(commandBlock).toHaveTextContent("./bin/sourceharbor help");
		expect(commandBlock).toHaveTextContent("./bin/sourceharbor mcp");
		expect(commandBlock).toHaveTextContent("./bin/dev-mcp");
		expect(
			screen.getByText("sourceharbor.retrieval.search"),
		).toBeInTheDocument();
		expect(screen.getByRole("link", { name: "Open Search" })).toHaveAttribute(
			"href",
			"/search",
		);
		expect(screen.getByRole("link", { name: "Open Ask" })).toHaveAttribute(
			"href",
			"/ask",
		);
	});
});
