import type { Metadata } from "next";
import Link from "next/link";

import { FormInputField, FormSelectField } from "@/components/form-field";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
} from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import type {
	AskAnswerResponse,
	AskStorySelectionBasis,
	RetrievalHit,
	RetrievalSearchMode,
} from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";
import { getLocaleMessages } from "@/lib/i18n/messages";
import {
	resolveSearchParams,
	type SearchParamsInput,
} from "@/lib/search-params";
import { buildProductMetadata } from "@/lib/seo";
import { decorateAskRoute, preferRoute } from "@/lib/story-routes";

const askCopy = getLocaleMessages().searchPage;
const briefingsCopy = getLocaleMessages().briefingsPage;

export const metadata: Metadata = buildProductMetadata({
	title: askCopy.askTitle,
	description: askCopy.askSubtitle,
	route: "ask",
	keywords: [
		"briefing-aware Ask",
		"watchlist question front door",
		"answer change evidence workflow",
	],
});

type AskPageProps = {
	searchParams?: SearchParamsInput;
};

const MODE_OPTIONS: Array<{ value: RetrievalSearchMode; label: string }> = [
	{ value: "keyword", label: "Keyword" },
	{ value: "semantic", label: "Semantic (experimental)" },
	{ value: "hybrid", label: "Hybrid (experimental)" },
];

function compactId(value: string): string {
	return value.length <= 16 ? value : `${value.slice(0, 8)}…${value.slice(-6)}`;
}

function formatSourceLabel(source: string): string {
	if (source === "knowledge_cards") {
		return askCopy.knowledgeCardsSourceLabel;
	}
	return source
		.split(/[_-]+/)
		.filter(Boolean)
		.map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
		.join(" ");
}

function platformLabel(platform: string, fallback: string): string {
	const normalized = platform.trim().toLowerCase();
	if (normalized === "youtube") {
		return "YouTube";
	}
	if (normalized === "bilibili") {
		return "Bilibili";
	}
	if (normalized === "rss") {
		return "RSS";
	}
	return platform.trim() || fallback;
}

function renderTokenList(items: string[], fallback: string): string {
	return items.length > 0 ? items.join(", ") : fallback;
}

function buildAskHref(params: {
	question?: string;
	mode?: string;
	top_k?: string;
	watchlist_id?: string;
	story_id?: string;
	topic_key?: string;
}): string {
	const nextParams = new URLSearchParams();
	for (const [key, value] of Object.entries(params)) {
		const safeValue = value?.trim();
		if (safeValue) {
			nextParams.set(key, safeValue);
		}
	}
	const serialized = nextParams.toString();
	return serialized ? `/ask?${serialized}` : "/ask";
}

function buildContextSeed({
	question,
	fallback,
}: {
	question: string;
	fallback: string;
}): string {
	return question.trim() || fallback.trim();
}

function stateBadgeLabel(
	state: Awaited<ReturnType<typeof apiClient.getAskAnswer>>["answer_state"],
): string {
	switch (state) {
		case "briefing_grounded":
			return askCopy.askAnswerGroundedState;
		case "briefing_unavailable":
			return askCopy.askAnswerUnavailableState;
		case "no_confident_answer":
			return askCopy.askAnswerNoConfidentState;
		default:
			return askCopy.askAnswerNeedsContextState;
	}
}

function stateDescription({
	state,
	hasQuestion,
}: {
	state: Awaited<ReturnType<typeof apiClient.getAskAnswer>>["answer_state"];
	hasQuestion: boolean;
}): string {
	if (state === "briefing_grounded" && hasQuestion) {
		return askCopy.askAnswerGroundedDescription;
	}
	if (state === "briefing_grounded") {
		return askCopy.askAnswerContextOnlyDescription;
	}
	if (state === "briefing_unavailable") {
		return askCopy.askAnswerUnavailableDescription;
	}
	if (state === "no_confident_answer") {
		return askCopy.askAnswerNoConfidentDescription;
	}
	return askCopy.askContextMissingDescription;
}

function selectionBasisLabel(selectionBasis: AskStorySelectionBasis): string {
	return askCopy.askSelectionBasis[selectionBasis];
}

