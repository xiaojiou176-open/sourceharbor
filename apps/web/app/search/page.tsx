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
import type { RetrievalSearchMode } from "@/lib/api/types";
import { getLocaleMessages } from "@/lib/i18n/messages";
import {
	resolveSearchParams,
	type SearchParamsInput,
} from "@/lib/search-params";
import { buildProductMetadata } from "@/lib/seo";

const searchCopy = getLocaleMessages().searchPage;
const briefingsCopy = getLocaleMessages().briefingsPage;

export const metadata: Metadata = buildProductMetadata({
	title: searchCopy.metadataTitle,
	description: searchCopy.metadataDescription,
	route: "search",
});

type SearchPageProps = {
	searchParams?: SearchParamsInput;
};

function humanizeSource(source: string): string {
	return source
		.split(/[_-]+/)
		.filter(Boolean)
		.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
		.join(" ");
}

function describeMatchStrength(score: number, maxScore: number): string {
	if (maxScore <= 0) return "Match";
	const ratio = score / maxScore;
	if (ratio >= 0.85) return "Top match";
	if (ratio >= 0.55) return "Strong match";
	return "Related";
}

export default async function SearchPage({ searchParams }: SearchPageProps) {
	const copy = getLocaleMessages().searchPage;
	const modeOptions = [
		{ value: "keyword", label: copy.modeOptions.keyword },
		{ value: "semantic", label: copy.modeOptions.semantic },
		{ value: "hybrid", label: copy.modeOptions.hybrid },
	];
	const { q, query, mode, top_k, intent, platform } = await resolveSearchParams(
		searchParams,
		["q", "query", "mode", "top_k", "intent", "platform"] as const,
	);
	const queryValue = query.trim() || q.trim();
	const trimmedMode = mode.trim();
	const normalizedMode: RetrievalSearchMode =
		trimmedMode === "semantic" || trimmedMode === "hybrid"
			? trimmedMode
			: "keyword";
	const parsedTopK = Number.parseInt(top_k, 10);
	const safeTopK =
		Number.isFinite(parsedTopK) && parsedTopK > 0
			? Math.min(parsedTopK, 20)
			: 8;
	const askIntent = intent.trim() === "ask";
	const safePlatform = platform.trim().toLowerCase();
	const basePlatformOptions = [
		{ value: "", label: copy.platformOptions.all },
		{ value: "youtube", label: copy.platformOptions.youtube },
		{ value: "bilibili", label: copy.platformOptions.bilibili },
		{ value: "rss", label: copy.platformOptions.rss },
	];
	const platformOptions = safePlatform
		? basePlatformOptions.some((option) => option.value === safePlatform)
			? basePlatformOptions
			: [
					...basePlatformOptions,
					{ value: safePlatform, label: humanizeSource(safePlatform) },
				]
		: basePlatformOptions;

	let payload: Awaited<ReturnType<typeof apiClient.searchRetrieval>> | null =
		null;
	let error = false;
	if (queryValue) {
		try {
			payload = await apiClient.searchRetrieval({
				query: queryValue,
				mode: normalizedMode,
				top_k: safeTopK,
				filters: safePlatform ? { platform: safePlatform } : {},
			});
		} catch {
			error = true;
		}
	}

	const results = payload?.items ?? [];
	const leadResult = results[0] ?? null;
	const maxScore = results.reduce(
		(max, item) => Math.max(max, Number.isFinite(item.score) ? item.score : 0),
		0,
	);
	const remainingResults = leadResult ? results.slice(1) : results;

	return (
		<div className="folo-page-shell folo-unified-shell">
			<div className="folo-page-header">
				<p className="folo-page-kicker">
					{askIntent ? copy.askKicker : copy.searchKicker}
				</p>
				<h1 className="folo-page-title" data-route-heading tabIndex={-1}>
					{askIntent ? copy.askTitle : copy.searchTitle}
				</h1>
				<p className="folo-page-subtitle">
					{askIntent ? copy.askSubtitle : copy.searchSubtitle}
				</p>
			</div>

			{queryValue && leadResult ? (
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<h2 className="text-xl font-semibold">Start with the best hit</h2>
						<CardDescription>
							Read the strongest match first, then adjust the search only if you
							still need it.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4">
						<div className="flex flex-wrap gap-2">
							<Badge variant="outline">
								{humanizeSource(leadResult.source)}
							</Badge>
							<Badge variant="outline">
								{leadResult.platform || "unknown"}
							</Badge>
							<Badge variant="secondary">
								{describeMatchStrength(leadResult.score, maxScore)}
							</Badge>
						</div>
						<div className="space-y-2">
							<h3 className="text-lg font-semibold">
								{leadResult.title?.trim() || `Job ${leadResult.job_id}`}
							</h3>
							<p className="text-sm text-muted-foreground">
								{leadResult.snippet}
							</p>
						</div>
						<div className="flex flex-wrap gap-3">
							<Button asChild variant="hero" size="sm">
								<Link
									href={`/feed?item=${encodeURIComponent(leadResult.job_id)}`}
								>
									{copy.openFeedEntryButton}
								</Link>
							</Button>
							<Button asChild variant="secondary" size="sm">
								<Link
									href={`/jobs?job_id=${encodeURIComponent(leadResult.job_id)}`}
								>
									{copy.openJobTraceButton}
								</Link>
							</Button>
							{leadResult.source_url ? (
								<a
									href={leadResult.source_url}
									target="_blank"
									rel="noreferrer"
									className="inline-flex items-center text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
								>
									{copy.openSourceButton}
								</a>
							) : null}
						</div>
					</CardContent>
				</Card>
			) : null}

			<div className={queryValue ? "flex flex-col gap-6" : "space-y-6"}>
				{queryValue && (error || !leadResult || remainingResults.length > 0) ? (
					<Card className="order-1 folo-surface border-border/70">
						<CardHeader>
							<h2 className="text-xl font-semibold">
								{error && !leadResult
									? "The reading lane is temporarily unavailable"
									: leadResult
										? "Keep reading"
										: askIntent
											? copy.askResultsTitle
											: copy.searchResultsTitle}
							</h2>
							<CardDescription>
								{error && !leadResult
									? "Search could not load the current reading lane. Retry first, then widen into the API or ops view only if it still stays quiet."
									: leadResult
										? "Only the remaining matches stay here so the strongest hit can keep the stage."
										: queryValue
											? `${askIntent ? copy.askResultsPrefix : copy.searchResultsPrefix} for “${queryValue}”.`
											: askIntent
												? copy.askRunPrompt
												: copy.searchRunPrompt}
							</CardDescription>
						</CardHeader>
						<CardContent className="space-y-4">
							{!error && queryValue && results.length === 0 ? (
								<p className="text-sm text-muted-foreground">
									{copy.noResults}
								</p>
							) : null}
							{remainingResults.map((item, index) => (
								<Card
									key={`${item.job_id}-${item.source}-${index}`}
									className="border-border/60"
								>
									<CardContent className="space-y-4 pt-6">
										<div className="flex flex-wrap gap-2">
											<Badge variant="outline">
												{humanizeSource(item.source)}
											</Badge>
											<Badge variant="outline">
												{item.platform || "unknown"}
											</Badge>
											<Badge variant="secondary">
												{describeMatchStrength(item.score, maxScore)}
											</Badge>
											{normalizedMode !== "keyword" ? (
												<Badge variant="secondary">
													{copy.experimentalMode}
												</Badge>
											) : null}
										</div>
										<div className="space-y-2">
											<h3 className="text-lg font-semibold">
												{item.title?.trim() || `Job ${item.job_id}`}
											</h3>
											<p className="text-sm text-muted-foreground">
												{item.snippet}
											</p>
										</div>
										<div className="flex flex-wrap gap-3">
											<Button asChild variant="secondary" size="sm">
												<Link
													href={`/jobs?job_id=${encodeURIComponent(item.job_id)}`}
												>
													{copy.openJobTraceButton}
												</Link>
											</Button>
											<Button asChild variant="outline" size="sm">
												<Link
													href={`/feed?item=${encodeURIComponent(item.job_id)}`}
												>
													{copy.openFeedEntryButton}
												</Link>
											</Button>
											<Link
												href={`/knowledge?job_id=${encodeURIComponent(item.job_id)}`}
												className="inline-flex items-center text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
											>
												{copy.openKnowledgeCardsButton}
											</Link>
											{item.source_url ? (
												<a
													href={item.source_url}
													target="_blank"
													rel="noreferrer"
													className="inline-flex items-center text-sm text-muted-foreground underline underline-offset-4 hover:text-foreground"
												>
													{copy.openSourceButton}
												</a>
											) : null}
										</div>
									</CardContent>
								</Card>
							))}
						</CardContent>
					</Card>
				) : null}

				{queryValue ? (
					<details className="order-2 folo-surface rounded-[1.6rem] border border-border/70 bg-background/95 p-5 shadow-sm">
						<summary className="m-[-0.5rem] cursor-pointer list-none rounded-[1.2rem] p-2 transition-colors hover:bg-muted/20">
							<div className="space-y-2">
								<p className="text-sm font-semibold uppercase tracking-[0.2em] text-muted-foreground">
									Refine later
								</p>
								<p className="text-base font-semibold text-foreground">
									Open the search controls only if the first result is not
									enough
								</p>
							</div>
						</summary>
						<div className="mt-5 space-y-5">
							<form
								method="GET"
								className="grid gap-4 xl:grid-cols-[1.5fr_0.72fr_0.72fr_0.26fr]"
							>
								<input
									type="hidden"
									name="intent"
									value={askIntent ? "ask" : ""}
								/>
								<FormInputField
									name="q"
									label={askIntent ? copy.questionLabel : copy.queryLabel}
									placeholder={
										askIntent ? copy.questionPlaceholder : copy.queryPlaceholder
									}
									defaultValue={queryValue}
									hint={askIntent ? copy.askHint : copy.searchHint}
								/>
								<FormSelectField
									name="mode"
									label={askIntent ? copy.groundingModeLabel : copy.modeLabel}
									defaultValue={normalizedMode}
									options={modeOptions}
								/>
								<FormSelectField
									name="platform"
									label={copy.platformLabel}
									defaultValue={safePlatform}
									options={platformOptions}
								/>
								<FormInputField
									name="top_k"
									label={copy.topKLabel}
									type="number"
									min={1}
									max={20}
									defaultValue={safeTopK}
								/>
								<div className="flex flex-wrap items-end gap-3 xl:col-span-full">
									<Button type="submit" variant="hero" size="sm">
										{askIntent ? copy.askButton : copy.searchButton}
									</Button>
									<Button asChild variant="ghost" size="sm">
										<Link href={askIntent ? "/ask" : "/search"}>
											{copy.clearButton}
										</Link>
									</Button>
								</div>
							</form>
							<p className="text-sm leading-6 text-muted-foreground">
								Need a wider reading path?{" "}
								<Link
									href={askIntent ? "/briefings" : "/ask"}
									className="underline underline-offset-4 hover:text-foreground"
								>
									{askIntent
										? briefingsCopy.openBriefingButton
										: copy.searchTruthCta}
								</Link>
								{askIntent ? null : (
									<>
										{" "}
										or{" "}
										<Link
											href="/briefings"
											className="underline underline-offset-4 hover:text-foreground"
										>
											{briefingsCopy.openBriefingButton}
										</Link>
									</>
								)}
								.
							</p>
						</div>
					</details>
				) : (
					<section>
						<Card className="folo-surface border-border/70">
							<CardHeader>
								<h2 className="text-xl font-semibold">
									{askIntent ? copy.askFormTitle : copy.searchFormTitle}
								</h2>
								<CardDescription>
									{askIntent
										? copy.askFormDescription
										: copy.searchFormDescription}
								</CardDescription>
							</CardHeader>
							<CardContent className="space-y-6">
								<form method="GET" className="space-y-5">
									<input
										type="hidden"
										name="intent"
										value={askIntent ? "ask" : ""}
									/>
									<div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-end">
										<FormInputField
											name="q"
											label={askIntent ? copy.questionLabel : copy.queryLabel}
											placeholder={
												askIntent
													? copy.questionPlaceholder
													: copy.queryPlaceholder
											}
											defaultValue={queryValue}
											hint={askIntent ? copy.askHint : copy.searchHint}
										/>
										<div className="flex flex-wrap items-end gap-3">
											<Button type="submit" variant="hero" size="sm">
												{askIntent ? copy.askButton : copy.searchButton}
											</Button>
											<Button asChild variant="ghost" size="sm">
												<Link href={askIntent ? "/ask" : "/search"}>
													{copy.clearButton}
												</Link>
											</Button>
										</div>
									</div>
									<details className="rounded-2xl border border-border/60 bg-background/55 p-4">
										<summary className="cursor-pointer list-none text-sm font-semibold text-foreground">
											Refine later
										</summary>
										<div className="mt-4 grid gap-4 xl:grid-cols-[0.72fr_0.72fr_0.26fr]">
											<FormSelectField
												name="mode"
												label={
													askIntent ? copy.groundingModeLabel : copy.modeLabel
												}
												defaultValue={normalizedMode}
												options={modeOptions}
											/>
											<FormSelectField
												name="platform"
												label={copy.platformLabel}
												defaultValue={safePlatform}
												options={platformOptions}
											/>
											<FormInputField
												name="top_k"
												label={copy.topKLabel}
												type="number"
												min={1}
												max={20}
												defaultValue={safeTopK}
											/>
										</div>
									</details>
								</form>
								<p className="text-sm leading-6 text-muted-foreground">
									Start with one plain-language question. Open filters only
									after the first reading path feels too wide.
								</p>
								<p className="text-sm leading-6 text-muted-foreground">
									Need a wider reading path?{" "}
									<Link
										href={askIntent ? "/briefings" : "/ask"}
										className="underline underline-offset-4 hover:text-foreground"
									>
										{askIntent
											? briefingsCopy.openBriefingButton
											: copy.searchTruthCta}
									</Link>
									{askIntent ? null : (
										<>
											{" "}
											or{" "}
											<Link
												href="/briefings"
												className="underline underline-offset-4 hover:text-foreground"
											>
												{briefingsCopy.openBriefingButton}
											</Link>
										</>
									)}
									.
								</p>
							</CardContent>
						</Card>
					</section>
				)}
			</div>
		</div>
	);
}
