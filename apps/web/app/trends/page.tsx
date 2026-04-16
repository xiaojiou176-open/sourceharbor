import type { Metadata } from "next";
import Link from "next/link";
import { SignalStrip } from "@/components/signal-strip";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";
import type {
	WatchlistMergedStory,
	WatchlistTrendResponse,
} from "@/lib/api/types";
import { formatDateTime } from "@/lib/format";
import { getLocaleMessages } from "@/lib/i18n/messages";
import {
	resolveSearchParams,
	type SearchParamsInput,
} from "@/lib/search-params";
import { buildProductMetadata } from "@/lib/seo";

const trendsCopy = getLocaleMessages().trendsPage;

export const metadata: Metadata = buildProductMetadata({
	title: trendsCopy.metadataTitle,
	description: trendsCopy.metadataDescription,
	route: "trends",
});

type TrendsPageProps = {
	searchParams?: SearchParamsInput;
};

type DerivedMergedStoryEvidence = {
	jobId: string;
	platform: string;
	title: string;
	sourceUrl: string | null;
	createdAt: string;
	excerpt: string | null;
};

type DerivedMergedStory = {
	id: string;
	label: string;
	summary: string | null;
	sourceCount: number;
	runCount: number;
	latestCreatedAt: string | null;
	platforms: string[];
	claimKinds: string[];
	topicKey: string | null;
	latestJobId: string | null;
	evidence: DerivedMergedStoryEvidence[];
};

type DerivedSourceCoverage = {
	platform: string;
	run_count: number;
	card_count: number;
	latest_created_at: string | null;
};

function platformLabel(platform: string): string {
	if (platform === "youtube") {
		return "YouTube";
	}
	if (platform === "bilibili") {
		return "Bilibili";
	}
	if (platform === "rss") {
		return "RSS";
	}
	return platform;
}

function humanizeClaimKind(value: string): string {
	return value
		.split(/[_-]/)
		.filter((part) => part.length > 0)
		.map((part) => part[0].toUpperCase() + part.slice(1))
		.join(" ");
}

