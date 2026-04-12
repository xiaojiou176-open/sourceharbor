import type { Metadata } from "next";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
} from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import { formatDateTime } from "@/lib/format";
import { getLocaleMessages } from "@/lib/i18n/messages";
import {
	resolveSearchParams,
	type SearchParamsInput,
} from "@/lib/search-params";
import { buildProductMetadata } from "@/lib/seo";

const briefingsCopy = getLocaleMessages().briefingsPage;
const askCopy = getLocaleMessages().searchPage;

export const metadata: Metadata = buildProductMetadata({
	title: briefingsCopy.metadataTitle,
	description: briefingsCopy.metadataDescription,
	route: "briefings",
});

type BriefingsPageProps = {
	searchParams?: SearchParamsInput;
};

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

function matcherLabel(value: string): string {
	return value
		.split(/[_-]+/)
		.filter(Boolean)
		.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
		.join(" ");
}

function renderTokenList(items: string[], fallback: string): string {
	return items.length > 0 ? items.join(", ") : fallback;
}

function jobRoute(jobId: string | null | undefined): string | null {
	if (!jobId) {
		return null;
	}
	return `/jobs?job_id=${encodeURIComponent(jobId)}`;
}

function knowledgeRoute(jobId: string | null | undefined): string | null {
	if (!jobId) {
		return null;
	}
	return `/knowledge?job_id=${encodeURIComponent(jobId)}`;
}