function EvidenceCard({ hit }: { hit: RetrievalHit }) {
	return (
		<Card className="folo-surface border-border/70">
			<CardHeader className="space-y-3">
				<div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
					<span>{hit.platform || "unknown"}</span>
					<span>·</span>
					<span>{formatSourceLabel(hit.source)}</span>
					<span>·</span>
					<span>Job {compactId(hit.job_id)}</span>
				</div>
				<div className="space-y-2">
					<h3 className="text-xl font-semibold">
						{hit.title?.trim() || askCopy.groundedEvidenceTitle}
					</h3>
					<CardDescription>{hit.snippet}</CardDescription>
				</div>
			</CardHeader>
			<CardContent className="flex flex-wrap gap-2">
				<Button asChild variant="secondary" size="sm">
					<Link href={`/jobs?job_id=${encodeURIComponent(hit.job_id)}`}>
						{askCopy.openJobTraceButton}
					</Link>
				</Button>
				<Button asChild variant="outline" size="sm">
					<Link href={`/feed?item=${encodeURIComponent(hit.job_id)}`}>
						{askCopy.openFeedEntryButton}
					</Link>
				</Button>
				<Link
					href={`/knowledge?job_id=${encodeURIComponent(hit.job_id)}`}
					className="inline-flex items-center text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
				>
					{askCopy.openKnowledgeCardsButton}
				</Link>
				{hit.source_url ? (
					<a
						href={hit.source_url}
						target="_blank"
						rel="noreferrer"
						className="inline-flex items-center text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
					>
						{askCopy.openSourceButton}
					</a>
				) : null}
			</CardContent>
		</Card>
	);
}