function deriveMergedStories(
	trend: WatchlistTrendResponse,
): DerivedMergedStory[] {
	if (Array.isArray(trend.merged_stories) && trend.merged_stories.length > 0) {
		return trend.merged_stories
			.map((story: WatchlistMergedStory) => ({
				id: story.id,
				label: story.headline || story.topic_label || story.story_key,
				summary: null,
				sourceCount: story.source_urls.length,
				runCount: story.run_ids.length,
				latestCreatedAt: story.latest_created_at,
				platforms: story.platforms,
				claimKinds: story.claim_kinds,
				topicKey: story.topic_key,
				latestJobId:
					story.cards[0]?.job_id?.trim() || story.run_ids[0]?.trim() || null,
				evidence: story.cards.slice(0, 3).map((item) => ({
					jobId: item.job_id,
					platform: item.platform,
					title:
						item.video_title?.trim() ||
						item.card_title?.trim() ||
						`Job ${item.job_id}`,
					sourceUrl: item.source_url,
					createdAt: item.created_at,
					excerpt: item.card_body,
				})),
			}))
			.sort((left, right) => {
				const timeDelta =
					new Date(right.latestCreatedAt ?? 0).getTime() -
					new Date(left.latestCreatedAt ?? 0).getTime();
				if (timeDelta !== 0) {
					return timeDelta;
				}
				if (right.sourceCount !== left.sourceCount) {
					return right.sourceCount - left.sourceCount;
				}
				return right.runCount - left.runCount;
			});
	}

	const groups = new Map<
		string,
		{
			id: string;
			label: string;
			summary: string | null;
			sourceKeys: Set<string>;
			runIds: Set<string>;
			platforms: Set<string>;
			claimKinds: Set<string>;
			topicKey: string | null;
			latestJobId: string | null;
			latestCreatedAt: string | null;
			evidence: Map<string, DerivedMergedStoryEvidence>;
		}
	>();

	for (const run of trend.timeline) {
		const register = (
			groupId: string,
			label: string,
			excerpt: string | null,
		) => {
			const sourceKey = `${run.platform}:${run.source_url ?? run.video_id ?? run.title}`;
			const existing = groups.get(groupId) ?? {
				id: groupId,
				label,
				summary: null,
				sourceKeys: new Set<string>(),
				runIds: new Set<string>(),
				platforms: new Set<string>(),
				claimKinds: new Set<string>(),
				topicKey: null as string | null,
				latestJobId: null as string | null,
				latestCreatedAt: null as string | null,
				evidence: new Map<string, DerivedMergedStoryEvidence>(),
			};
			existing.label = label;
			existing.sourceKeys.add(sourceKey);
			existing.runIds.add(run.job_id);
			existing.platforms.add(run.platform);
			if (!existing.latestJobId) {
				existing.latestJobId = run.job_id;
			}
			if (
				!existing.latestCreatedAt ||
				new Date(run.created_at).getTime() >
					new Date(existing.latestCreatedAt).getTime()
			) {
				existing.latestCreatedAt = run.created_at;
			}
			if (!existing.evidence.has(run.job_id)) {
				existing.evidence.set(run.job_id, {
					jobId: run.job_id,
					platform: run.platform,
					title: run.title,
					sourceUrl: run.source_url,
					createdAt: run.created_at,
					excerpt,
				});
			}
			groups.set(groupId, existing);
		};

		let matchedStructuredCard = false;
		for (const card of run.cards) {
			if (card.topic_key || card.topic_label) {
				matchedStructuredCard = true;
				const rawTopic = card.topic_key ?? card.topic_label ?? "topic";
				const label = card.topic_label ?? card.topic_key ?? "Topic";
				register(`topic:${rawTopic}`, label, card.card_body);
				const group = groups.get(`topic:${rawTopic}`);
				if (group && card.topic_key) {
					group.topicKey = card.topic_key;
				}
			}
			if (card.claim_kind) {
				matchedStructuredCard = true;
				register(
					`claim:${card.claim_kind}`,
					`${humanizeClaimKind(card.claim_kind)} claims`,
					card.card_body,
				);
				const claimGroup = groups.get(`claim:${card.claim_kind}`);
				if (claimGroup) {
					claimGroup.claimKinds.add(card.claim_kind);
				}
			}
		}

		if (!matchedStructuredCard) {
			for (const topic of run.topics) {
				register(`topic:${topic}`, topic, null);
			}
			for (const claimKind of run.claim_kinds) {
				register(
					`claim:${claimKind}`,
					`${humanizeClaimKind(claimKind)} claims`,
					null,
				);
			}
		}
	}

	return [...groups.values()]
		.map((group) => ({
			id: group.id,
			label: group.label,
			summary: null,
			sourceCount: group.sourceKeys.size,
			runCount: group.runIds.size,
			latestCreatedAt: group.latestCreatedAt,
			platforms: [...group.platforms],
			claimKinds: [...group.claimKinds],
			topicKey: group.topicKey,
			latestJobId: group.latestJobId,
			evidence: [...group.evidence.values()]
				.sort(
					(left, right) =>
						new Date(right.createdAt).getTime() -
						new Date(left.createdAt).getTime(),
				)
				.slice(0, 3),
		}))
		.sort((left, right) => {
			if (right.sourceCount !== left.sourceCount) {
				return right.sourceCount - left.sourceCount;
			}
			if (right.runCount !== left.runCount) {
				return right.runCount - left.runCount;
			}
			return (
				new Date(right.latestCreatedAt ?? 0).getTime() -
				new Date(left.latestCreatedAt ?? 0).getTime()
			);
		});
}

function buildStorySummary(story: DerivedMergedStory): string {
	const claims =
		story.claimKinds.length > 0
			? story.claimKinds.map(humanizeClaimKind).join(", ")
			: "mixed evidence";
	return `Consensus is strongest across ${story.sourceCount} source families and ${story.runCount} runs. Claim shape: ${claims}.`;
}

function buildAskRoute({
	watchlistId,
	storyId,
	topicKey,
	label,
}: {
	watchlistId: string;
	storyId: string;
	topicKey: string | null;
	label: string;
}): string {
	const params = new URLSearchParams({
		watchlist_id: watchlistId,
		story_id: storyId,
	});
	if (topicKey) {
		params.set("topic_key", topicKey);
	}
	params.set("question", label);
	return `/ask?${params.toString()}`;
}