export default async function BriefingsPage({
	searchParams,
}: BriefingsPageProps) {
	const copy = getLocaleMessages().briefingsPage;
	const { watchlist_id: watchlistId, story_id: storyId } =
		await resolveSearchParams(searchParams, [
			"watchlist_id",
			"story_id",
		] as const);
	const watchlists = await apiClient.listWatchlists().catch(() => []);
	const selectedWatchlist =
		watchlists.find((item) => item.id === watchlistId.trim()) ??
		watchlists[0] ??
		null;
	const briefingPage = selectedWatchlist
		? await apiClient
				.getWatchlistBriefingPage(selectedWatchlist.id, {
					story_id: storyId.trim() || undefined,
					limit_runs: 4,
					limit_cards: 12,
					limit_stories: 4,
					limit_evidence_per_story: 3,
				})
				.catch(() => null)
		: null;
	const briefing = briefingPage?.briefing ?? null;
	const selectedStory = briefingPage?.selected_story ?? null;
	const compareDrilldownHref = briefingPage?.compare_route ?? null;
	const briefingAskHref = briefingPage?.ask_route ?? "/ask";
	const selectionLabel = briefingPage
		? askCopy.askSelectionBasis[briefingPage.context.selection_basis]
		: null;

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">{copy.kicker}</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{copy.heroTitle}
				</h1>
				<p className="folo-page-subtitle">{copy.heroSubtitle}</p>
			</div>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<h2 className="text-xl font-semibold">{copy.truthTitle}</h2>
					<CardDescription>{copy.truthDescription}</CardDescription>
				</CardHeader>
				<CardContent className="space-y-3 text-sm text-muted-foreground">
					<p>{copy.truthPrimary}</p>
					<p>{copy.truthSecondary}</p>
					<div className="flex flex-wrap gap-3">
						<Button asChild variant="outline" size="sm">
							<Link href="/watchlists">{copy.openWatchlistsButton}</Link>
						</Button>
						<Button asChild variant="outline" size="sm">
							<Link href="/trends">{copy.openTrendsButton}</Link>
						</Button>
					</div>
				</CardContent>
			</Card>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<h2 className="text-xl font-semibold">{copy.chooseTitle}</h2>
					<CardDescription>{copy.chooseDescription}</CardDescription>
				</CardHeader>
				<CardContent className="flex flex-wrap gap-3">
					{watchlists.length === 0 ? (
						<p className="text-sm text-muted-foreground">{copy.empty}</p>
					) : (
						watchlists.map((item) => (
							<Button
								key={item.id}
								asChild
								variant={selectedWatchlist?.id === item.id ? "hero" : "outline"}
								size="sm"
							>
								<Link
									href={`/briefings?watchlist_id=${encodeURIComponent(item.id)}`}
								>
									{item.name}
								</Link>
							</Button>
						))
					)}
				</CardContent>
			</Card>

			{selectedWatchlist && briefing ? (
				<>
					<section className="grid gap-4 xl:grid-cols-[1.15fr_0.95fr]">
						<Card className="folo-surface border-border/70">
							<CardHeader>
								<h2 className="text-xl font-semibold">{copy.overviewTitle}</h2>
								<CardDescription>{copy.overviewDescription}</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4">
								<div className="space-y-2 rounded-xl border border-border/60 bg-muted/20 p-4">
									<p className="text-sm font-medium text-muted-foreground">
										{copy.currentWatchlistLabel}
									</p>
									<h3 className="text-2xl font-semibold">
										{selectedWatchlist.name}
									</h3>
									<p className="text-sm text-muted-foreground">
										{briefing.summary.overview}
									</p>
								</div>
								<div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
									<div className="rounded-lg border border-border/60 bg-muted/20 p-3">
										<p className="text-xs uppercase tracking-wide text-muted-foreground">
											{copy.sourcesLabel}
										</p>
										<p className="mt-1 text-2xl font-semibold">
											{briefing.summary.source_count}
										</p>
									</div>
									<div className="rounded-lg border border-border/60 bg-muted/20 p-3">
										<p className="text-xs uppercase tracking-wide text-muted-foreground">
											{copy.runsLabel}
										</p>
										<p className="mt-1 text-2xl font-semibold">
											{briefing.summary.run_count}
										</p>
									</div>
									<div className="rounded-lg border border-border/60 bg-muted/20 p-3">
										<p className="text-xs uppercase tracking-wide text-muted-foreground">
											{copy.storiesLabel}
										</p>
										<p className="mt-1 text-2xl font-semibold">
											{briefing.summary.story_count}
										</p>
									</div>
									<div className="rounded-lg border border-border/60 bg-muted/20 p-3">
										<p className="text-xs uppercase tracking-wide text-muted-foreground">
											{copy.matchedCardsLabel}
										</p>
										<p className="mt-1 text-2xl font-semibold">
											{briefing.summary.matched_cards}
										</p>
									</div>
								</div>
								<div className="grid gap-3 sm:grid-cols-2">
									<div className="rounded-lg border border-border/60 bg-background/70 p-3 text-sm text-muted-foreground">
										<p className="font-medium text-foreground">
											{selectedWatchlist.name}
										</p>
										<p className="mt-1">
											{copy.matcherLabel}:{" "}
											{matcherLabel(selectedWatchlist.matcher_type)} ={" "}
											<code>{selectedWatchlist.matcher_value}</code>
										</p>
										{selectedStory?.headline ||
										briefing.summary.primary_story_headline ? (
											<p className="mt-1">
												{copy.primaryStoryLabel}:{" "}
												{selectedStory?.headline ||
													briefing.summary.primary_story_headline}
											</p>
										) : null}
										{selectionLabel ? (
											<div className="mt-3">
												<Badge variant="outline">
													{askCopy.askSelectionBasisLabel}: {selectionLabel}
												</Badge>
											</div>
										) : null}
									</div>
									<div className="rounded-lg border border-border/60 bg-background/70 p-3 text-sm text-muted-foreground">
										<p className="font-medium text-foreground">
											{copy.signalsTitle}
										</p>
										{briefing.summary.signals.length === 0 ? (
											<p className="mt-2">{copy.noSignals}</p>
										) : null}
										<ul className="mt-2 space-y-2">
											{briefing.summary.signals.map((signal) => (
												<li key={signal.story_key}>
													<p className="font-medium text-foreground">
														{signal.headline}
													</p>
													<p>{signal.reason}</p>
												</li>
											))}
										</ul>
									</div>
								</div>
								<div className="flex flex-wrap items-start gap-3 rounded-lg border border-border/60 bg-background/70 p-3">
									<Button asChild size="sm">
										<Link href={briefingAskHref}>{copy.askBriefingButton}</Link>
									</Button>
									<Button asChild variant="outline" size="sm">
										<Link
											href={`/trends?watchlist_id=${encodeURIComponent(selectedWatchlist.id)}`}
										>
											{copy.openTrendButton}
										</Link>
									</Button>
									<Button asChild variant="outline" size="sm">
										<Link
											href={`/watchlists?watchlist_id=${encodeURIComponent(selectedWatchlist.id)}`}
										>
											{copy.editWatchlistButton}
										</Link>
									</Button>
								</div>
							</CardContent>
						</Card>

						<Card className="folo-surface border-border/70">
							<CardHeader>
								<h2 className="text-xl font-semibold">
									{copy.differencesTitle}
								</h2>
								<CardDescription>{copy.differencesDescription}</CardDescription>
							</CardHeader>
							<CardContent>
								<div className="grid gap-3 sm:grid-cols-2">
									<div className="rounded-lg border border-border/60 bg-muted/20 p-4 text-sm text-muted-foreground">
										<p className="font-medium text-foreground">
											{copy.addedTopicsLabel}
										</p>
										<p className="mt-2">
											{renderTokenList(
												briefing.differences.added_topics,
												copy.noneValue,
											)}
										</p>
									</div>
									<div className="rounded-lg border border-border/60 bg-muted/20 p-4 text-sm text-muted-foreground">
										<p className="font-medium text-foreground">
											{copy.removedTopicsLabel}
										</p>
										<p className="mt-2">
											{renderTokenList(
												briefing.differences.removed_topics,
												copy.noneValue,
											)}
										</p>
									</div>
									<div className="rounded-lg border border-border/60 bg-muted/20 p-4 text-sm text-muted-foreground">
										<p className="font-medium text-foreground">
											{copy.addedClaimKindsLabel}
										</p>
										<p className="mt-2">
											{renderTokenList(
												briefing.differences.added_claim_kinds,
												copy.noneValue,
											)}
										</p>
									</div>
									<div className="rounded-lg border border-border/60 bg-muted/20 p-4 text-sm text-muted-foreground">
										<p className="font-medium text-foreground">
											{copy.removedClaimKindsLabel}
										</p>
										<p className="mt-2">
											{renderTokenList(
												briefing.differences.removed_claim_kinds,
												copy.noneValue,
											)}
										</p>
									</div>
									<div className="rounded-lg border border-border/60 bg-muted/20 p-4 text-sm text-muted-foreground">
										<p className="font-medium text-foreground">
											{copy.newStoryKeysLabel}
										</p>
										<p className="mt-2">
											{renderTokenList(
												briefing.differences.new_story_keys,
												copy.noneValue,
											)}
										</p>
									</div>
									<div className="rounded-lg border border-border/60 bg-muted/20 p-4 text-sm text-muted-foreground">
										<p className="font-medium text-foreground">
											{copy.removedStoryKeysLabel}
										</p>
										<p className="mt-2">
											{renderTokenList(
												briefing.differences.removed_story_keys,
												copy.noneValue,
											)}
										</p>
									</div>
								</div>
								{briefing.differences.compare ? (
									<div className="mt-4 rounded-lg border border-border/60 bg-background/70 p-4 text-sm text-muted-foreground">
										<p className="font-medium text-foreground">
											{copy.compareTitle}
										</p>
										<p className="mt-2">
											{briefing.differences.compare.diff_excerpt ||
												copy.noCompareExcerpt}
										</p>
										<p className="mt-2">
											+{briefing.differences.compare.added_lines} / -
											{briefing.differences.compare.removed_lines}
										</p>
										{compareDrilldownHref ? (
											<div className="mt-3 flex flex-wrap gap-3">
												<Button asChild variant="outline" size="sm">
													<Link href={compareDrilldownHref}>
														{copy.openCompareButton}
													</Link>
												</Button>
											</div>
										) : null}
									</div>
								) : (
									<p className="text-sm text-muted-foreground">
										{copy.noCompareExcerpt}
									</p>
								)}
							</CardContent>
						</Card>
					</section>

					<Card className="folo-surface border-border/70">
						<CardHeader>
							<h2 className="text-xl font-semibold">{copy.evidenceTitle}</h2>
							<CardDescription>{copy.evidenceDescription}</CardDescription>
						</CardHeader>
						<CardContent>
							{briefing.evidence.stories.length === 0 &&
							briefing.evidence.featured_runs.length === 0 ? (
								<p className="text-sm text-muted-foreground">
									{copy.evidenceEmpty}
								</p>
							) : (
								<div className="space-y-6">
									{briefing.evidence.stories.length > 0 ? (
										<section className="space-y-4">
											<h3 className="text-lg font-semibold">
												{copy.storyEvidenceTitle}
											</h3>
											<div className="grid gap-4 lg:grid-cols-2">
												{briefing.evidence.stories.map((story) => {
													const storyJobHref = jobRoute(
														story.latest_run_job_id,
													);
													const storyKnowledgeHref = knowledgeRoute(
														story.latest_run_job_id,
													);
													return (
														<article
															key={story.story_id}
															className={
																story.story_id === selectedStory?.story_id
																	? "rounded-xl border border-primary/40 bg-primary/5 p-4"
																	: "rounded-xl border border-border/60 bg-muted/20 p-4"
															}
														>
															<div className="space-y-3">
																<div className="flex flex-wrap gap-2">
																	{story.platforms.map((platform) => (
																		<Badge key={platform} variant="outline">
																			{platformLabel(
																				platform,
																				copy.platformUnknown,
																			)}
																		</Badge>
																	))}
																</div>
																<div className="space-y-1">
																	<h4 className="text-lg font-semibold">
																		{story.headline}
																	</h4>
																	<p className="text-sm text-muted-foreground">
																		{copy.sourcesLabel}: {story.source_count} ·{" "}
																		{copy.runsLabel}: {story.run_count} ·{" "}
																		{copy.matchedCardsLabel}:{" "}
																		{story.matched_card_count}
																	</p>
																</div>
																<ul className="space-y-2 text-sm text-muted-foreground">
																	{story.evidence_cards.map((card) => (
																		<li
																			key={card.card_id}
																			className="rounded-lg border border-border/50 bg-background/70 p-3"
																		>
																			<p className="font-medium text-foreground">
																				{card.card_title ||
																					card.video_title ||
																					copy.untitledEvidenceLabel}
																			</p>
																			<p className="mt-1">
																				{card.card_body.trim() ||
																					copy.noExcerpt}
																			</p>
																			<p className="mt-1">
																				{card.source_section}
																			</p>
																		</li>
																	))}
																</ul>
																<div className="flex flex-wrap gap-3">
																	<Button asChild size="sm">
																		<Link href={story.routes.ask ?? "/ask"}>
																			{copy.askStoryButton}
																		</Link>
																	</Button>
																	{story.routes.briefing ? (
																		<Button asChild variant="outline" size="sm">
																			<Link href={story.routes.briefing}>
																				{copy.openBriefingButton}
																			</Link>
																		</Button>
																	) : null}
																	{storyJobHref ? (
																		<Button asChild variant="outline" size="sm">
																			<Link href={storyJobHref}>
																				{copy.openJobButton}
																			</Link>
																		</Button>
																	) : null}
																	{storyKnowledgeHref ? (
																		<Button asChild variant="outline" size="sm">
																			<Link href={storyKnowledgeHref}>
																				{copy.openKnowledgeButton}
																			</Link>
																		</Button>
																	) : null}
																	{story.source_urls[0] ? (
																		<Button asChild variant="ghost" size="sm">
																			<a
																				href={story.source_urls[0]}
																				target="_blank"
																				rel="noreferrer"
																			>
																				{copy.openSourceButton}
																			</a>
																		</Button>
																	) : null}
																</div>
															</div>
														</article>
													);
												})}
											</div>
										</section>
									) : null}

									{briefing.evidence.featured_runs.length > 0 ? (
										<section className="space-y-4">
											<h3 className="text-lg font-semibold">
												{copy.featuredRunsTitle}
											</h3>
											<div className="grid gap-4 lg:grid-cols-2">
												{briefing.evidence.featured_runs.map((run) => {
													const runJobHref = jobRoute(run.job_id);
													const runKnowledgeHref = knowledgeRoute(run.job_id);
													return (
														<article
															key={run.job_id}
															className="rounded-xl border border-border/60 bg-muted/20 p-4"
														>
															<div className="space-y-3">
																<div className="flex flex-wrap gap-2">
																	<Badge variant="outline">
																		{platformLabel(
																			run.platform,
																			copy.platformUnknown,
																		)}
																	</Badge>
																	<Badge variant="outline">
																		{run.matched_card_count}{" "}
																		{copy.matchedCardsLabel}
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
																	{runJobHref ? (
																		<Button asChild variant="outline" size="sm">
																			<Link href={runJobHref}>
																				{copy.openJobButton}
																			</Link>
																		</Button>
																	) : null}
																	{runKnowledgeHref ? (
																		<Button asChild variant="outline" size="sm">
																			<Link href={runKnowledgeHref}>
																				{copy.openKnowledgeButton}
																			</Link>
																		</Button>
																	) : null}
																	{run.source_url ? (
																		<Button asChild variant="ghost" size="sm">
																			<a
																				href={run.source_url}
																				target="_blank"
																				rel="noreferrer"
																			>
																				{copy.openSourceButton}
																			</a>
																		</Button>
																	) : null}
																</div>
															</div>
														</article>
													);
												})}
											</div>
										</section>
									) : null}
								</div>
							)}
						</CardContent>
					</Card>
				</>
			) : selectedWatchlist ? (
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<h2 className="text-xl font-semibold">{copy.unavailableTitle}</h2>
						<CardDescription>{copy.unavailableDescription}</CardDescription>
					</CardHeader>
				</Card>
			) : null}
		</div>
	);
}