export default async function AskPage({ searchParams }: AskPageProps) {
	const {
		question,
		mode,
		top_k: topK,
		watchlist_id: watchlistId,
		story_id: storyId,
		topic_key: topicKey,
	} = await resolveSearchParams(searchParams, [
		"question",
		"mode",
		"top_k",
		"watchlist_id",
		"story_id",
		"topic_key",
	] as const);
	const safeQuestion = question.trim();
	const modeCandidate = mode.trim().toLowerCase();
	const safeMode: RetrievalSearchMode =
		modeCandidate === "semantic" || modeCandidate === "hybrid"
			? modeCandidate
			: "keyword";
	const parsedTopK = Number.parseInt(topK, 10);
	const safeTopK =
		Number.isFinite(parsedTopK) && parsedTopK > 0
			? Math.min(parsedTopK, 12)
			: 6;
	const safeWatchlistId = watchlistId.trim();
	const safeStoryId = storyId.trim();
	const safeTopicKey = topicKey.trim();
	const fallbackBriefingHref = safeWatchlistId
		? `/briefings?watchlist_id=${encodeURIComponent(safeWatchlistId)}`
		: "/briefings";
	const watchlists = await apiClient.listWatchlists().catch(() => []);
	const selectedWatchlist =
		watchlists.find((item) => item.id === safeWatchlistId) ?? null;

	let askPayload: AskAnswerResponse;
	try {
		askPayload = await apiClient.getAskAnswer({
			question: safeQuestion,
			mode: safeMode,
			top_k: safeTopK,
			watchlist_id: safeWatchlistId,
			story_id: safeStoryId,
			topic_key: safeTopicKey,
		});
	} catch {
		askPayload = {
			question: safeQuestion,
			mode: safeMode,
			top_k: safeTopK,
			context: {
				watchlist_id: safeWatchlistId || null,
				watchlist_name: selectedWatchlist?.name ?? null,
				story_id: safeStoryId || null,
				selected_story_id: safeStoryId || null,
				story_headline: null,
				topic_key: safeTopicKey || null,
				topic_label: selectedWatchlist?.name ?? null,
				selection_basis: "none",
				mode: safeMode,
				filters: {},
				briefing_available: false,
			},
			answer_state: "briefing_unavailable",
			answer_headline: null,
			answer_summary: null,
			answer_reason: null,
			answer_confidence: "limited",
			story_change_summary: null,
			story_page: null,
			retrieval: null,
			citations: [],
			fallback_reason: "Ask could not load the current answer lane right now.",
			fallback_next_step:
				"Open raw search or the latest briefing while the answer lane recovers.",
			fallback_actions: [
				{
					kind: "open_briefing",
					label: askCopy.askOpenBriefingButton,
					route: fallbackBriefingHref,
				},
				{
					kind: "open_search",
					label: askCopy.openRawSearchButton,
					route: "/search",
				},
			],
		};
	}

	const genericBriefingHref = askPayload.context.watchlist_id
		? `/briefings?watchlist_id=${encodeURIComponent(askPayload.context.watchlist_id)}`
		: "/briefings";
	const genericTrendHref = askPayload.context.watchlist_id
		? `/trends?watchlist_id=${encodeURIComponent(askPayload.context.watchlist_id)}`
		: "/trends";
	const clearContextHref = buildAskHref({
		question: safeQuestion,
		mode: safeMode,
		top_k: String(safeTopK),
	});
	const clearStoryHref = buildAskHref({
		question: safeQuestion,
		mode: safeMode,
		top_k: String(safeTopK),
		watchlist_id: askPayload.context.watchlist_id ?? undefined,
	});
	const contextOptions = [
		{ value: "", label: askCopy.askContextEmptyOption },
		...watchlists.map((item) => ({
			value: item.id,
			label: item.name,
		})),
	];
	const retrievalHits = askPayload.retrieval?.items ?? [];
	const storyPage = askPayload.story_page;
	const briefing = storyPage?.briefing ?? null;
	const briefingDifferences = briefing?.differences ?? null;
	const briefingCompare = briefingDifferences?.compare ?? null;
	const selectedStory = storyPage?.selected_story ?? null;
	const storyChoices = briefing?.evidence.stories ?? [];
	const featuredRuns = briefing?.evidence.featured_runs ?? [];
	const citations = askPayload.citations ?? [];
	const fallbackActions = askPayload.fallback_actions ?? [];
	const activeStoryId =
		selectedStory?.story_id ??
		askPayload.context.selected_story_id ??
		askPayload.context.story_id ??
		"";
	const briefingHref =
		preferRoute(selectedStory?.routes.briefing ?? null, genericBriefingHref) ??
		"/briefings";
	const trendHref =
		preferRoute(
			selectedStory?.routes.watchlist_trend ?? null,
			genericTrendHref,
		) ?? "/trends";
	const compareHref = preferRoute(
		selectedStory?.routes.job_compare ?? null,
		briefingCompare?.compare_route ?? null,
	);
	const contextReady = Boolean(askPayload.context.watchlist_id && briefing);
	const shouldShowChangesLane = Boolean(briefing);
	const shouldShowEvidenceLane = Boolean(
		citations.length > 0 ||
			retrievalHits.length > 0 ||
			selectedStory ||
			featuredRuns.length > 0 ||
			!safeQuestion,
	);
	const refinePrompt = contextReady
		? "Need to challenge this answer? Open changes or receipts only when you really need them."
		: "Pick one saved topic first. Without a watchlist briefing, Ask stays in raw evidence mode instead of pretending it knows more than it does.";
	const askFormSurface = (
		<Card className="folo-surface border-border/70">
			<CardHeader>
				<h2 className="text-xl font-semibold">{askCopy.askFormTitle}</h2>
				<CardDescription>{askCopy.askFormDescription}</CardDescription>
			</CardHeader>
			<CardContent className="space-y-6">
				<form method="GET" className="grid gap-4 xl:grid-cols-2">
					<FormInputField
						id="ask-question"
						name="question"
						label={askCopy.questionLabel}
						type="search"
						placeholder={askCopy.questionPlaceholder}
						defaultValue={safeQuestion}
						hint={askCopy.askHint}
					/>
					<FormSelectField
						name="watchlist_id"
						label={askCopy.askContextLabel}
						defaultValue={askPayload.context.watchlist_id ?? ""}
						options={contextOptions}
						hint={askCopy.askContextDescription}
					/>
					<FormSelectField
						name="mode"
						label={askCopy.groundingModeLabel}
						defaultValue={safeMode}
						options={MODE_OPTIONS.map((option) => ({
							...option,
							label:
								option.value === "keyword"
									? askCopy.modeOptions.keyword
									: option.value === "semantic"
										? askCopy.modeOptions.semantic
										: askCopy.modeOptions.hybrid,
						}))}
					/>
					<FormInputField
						id="ask-top-k"
						name="top_k"
						label={askCopy.topKLabel}
						type="number"
						min={1}
						max={12}
						defaultValue={String(safeTopK)}
					/>
					{askPayload.context.story_id ? (
						<input
							type="hidden"
							name="story_id"
							value={askPayload.context.story_id}
						/>
					) : null}
					{askPayload.context.topic_key ? (
						<input
							type="hidden"
							name="topic_key"
							value={askPayload.context.topic_key}
						/>
					) : null}
					<div className="flex items-end gap-3">
						<Button type="submit" variant="hero" size="sm">
							{askCopy.askButton}
						</Button>
						<Button asChild variant="ghost" size="sm">
							<Link href="/ask">{askCopy.clearButton}</Link>
						</Button>
					</div>
				</form>
				<div className="space-y-4 rounded-2xl border border-border/60 bg-background/55 p-4">
					<p className="text-sm leading-6 text-muted-foreground">
						{refinePrompt}
					</p>
					<div className="flex flex-wrap gap-3 text-sm text-muted-foreground">
						{contextReady ? (
							<>
								<Link
									href={briefingHref}
									className="underline underline-offset-4 hover:text-foreground"
								>
									{askCopy.askOpenBriefingButton}
								</Link>
								<Link
									href={trendHref}
									className="underline underline-offset-4 hover:text-foreground"
								>
									{briefingsCopy.openTrendButton}
								</Link>
								<Link
									href={clearContextHref}
									className="underline underline-offset-4 hover:text-foreground"
								>
									{askCopy.askClearContextButton}
								</Link>
							</>
						) : (
							<>
								<Link
									href="/briefings"
									className="underline underline-offset-4 hover:text-foreground"
								>
									{askCopy.askOpenBriefingButton}
								</Link>
								<Link
									href="/search"
									className="underline underline-offset-4 hover:text-foreground"
								>
									{askCopy.openRawSearchButton}
								</Link>
							</>
						)}
					</div>
					{!contextReady && watchlists.length > 0 ? (
						<div className="space-y-3 border-t border-border/50 pt-4">
							<p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
								Saved topics
							</p>
							<div className="flex flex-wrap gap-3">
								{watchlists.map((item) => (
									<Link
										key={item.id}
										href={buildAskHref({
											question: buildContextSeed({
												question: safeQuestion,
												fallback: item.matcher_value || item.name,
											}),
											mode: safeMode,
											top_k: String(safeTopK),
											watchlist_id: item.id,
										})}
										className="rounded-full border border-border/60 px-3 py-1 text-sm text-foreground transition hover:bg-muted/20"
									>
										{item.name}
									</Link>
								))}
							</div>
						</div>
					) : null}
				</div>
			</CardContent>
		</Card>
	);

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">{askCopy.askKicker}</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{askCopy.askTitle}
				</h1>
				<p className="folo-page-subtitle">{askCopy.askSubtitle}</p>
			</div>

			<div className="space-y-6">
				{!safeQuestion ? <section>{askFormSurface}</section> : null}

				<section className="space-y-4" aria-label={askCopy.askResultsAriaLabel}>
					<Card className="folo-surface border-border/70">
						<CardHeader>
							<div className="flex flex-wrap items-center gap-3">
								<h2 className="text-xl font-semibold">
									{askCopy.askAnswerTitle}
								</h2>
								<Badge variant="outline">
									{stateBadgeLabel(askPayload.answer_state)}
								</Badge>
							</div>
							<CardDescription>
								{stateDescription({
									state: askPayload.answer_state,
									hasQuestion: Boolean(safeQuestion),
								})}
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							{safeQuestion ? (
								<div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
									<Badge variant="outline">
										{askCopy.askSummaryQuestionPrefix}: {safeQuestion}
									</Badge>
									<Badge variant="outline">
										{askCopy.askSummaryHitsPrefix}: {retrievalHits.length}
									</Badge>
								</div>
							) : null}

							{selectedStory ? (
								<div className="rounded-lg border border-border/60 bg-muted/20 p-4">
									<div className="flex flex-wrap items-center gap-2">
										<h3 className="text-lg font-semibold">
											{askCopy.askStoryFocusTitle}
										</h3>
										<Badge variant="outline">
											{askCopy.askSelectionBasisLabel}:{" "}
											{selectionBasisLabel(askPayload.context.selection_basis)}
										</Badge>
										{selectedStory.topic_label ? (
											<Badge variant="outline">
												{selectedStory.topic_label}
											</Badge>
										) : null}
									</div>
									<p className="mt-2 text-sm text-muted-foreground">
										{askCopy.askStoryFocusDescription}
									</p>
									<div className="mt-3 flex flex-wrap gap-2 text-sm text-muted-foreground">
										<Badge variant="outline">
											{briefingsCopy.sourcesLabel}: {selectedStory.source_count}
										</Badge>
										<Badge variant="outline">
											{briefingsCopy.runsLabel}: {selectedStory.run_count}
										</Badge>
										<Badge variant="outline">
											{briefingsCopy.matchedCardsLabel}:{" "}
											{selectedStory.matched_card_count}
										</Badge>
									</div>
									<div className="mt-3 flex flex-wrap gap-3">
										{selectedStory.routes.briefing ? (
											<Button asChild variant="outline" size="sm">
												<Link href={selectedStory.routes.briefing}>
													{askCopy.askOpenBriefingButton}
												</Link>
											</Button>
										) : null}
										{selectedStory.routes.watchlist_trend ? (
											<Button asChild variant="outline" size="sm">
												<Link href={selectedStory.routes.watchlist_trend}>
													{briefingsCopy.openTrendButton}
												</Link>
											</Button>
										) : null}
										{selectedStory.routes.job_compare ? (
											<Button asChild variant="outline" size="sm">
												<Link href={selectedStory.routes.job_compare}>
													{briefingsCopy.openCompareButton}
												</Link>
											</Button>
										) : null}
										{selectedStory.routes.job_knowledge_cards ? (
											<Button asChild variant="outline" size="sm">
												<Link href={selectedStory.routes.job_knowledge_cards}>
													{briefingsCopy.openKnowledgeButton}
												</Link>
											</Button>
										) : null}
										{selectedStory.source_urls[0] ? (
											<Button asChild variant="ghost" size="sm">
												<a
													href={selectedStory.source_urls[0]}
													target="_blank"
													rel="noreferrer"
												>
													{briefingsCopy.openSourceButton}
												</a>
											</Button>
										) : null}
									</div>
									{storyChoices.length > 1 ? (
										<div className="mt-4 rounded-lg border border-border/60 bg-background/70 p-4">
											<div className="space-y-1">
												<h3 className="text-lg font-semibold">
													{askCopy.askStorySwitcherTitle}
												</h3>
												<p className="text-sm text-muted-foreground">
													{askCopy.askStorySwitcherDescription}
												</p>
											</div>
											<div className="mt-3 flex flex-wrap gap-2">
												{storyChoices.map((story) => (
													<Button
														key={story.story_id}
														asChild
														size="sm"
														variant={
															story.story_id === activeStoryId
																? "hero"
																: "outline"
														}
													>
														<Link
															href={
																decorateAskRoute(story.routes.ask, {
																	question:
																		safeQuestion ||
																		story.topic_label ||
																		story.headline,
																	mode: safeMode,
																	top_k: String(safeTopK),
																}) ??
																buildAskHref({
																	question: safeQuestion || undefined,
																	mode: safeMode,
																	top_k: String(safeTopK),
																	watchlist_id:
																		askPayload.context.watchlist_id ??
																		undefined,
																	story_id: story.story_id,
																	topic_key: story.topic_key ?? undefined,
																})
															}
														>
															{story.headline}
														</Link>
													</Button>
												))}
											</div>
											{askPayload.context.story_id ||
											askPayload.context.topic_key ? (
												<div className="mt-3 text-sm text-muted-foreground">
													<Link
														href={clearStoryHref}
														className="underline underline-offset-4 hover:text-foreground"
													>
														{askCopy.askClearStoryContextButton}
													</Link>
												</div>
											) : null}
										</div>
									) : null}
								</div>
							) : null}

							{askPayload.answer_state === "briefing_grounded" ? (
								<div className="space-y-3">
									<h3 className="text-2xl font-semibold">
										{askPayload.answer_headline ||
											askCopy.askAnswerFallbackTitle}
									</h3>
									{askPayload.answer_summary ? (
										<p className="text-sm text-muted-foreground">
											{askPayload.answer_summary}
										</p>
									) : null}
									{askPayload.answer_reason ? (
										<div className="rounded-lg border border-border/60 bg-muted/20 p-3 text-sm text-muted-foreground">
											<p className="font-medium text-foreground">
												{askCopy.askAnswerWhyLabel}
											</p>
											<p className="mt-2">{askPayload.answer_reason}</p>
										</div>
									) : null}
									<p className="text-sm text-muted-foreground">
										{safeQuestion
											? askCopy.askAnswerGroundedNote
											: askCopy.askAnswerContextOnlyNote}
									</p>
								</div>
							) : (
								<div className="space-y-3 rounded-lg border border-border/60 bg-muted/20 p-4 text-sm text-muted-foreground">
									<p className="font-medium text-foreground">
										{askPayload.answer_state === "no_confident_answer"
											? askCopy.askNoEvidenceTitle
											: askPayload.answer_state === "briefing_unavailable"
												? briefingsCopy.unavailableTitle
												: askCopy.askContextMissingTitle}
									</p>
									<p>
										{askPayload.answer_state === "no_confident_answer"
											? askCopy.askNoEvidenceDescription
											: askPayload.answer_state === "briefing_unavailable"
												? briefingsCopy.unavailableDescription
												: askCopy.askContextMissingDescription}
									</p>
									{askPayload.fallback_reason ? (
										<p>{askPayload.fallback_reason}</p>
									) : null}
									{askPayload.fallback_next_step ? (
										<p>{askPayload.fallback_next_step}</p>
									) : null}
									{fallbackActions.length > 0 ? (
										<div className="space-y-2">
											<p className="font-medium text-foreground">
												{askCopy.askFallbackActionsTitle}
											</p>
											<div className="flex flex-wrap gap-3">
												{fallbackActions.map((action) =>
													action.route ? (
														<Button
															key={`${action.kind}-${action.route}`}
															asChild
															variant="outline"
															size="sm"
														>
															<Link href={action.route}>{action.label}</Link>
														</Button>
													) : null,
												)}
											</div>
										</div>
									) : null}
								</div>
							)}
						</CardContent>
					</Card>

					{shouldShowChangesLane || shouldShowEvidenceLane ? (
						<details className="folo-surface rounded-[1.6rem] border border-border/70 bg-background/95 p-5 shadow-sm">
							<summary className="m-[-0.5rem] cursor-pointer list-none rounded-[1.2rem] p-2 transition-colors hover:bg-muted/20">
								<div className="space-y-2">
									<p className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">
										Receipts later
									</p>
									<p className="text-base font-semibold text-foreground">
										Open the change log, citations, and raw evidence only when
										you need to verify the answer.
									</p>
								</div>
							</summary>
							<div className="mt-5 space-y-6">
								{shouldShowChangesLane ? (
									<section className="space-y-4">
										<div className="space-y-1">
											<h2 className="text-xl font-semibold">
												{briefingsCopy.differencesTitle}
											</h2>
											<p className="text-sm text-muted-foreground">
												{briefingsCopy.differencesDescription}
											</p>
										</div>
										{askPayload.story_change_summary ? (
											<div className="rounded-lg border border-border/60 bg-background/70 p-4 text-sm text-muted-foreground">
												<p className="font-medium text-foreground">
													{askCopy.askAnswerWhyLabel}
												</p>
												<p className="mt-2">
													{askPayload.story_change_summary}
												</p>
											</div>
										) : null}
										<div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
											<div className="rounded-lg border border-border/60 bg-muted/20 p-3 text-sm text-muted-foreground">
												<p className="font-medium text-foreground">
													{briefingsCopy.addedTopicsLabel}
												</p>
												<p className="mt-2">
													{renderTokenList(
														briefingDifferences?.added_topics ?? [],
														briefingsCopy.noneValue,
													)}
												</p>
											</div>
											<div className="rounded-lg border border-border/60 bg-muted/20 p-3 text-sm text-muted-foreground">
												<p className="font-medium text-foreground">
													{briefingsCopy.removedTopicsLabel}
												</p>
												<p className="mt-2">
													{renderTokenList(
														briefingDifferences?.removed_topics ?? [],
														briefingsCopy.noneValue,
													)}
												</p>
											</div>
											<div className="rounded-lg border border-border/60 bg-muted/20 p-3 text-sm text-muted-foreground">
												<p className="font-medium text-foreground">
													{briefingsCopy.addedClaimKindsLabel}
												</p>
												<p className="mt-2">
													{renderTokenList(
														briefingDifferences?.added_claim_kinds ?? [],
														briefingsCopy.noneValue,
													)}
												</p>
											</div>
											<div className="rounded-lg border border-border/60 bg-muted/20 p-3 text-sm text-muted-foreground">
												<p className="font-medium text-foreground">
													{briefingsCopy.removedClaimKindsLabel}
												</p>
												<p className="mt-2">
													{renderTokenList(
														briefingDifferences?.removed_claim_kinds ?? [],
														briefingsCopy.noneValue,
													)}
												</p>
											</div>
											<div className="rounded-lg border border-border/60 bg-muted/20 p-3 text-sm text-muted-foreground">
												<p className="font-medium text-foreground">
													{briefingsCopy.newStoryKeysLabel}
												</p>
												<p className="mt-2">
													{renderTokenList(
														briefingDifferences?.new_story_keys ?? [],
														briefingsCopy.noneValue,
													)}
												</p>
											</div>
											<div className="rounded-lg border border-border/60 bg-muted/20 p-3 text-sm text-muted-foreground">
												<p className="font-medium text-foreground">
													{briefingsCopy.removedStoryKeysLabel}
												</p>
												<p className="mt-2">
													{renderTokenList(
														briefingDifferences?.removed_story_keys ?? [],
														briefingsCopy.noneValue,
													)}
												</p>
											</div>
										</div>
										<div className="rounded-lg border border-border/60 bg-background/70 p-4 text-sm text-muted-foreground">
											<p className="font-medium text-foreground">
												{briefingsCopy.compareTitle}
											</p>
											<p className="mt-2">
												{briefingCompare?.diff_excerpt ||
													briefingsCopy.noCompareExcerpt}
											</p>
											{briefingCompare ? (
												<p className="mt-2">
													+{briefingCompare.added_lines} / -
													{briefingCompare.removed_lines}
												</p>
											) : null}
										</div>
										<div className="flex flex-wrap gap-3">
											<Button asChild variant="outline" size="sm">
												<Link href={briefingHref}>
													{askCopy.askOpenBriefingButton}
												</Link>
											</Button>
											{compareHref ? (
												<Button asChild variant="outline" size="sm">
													<Link href={compareHref}>
														{briefingsCopy.openCompareButton}
													</Link>
												</Button>
											) : null}
										</div>
									</section>
								) : null}

								{shouldShowEvidenceLane ? (
									<section className="space-y-6">
										<div className="space-y-1">
											<h2 className="text-xl font-semibold">
												{briefingsCopy.evidenceTitle}
											</h2>
											<p className="text-sm text-muted-foreground">
												{briefingsCopy.evidenceDescription}
											</p>
										</div>
										{citations.length > 0 ? (
											<section className="space-y-4">
												<div className="space-y-1">
													<h3 className="text-lg font-semibold">
														{askCopy.askCitationsTitle}
													</h3>
													<p className="text-sm text-muted-foreground">
														{askCopy.askCitationsDescription}
													</p>
												</div>
												<div className="grid gap-4 xl:grid-cols-2">
													{citations.map((citation, index) => (
														<article
															key={`${citation.kind}-${citation.label}-${index}`}
															className="rounded-xl border border-border/60 bg-muted/20 p-4"
														>
															<div className="space-y-3">
																<div className="flex flex-wrap gap-2">
																	{citation.job_id ? (
																		<Badge variant="outline">
																			Job {compactId(citation.job_id)}
																		</Badge>
																	) : null}
																	<Badge variant="outline">
																		{formatSourceLabel(citation.kind)}
																	</Badge>
																</div>
																<div className="space-y-1">
																	<h4 className="text-lg font-semibold">
																		{citation.label}
																	</h4>
																	<p className="text-sm text-muted-foreground">
																		{citation.snippet}
																	</p>
																</div>
																<div className="flex flex-wrap gap-3">
																	{citation.route ? (
																		<Button asChild variant="outline" size="sm">
																			<Link href={citation.route}>
																				{citation.route_label ??
																					askCopy.askOpenCitationRouteButton}
																			</Link>
																		</Button>
																	) : null}
																	{citation.source_url ? (
																		<Button asChild variant="ghost" size="sm">
																			<a
																				href={citation.source_url}
																				target="_blank"
																				rel="noreferrer"
																			>
																				{askCopy.openSourceButton}
																			</a>
																		</Button>
																	) : null}
																</div>
															</div>
														</article>
													))}
												</div>
											</section>
										) : null}

										{safeQuestion ? (
											<section className="space-y-4">
												<div className="space-y-1">
													<h3 className="text-lg font-semibold">
														{askCopy.askQuestionEvidenceTitle}
													</h3>
													<p className="text-sm text-muted-foreground">
														{askCopy.askQuestionEvidenceDescription}
													</p>
												</div>
												{retrievalHits.length > 0 ? (
													retrievalHits.map((hit) => (
														<EvidenceCard
															key={`${hit.job_id}-${hit.source}-${hit.snippet}`}
															hit={hit}
														/>
													))
												) : (
													<p className="text-sm text-muted-foreground">
														{askCopy.askNoEvidenceDescription}
													</p>
												)}
											</section>
										) : null}

										{selectedStory ? (
											<section className="space-y-4">
												<div className="space-y-1">
													<h3 className="text-lg font-semibold">
														{briefingsCopy.storyEvidenceTitle}
													</h3>
													<p className="text-sm text-muted-foreground">
														{selectedStory.headline}
													</p>
												</div>
												<div className="grid gap-4 xl:grid-cols-2">
													{selectedStory.evidence_cards.map((card) => (
														<article
															key={card.card_id}
															className="rounded-xl border border-border/60 bg-muted/20 p-4"
														>
															<div className="space-y-3">
																<div className="flex flex-wrap gap-2">
																	<Badge variant="outline">
																		{platformLabel(
																			card.platform,
																			briefingsCopy.platformUnknown,
																		)}
																	</Badge>
																	{card.topic_label ? (
																		<Badge variant="outline">
																			{card.topic_label}
																		</Badge>
																	) : null}
																</div>
																<div className="space-y-1">
																	<h4 className="text-lg font-semibold">
																		{card.card_title ||
																			card.video_title ||
																			briefingsCopy.untitledEvidenceLabel}
																	</h4>
																	<p className="text-sm text-muted-foreground">
																		{card.card_body.trim() ||
																			briefingsCopy.noExcerpt}
																	</p>
																</div>
																<div className="flex flex-wrap gap-3">
																	<Button asChild variant="outline" size="sm">
																		<Link
																			href={`/jobs?job_id=${encodeURIComponent(card.job_id)}`}
																		>
																			{briefingsCopy.openJobButton}
																		</Link>
																	</Button>
																	<Button asChild variant="outline" size="sm">
																		<Link
																			href={`/knowledge?job_id=${encodeURIComponent(card.job_id)}`}
																		>
																			{briefingsCopy.openKnowledgeButton}
																		</Link>
																	</Button>
																	{card.source_url ? (
																		<Button asChild variant="ghost" size="sm">
																			<a
																				href={card.source_url}
																				target="_blank"
																				rel="noreferrer"
																			>
																				{briefingsCopy.openSourceButton}
																			</a>
																		</Button>
																	) : null}
																</div>
															</div>
														</article>
													))}
												</div>
											</section>
										) : null}

										{featuredRuns.length > 0 ? (
											<section className="space-y-4">
												<div className="space-y-1">
													<h3 className="text-lg font-semibold">
														{briefingsCopy.featuredRunsTitle}
													</h3>
													<p className="text-sm text-muted-foreground">
														{askCopy.askFeaturedRunsDescription}
													</p>
												</div>
												<div className="grid gap-4 xl:grid-cols-2">
													{featuredRuns.map((run) => (
														<article
															key={run.job_id}
															className="rounded-xl border border-border/60 bg-muted/20 p-4"
														>
															<div className="space-y-3">
																<div className="flex flex-wrap gap-2">
																	<Badge variant="outline">
																		{platformLabel(
																			run.platform,
																			briefingsCopy.platformUnknown,
																		)}
																	</Badge>
																	<Badge variant="outline">
																		{run.matched_card_count}{" "}
																		{briefingsCopy.matchedCardsLabel}
																	</Badge>
																</div>
																<div className="space-y-1">
																	<h4 className="text-lg font-semibold">
																		{run.title}
																	</h4>
																	<p className="text-sm text-muted-foreground">
																		{formatDateTime(run.created_at)}
																	</p>
																</div>
																<div className="flex flex-wrap gap-3">
																	<Button asChild variant="outline" size="sm">
																		<Link
																			href={`/jobs?job_id=${encodeURIComponent(run.job_id)}`}
																		>
																			{briefingsCopy.openJobButton}
																		</Link>
																	</Button>
																	<Button asChild variant="outline" size="sm">
																		<Link
																			href={`/knowledge?job_id=${encodeURIComponent(run.job_id)}`}
																		>
																			{briefingsCopy.openKnowledgeButton}
																		</Link>
																	</Button>
																	{run.source_url ? (
																		<Button asChild variant="ghost" size="sm">
																			<a
																				href={run.source_url}
																				target="_blank"
																				rel="noreferrer"
																			>
																				{briefingsCopy.openSourceButton}
																			</a>
																		</Button>
																	) : null}
																</div>
															</div>
														</article>
													))}
												</div>
											</section>
										) : null}

										{!safeQuestion &&
										!selectedStory &&
										featuredRuns.length === 0 ? (
											<p className="text-sm text-muted-foreground">
												{askCopy.askExpectationDescription}
											</p>
										) : null}
									</section>
								) : null}
							</div>
						</details>
					) : null}
				</section>
				{safeQuestion ? (
					<details className="folo-surface rounded-[1.6rem] border border-border/70 bg-background/95 p-5 shadow-sm">
						<summary className="m-[-0.5rem] cursor-pointer list-none rounded-[1.2rem] p-2 transition-colors hover:bg-muted/20">
							<div className="space-y-2">
								<p className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">
									Refine later
								</p>
								<p className="text-base font-semibold text-foreground">
									Open the question controls only if the first answer is not
									enough
								</p>
							</div>
						</summary>
						<div className="mt-5">{askFormSurface}</div>
					</details>
				) : null}
			</div>
		</div>
	);
}