function deriveSourceCoverage(
	trend: WatchlistTrendResponse,
): DerivedSourceCoverage[] {
	const sourceCoverage = (
		trend as WatchlistTrendResponse & {
			source_coverage?: DerivedSourceCoverage[];
		}
	).source_coverage;
	if (Array.isArray(sourceCoverage) && sourceCoverage.length > 0) {
		return sourceCoverage;
	}
	const coverage = new Map<
		string,
		{
			platform: string;
			runIds: Set<string>;
			cardCount: number;
			latestCreatedAt: string | null;
		}
	>();

	for (const run of trend.timeline) {
		const existing = coverage.get(run.platform) ?? {
			platform: run.platform,
			runIds: new Set<string>(),
			cardCount: 0,
			latestCreatedAt: null as string | null,
		};
		existing.runIds.add(run.job_id);
		existing.cardCount += run.matched_card_count;
		if (
			!existing.latestCreatedAt ||
			new Date(run.created_at).getTime() >
				new Date(existing.latestCreatedAt).getTime()
		) {
			existing.latestCreatedAt = run.created_at;
		}
		coverage.set(run.platform, existing);
	}

	return [...coverage.values()]
		.map((item) => ({
			platform: item.platform,
			run_count: item.runIds.size,
			card_count: item.cardCount,
			latest_created_at: item.latestCreatedAt,
		}))
		.sort((left, right) => {
			if (right.run_count !== left.run_count) {
				return right.run_count - left.run_count;
			}
			return right.card_count - left.card_count;
		});
}

export default async function TrendsPage({ searchParams }: TrendsPageProps) {
	const messages = getLocaleMessages();
	const copy = messages.trendsPage;
	const watchlistsCopy = messages.watchlistsPage;
	const { watchlist_id: watchlistId } = await resolveSearchParams(
		searchParams,
		["watchlist_id"] as const,
	);
	const watchlists = await apiClient.listWatchlists().catch(() => []);
	const selectedWatchlist =
		watchlists.find((item) => item.id === watchlistId.trim()) ??
		watchlists[0] ??
		null;
	const [trend, briefing] = selectedWatchlist
		? await Promise.all([
				apiClient
					.getWatchlistTrend(selectedWatchlist.id, {
						limit_runs: 4,
						limit_cards: 16,
					})
					.catch(() => null),
				apiClient
					.getWatchlistBriefing(selectedWatchlist.id, {
						limit_runs: 4,
						limit_cards: 16,
						limit_stories: 4,
						limit_evidence_per_story: 2,
					})
					.catch(() => null),
			])
		: [null, null];
	const mergedStories = trend ? deriveMergedStories(trend) : [];
	const sourceCoverage = trend ? deriveSourceCoverage(trend) : [];
	const leadStory =
		briefing?.evidence.stories.find(
			(item) => item.story_id === briefing.evidence.suggested_story_id,
		) ??
		briefing?.evidence.stories[0] ??
		null;
	const leadBundle = leadStory?.latest_run_job_id
		? await apiClient
				.getJobEvidenceBundle(leadStory.latest_run_job_id)
				.catch(() => null)
		: null;
	const leadBundleStepCount =
		leadBundle && typeof leadBundle.trace_summary.step_count === "number"
			? leadBundle.trace_summary.step_count
			: "unknown";
	const maxTimelineCards = Math.max(
		1,
		...(trend?.timeline.map((run) => run.matched_card_count) ?? [1]),
	);
	const maxSourceCards = Math.max(
		1,
		...(sourceCoverage.map((item) => item.card_count) ?? [1]),
	);
	const movementSnapshotItems = (trend?.timeline ?? [])
		.slice(0, 4)
		.map((run) => ({
			label: platformLabel(run.platform),
			value: run.matched_card_count,
			max: maxTimelineCards,
			valueLabel: String(run.matched_card_count),
			detail: formatDateTime(run.created_at),
			tone:
				run.added_topics.length > 0
					? ("success" as const)
					: ("primary" as const),
		}));
	const leadStoryJobId = leadStory?.latest_run_job_id ?? null;

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">{copy.kicker}</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{copy.heroTitle}
				</h1>
				<p className="folo-page-subtitle">{copy.heroSubtitle}</p>
			</div>

			{watchlists.length === 0 || watchlists.length > 1 ? (
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<CardTitle>{copy.chooseTitle}</CardTitle>
						<CardDescription>
							{watchlists.length === 0
								? copy.empty
								: "Pick the topic you want to keep reading. Everything else stays secondary."}
						</CardDescription>
					</CardHeader>
					<CardContent className="flex flex-wrap gap-3">
						{watchlists.length === 0 ? (
							<>
								<Button asChild variant="hero" size="sm">
									<Link href="/watchlists#create-watchlist">
										{watchlistsCopy.emptyReadyButton}
									</Link>
								</Button>
								<Button asChild variant="outline" size="sm">
									<Link href="/playground">
										{watchlistsCopy.emptyReadySecondaryButton}
									</Link>
								</Button>
							</>
						) : (
							watchlists.map((item) => (
								<Button
									key={item.id}
									asChild
									variant={
										selectedWatchlist?.id === item.id ? "hero" : "outline"
									}
									size="sm"
								>
									<Link
										href={`/trends?watchlist_id=${encodeURIComponent(item.id)}`}
									>
										{item.name}
									</Link>
								</Button>
							))
						)}
					</CardContent>
				</Card>
			) : null}

			{selectedWatchlist && trend ? (
				<>
					<section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
						<Card className="folo-surface border-border/70">
							<CardHeader>
								<CardTitle>Follow the story</CardTitle>
								<CardDescription>
									Start with the strongest repeated story first. Details stay
									behind it.
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-4">
								{leadStory ? (
									<>
										<div className="space-y-2 rounded-lg border border-border/60 bg-muted/20 p-4">
											<p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted-foreground">
												Current cross-source focus
											</p>
											<h2 className="text-xl font-semibold">
												{leadStory.headline}
											</h2>
											<p className="text-sm text-muted-foreground">
												Supported across {leadStory.source_count} source
												families, {leadStory.run_count} runs, and{" "}
												{leadStory.matched_card_count} matched cards.
											</p>
											<div className="flex flex-wrap gap-2">
												{leadStory.platforms.map((platform) => (
													<Badge key={platform} variant="outline">
														{platformLabel(platform)}
													</Badge>
												))}
												{leadStory.claim_kinds.map((claimKind) => (
													<Badge key={claimKind} variant="outline">
														{humanizeClaimKind(claimKind)}
													</Badge>
												))}
											</div>
										</div>

										<p className="text-sm leading-7 text-muted-foreground">
											{briefing?.summary.overview ??
												"Use the selected watchlist to see where repeated themes converge."}
										</p>
										{briefing?.differences.compare?.diff_excerpt ? (
											<p className="text-sm text-muted-foreground">
												Latest shift:{" "}
												{briefing.differences.compare.diff_excerpt}
											</p>
										) : null}

										{movementSnapshotItems.length > 0 ? (
											<SignalStrip
												title="What changed lately"
												description="See the newest movement first, then open the full timeline if you want more detail."
												items={movementSnapshotItems}
											/>
										) : null}

										<div className="flex flex-wrap gap-3">
											<Button asChild variant="hero" size="sm">
												<Link
													href={`/briefings?watchlist_id=${encodeURIComponent(selectedWatchlist.id)}&story_id=${encodeURIComponent(leadStory.story_id)}`}
												>
													Open brief
												</Link>
											</Button>
											<Button asChild variant="outline" size="sm">
												<Link
													href={buildAskRoute({
														watchlistId: selectedWatchlist.id,
														storyId: leadStory.story_id,
														topicKey: leadStory.topic_key,
														label: leadStory.headline,
													})}
												>
													Ask about this story
												</Link>
											</Button>
										</div>
									</>
								) : (
									<div className="rounded-lg border border-border/60 bg-muted/20 p-4 text-sm text-muted-foreground">
										This watchlist does not expose a selected story yet. Start
										with the recent evidence timeline below, then move into a
										briefing once repeated evidence accumulates.
									</div>
								)}
							</CardContent>
						</Card>

						<details className="folo-surface rounded-2xl border border-border/70 bg-background/95 p-5">
							<summary className="cursor-pointer list-none font-semibold text-foreground">
								Open receipts and examples later
							</summary>
							<div className="mt-4 space-y-4 text-sm text-muted-foreground">
								<p>
									Use this only when you want the raw bundle, notes, or sample
									explanation after the main story already makes sense.
								</p>
								{leadBundle ? (
									<p>
										Trace steps: {leadBundleStepCount} · Knowledge cards:{" "}
										{leadBundle.knowledge_cards.length}
									</p>
								) : null}
								{leadBundle ? <p>{leadBundle.proof_boundary}</p> : null}
								<div className="flex flex-wrap gap-3">
									{leadStoryJobId ? (
										<Button asChild variant="outline" size="sm">
											<Link
												href={`/api/v1/jobs/${encodeURIComponent(leadStoryJobId)}/bundle`}
											>
												Open bundle
											</Link>
										</Button>
									) : null}
									{leadStoryJobId ? (
										<Button asChild variant="outline" size="sm">
											<Link
												href={`/knowledge?job_id=${encodeURIComponent(leadStoryJobId)}`}
											>
												Open notes
											</Link>
										</Button>
									) : null}
									<Button asChild variant="outline" size="sm">
										<Link href="/playground">Open sample flow</Link>
									</Button>
								</div>
							</div>
						</details>
					</section>

					<section className="grid gap-4 xl:grid-cols-[0.95fr_1.35fr]">
						<Card className="folo-surface border-border/70">
							<CardHeader>
								<CardTitle>{selectedWatchlist.name}</CardTitle>
								<CardDescription>
									{copy.matcherLabel}: {trend.summary.matcher_type} ={" "}
									<code>{trend.summary.matcher_value}</code>
								</CardDescription>
							</CardHeader>
							<CardContent className="grid gap-3 text-sm text-muted-foreground sm:grid-cols-3 xl:grid-cols-1">
								<div className="rounded-lg border border-border/60 bg-muted/20 p-3">
									<p className="font-medium text-foreground">
										{copy.recentRunsLabel}
									</p>
									<p className="mt-1 text-2xl font-semibold text-foreground">
										{trend.summary.recent_runs}
									</p>
								</div>
								<div className="rounded-lg border border-border/60 bg-muted/20 p-3">
									<p className="font-medium text-foreground">
										{copy.matchedCardsLabel}
									</p>
									<p className="mt-1 text-2xl font-semibold text-foreground">
										{trend.summary.matched_cards}
									</p>
								</div>
								<div className="rounded-lg border border-border/60 bg-muted/20 p-3">
									<p className="font-medium text-foreground">
										{copy.sourceCountLabel}
									</p>
									<p className="mt-1 text-2xl font-semibold text-foreground">
										{sourceCoverage.length}
									</p>
								</div>
								<div className="flex flex-wrap gap-3 xl:pt-2">
									<Button asChild variant="outline" size="sm">
										<Link
											href={`/briefings?watchlist_id=${encodeURIComponent(selectedWatchlist.id)}`}
										>
											{copy.openBriefingButton}
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
								<CardTitle>{copy.sourceCoverageTitle}</CardTitle>
								<CardDescription>
									{copy.sourceCoverageDescription}
								</CardDescription>
							</CardHeader>
							<CardContent className="grid gap-3 md:grid-cols-2">
								{sourceCoverage.map((item) => (
									<div
										key={item.platform}
										className="rounded-lg border border-border/60 bg-muted/20 p-4"
									>
										<div className="flex items-center justify-between gap-3">
											<p className="font-medium">
												{platformLabel(item.platform)}
											</p>
											<Badge variant="outline">
												{item.run_count} {copy.sourceCoverageRunsLabel}
											</Badge>
										</div>
										<p className="mt-3 text-sm text-muted-foreground">
											{copy.sourceCoverageCardsLabel}: {item.card_count}
										</p>
										<div className="mt-3 h-2 overflow-hidden rounded-full bg-background/80">
											<div
												className="h-full rounded-full bg-primary/75"
												style={{
													width: `${Math.max(
														10,
														Math.min(
															100,
															(item.card_count / maxSourceCards) * 100,
														),
													)}%`,
												}}
											/>
										</div>
										{item.latest_created_at ? (
											<p className="mt-1 text-sm text-muted-foreground">
												{copy.latestSeenLabel}:{" "}
												{formatDateTime(item.latest_created_at)}
											</p>
										) : null}
									</div>
								))}
							</CardContent>
						</Card>
					</section>

					<Card className="folo-surface border-border/70">
						<CardHeader>
							<CardTitle>{copy.mergedStoriesTitle}</CardTitle>
							<CardDescription>{copy.mergedStoriesDescription}</CardDescription>
						</CardHeader>
						<CardContent>
							{mergedStories.length === 0 ? (
								<p className="text-sm text-muted-foreground">
									{copy.mergedStoriesEmpty}
								</p>
							) : (
								<div className="grid gap-4 lg:grid-cols-2">
									{mergedStories.map((story) => (
										<article
											key={story.id}
											className="rounded-xl border border-border/60 bg-muted/20 p-4"
										>
											<div className="flex flex-wrap items-start justify-between gap-3">
												<div className="space-y-2">
													<h2 className="text-lg font-semibold">
														{story.label}
													</h2>
													<div className="flex flex-wrap gap-2">
														{story.platforms.map((platform) => (
															<Badge key={platform} variant="outline">
																{platformLabel(platform)}
															</Badge>
														))}
													</div>
												</div>
												<Badge variant="outline">
													{story.sourceCount} {copy.sourceCountLabel}
												</Badge>
											</div>
											<div className="mt-4 grid gap-3 text-sm text-muted-foreground sm:grid-cols-3">
												<p>
													<span className="font-medium text-foreground">
														{copy.sourceCountLabel}:
													</span>{" "}
													{story.sourceCount}
												</p>
												<p>
													<span className="font-medium text-foreground">
														{copy.runCountLabel}:
													</span>{" "}
													{story.runCount}
												</p>
												<p>
													<span className="font-medium text-foreground">
														{copy.latestSeenLabel}:
													</span>{" "}
													{story.latestCreatedAt
														? formatDateTime(story.latestCreatedAt)
														: copy.noneValue}
												</p>
											</div>
											{story.summary ? (
												<p className="mt-4 text-sm text-muted-foreground">
													{story.summary}
												</p>
											) : (
												<p className="mt-4 text-sm text-muted-foreground">
													{buildStorySummary(story)}
												</p>
											)}
											<div className="mt-4 flex flex-wrap gap-2">
												{story.claimKinds.map((claimKind) => (
													<Badge key={claimKind} variant="outline">
														{humanizeClaimKind(claimKind)}
													</Badge>
												))}
											</div>
											<div className="mt-4 flex flex-wrap gap-3">
												<Button asChild variant="outline" size="sm">
													<Link
														href={`/briefings?watchlist_id=${encodeURIComponent(selectedWatchlist.id)}&story_id=${encodeURIComponent(story.id)}`}
													>
														Open briefing story
													</Link>
												</Button>
												{story.topicKey ? (
													<Button asChild variant="outline" size="sm">
														<Link
															href={buildAskRoute({
																watchlistId: selectedWatchlist.id,
																storyId: story.id,
																topicKey: story.topicKey,
																label: story.label,
															})}
														>
															Ask this story
														</Link>
													</Button>
												) : null}
												{story.latestJobId ? (
													<Button asChild variant="outline" size="sm">
														<Link
															href={`/api/v1/jobs/${encodeURIComponent(story.latestJobId)}/bundle`}
														>
															Open bundle
														</Link>
													</Button>
												) : null}
												{story.latestJobId ? (
													<Button asChild variant="outline" size="sm">
														<Link
															href={`/knowledge?job_id=${encodeURIComponent(story.latestJobId)}`}
														>
															Open knowledge
														</Link>
													</Button>
												) : null}
											</div>
											<div className="mt-4 space-y-3">
												{story.evidence.map((item) => (
													<div
														key={item.jobId}
														className="rounded-lg border border-border/50 bg-background/70 p-3"
													>
														<div className="flex flex-wrap items-center justify-between gap-3">
															<div className="space-y-1">
																<p className="font-medium">{item.title}</p>
																<p className="text-sm text-muted-foreground">
																	{platformLabel(item.platform)} ·{" "}
																	{formatDateTime(item.createdAt)}
																</p>
															</div>
															<div className="flex flex-wrap gap-3">
																<Button
																	asChild
																	variant="link"
																	size="sm"
																	className="h-auto px-0"
																>
																	<Link
																		href={`/jobs?job_id=${encodeURIComponent(item.jobId)}`}
																	>
																		{copy.openJobButton}
																	</Link>
																</Button>
																<Button
																	asChild
																	variant="link"
																	size="sm"
																	className="h-auto px-0"
																>
																	<Link
																		href={`/knowledge?job_id=${encodeURIComponent(item.jobId)}`}
																	>
																		{copy.openKnowledgeButton}
																	</Link>
																</Button>
																{item.sourceUrl ? (
																	<Button
																		asChild
																		variant="link"
																		size="sm"
																		className="h-auto px-0"
																	>
																		<Link
																			href={item.sourceUrl}
																			target="_blank"
																			rel="noreferrer"
																		>
																			{copy.openSourceButton}
																		</Link>
																	</Button>
																) : null}
															</div>
														</div>
														{item.excerpt ? (
															<p className="mt-3 text-sm text-muted-foreground">
																{item.excerpt}
															</p>
														) : null}
													</div>
												))}
											</div>
										</article>
									))}
								</div>
							)}
						</CardContent>
					</Card>

					<Card className="folo-surface border-border/70">
						<CardHeader>
							<CardTitle>{copy.recentEvidenceTitle}</CardTitle>
							<CardDescription>
								{copy.recentEvidenceDescription}
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							{trend.timeline.map((run) => (
								<div
									key={run.job_id}
									className="rounded-lg border border-border/60 bg-muted/20 p-4"
								>
									<div className="flex flex-wrap items-center justify-between gap-3">
										<div className="space-y-1">
											<p className="font-medium">{run.title}</p>
											<p className="text-sm text-muted-foreground">
												{platformLabel(run.platform)} ·{" "}
												{formatDateTime(run.created_at)} ·{" "}
												{copy.matchedCardsLabel}: {run.matched_card_count}
											</p>
										</div>
										<div className="flex flex-wrap gap-3">
											<Button
												asChild
												variant="link"
												size="sm"
												className="h-auto px-0"
											>
												<Link
													href={`/jobs?job_id=${encodeURIComponent(run.job_id)}`}
												>
													{copy.openJobButton}
												</Link>
											</Button>
											<Button
												asChild
												variant="link"
												size="sm"
												className="h-auto px-0"
											>
												<Link
													href={`/knowledge?job_id=${encodeURIComponent(run.job_id)}`}
												>
													{copy.openKnowledgeButton}
												</Link>
											</Button>
											{run.source_url ? (
												<Button
													asChild
													variant="link"
													size="sm"
													className="h-auto px-0"
												>
													<Link
														href={run.source_url}
														target="_blank"
														rel="noreferrer"
													>
														{copy.openSourceButton}
													</Link>
												</Button>
											) : null}
										</div>
									</div>
									<div className="mt-3 grid gap-2 text-sm text-muted-foreground lg:grid-cols-2">
										<p>
											{copy.addedTopicsPrefix}:{" "}
											{run.added_topics.join(", ") || copy.noneValue}
										</p>
										<p>
											{copy.removedTopicsPrefix}:{" "}
											{run.removed_topics.join(", ") || copy.noneValue}
										</p>
										<p>
											{copy.addedClaimKindsPrefix}:{" "}
											{run.added_claim_kinds.join(", ") || copy.noneValue}
										</p>
										<p>
											{copy.removedClaimKindsPrefix}:{" "}
											{run.removed_claim_kinds.join(", ") || copy.noneValue}
										</p>
									</div>
									<div className="mt-3 h-2 overflow-hidden rounded-full bg-background/80">
										<div
											className="h-full rounded-full bg-primary/80"
											style={{
												width: `${Math.max(
													10,
													Math.min(
														100,
														(run.matched_card_count / maxTimelineCards) * 100,
													),
												)}%`,
											}}
										/>
									</div>
								</div>
							))}
						</CardContent>
					</Card>
				</>
			) : null}
		</div>
	);
}
