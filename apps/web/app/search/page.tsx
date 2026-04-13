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
	const routeFacts = askIntent
		? [copy.askTruthPrimary, copy.askTruthSecondary, copy.askTruthNote]
		: [copy.searchTruthPrimary, copy.searchTruthSecondary];
	const contractBullets = askIntent
		? [
				copy.askContractPrimary,
				copy.askContractSecondary,
				copy.askTruthContractLead,
			]
		: [
				copy.searchContractPrimary,
				copy.searchContractSecondary,
				copy.searchHint,
			];
	const emphasisBadges = askIntent
		? [
				copy.groundingModeLabel,
				copy.openJobTraceButton,
				copy.openKnowledgeCardsButton,
			]
		: ["Keyword-first", "Cited jumps", "Operator-auditable"];

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

			<section className="grid gap-4 xl:grid-cols-[1.45fr_0.82fr]">
				<Card className="folo-surface border-border/70">
					<CardHeader>
						<div className="flex flex-wrap gap-2">
							{emphasisBadges.map((label) => (
								<Badge
									key={label}
									variant="outline"
									className="bg-background/70"
								>
									{label}
								</Badge>
							))}
						</div>
						<h2 className="text-xl font-semibold">
							{askIntent ? copy.askFormTitle : copy.searchFormTitle}
						</h2>
						<CardDescription>
							{askIntent ? copy.askFormDescription : copy.searchFormDescription}
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-6">
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

						<div className="grid gap-4 rounded-2xl border border-border/60 bg-background/55 p-4 lg:grid-cols-[1.15fr_0.9fr]">
							<div className="space-y-3">
								<p className="font-semibold text-foreground">
									{askIntent ? copy.askTruthTitle : copy.searchTruthTitle}
								</p>
								<div className="space-y-3 text-sm leading-6 text-muted-foreground">
									{routeFacts.map((fact) => (
										<p key={fact}>{fact}</p>
									))}
								</div>
							</div>
							<div className="space-y-3 border-border/50 lg:border-l lg:pl-4">
								<p className="font-semibold text-foreground">
									{askIntent ? copy.askContractTitle : copy.searchContractTitle}
								</p>
								<ul className="space-y-2 text-sm leading-6 text-muted-foreground">
									{contractBullets.map((bullet) => (
										<li key={bullet} className="flex gap-3">
											<span
												className="mt-2 size-1.5 shrink-0 rounded-full bg-primary/80"
												aria-hidden
											/>
											<span>{bullet}</span>
										</li>
									))}
								</ul>
								<div className="flex flex-wrap gap-3 pt-1">
									<Button asChild variant="outline" size="sm">
										<Link href="/ask">
											{askIntent ? copy.askTruthCta : copy.searchTruthCta}
										</Link>
									</Button>
									<Button asChild variant="outline" size="sm">
										<Link href="/briefings">
											{briefingsCopy.openBriefingButton}
										</Link>
									</Button>
								</div>
							</div>
						</div>
					</CardContent>
				</Card>
			</section>

			<Card className="folo-surface border-border/70">
				<CardHeader>
					<h2 className="text-xl font-semibold">
						{askIntent ? copy.askResultsTitle : copy.searchResultsTitle}
					</h2>
					<CardDescription>
						{queryValue
							? `${askIntent ? copy.askResultsPrefix : copy.searchResultsPrefix} for “${queryValue}”.`
							: askIntent
								? copy.askRunPrompt
								: copy.searchRunPrompt}
					</CardDescription>
				</CardHeader>
				<CardContent className="space-y-4">
					{error ? (
						<p className="text-sm text-muted-foreground">
							{copy.requestFailed}
						</p>
					) : null}
					{!error && queryValue && results.length === 0 ? (
						<p className="text-sm text-muted-foreground">{copy.noResults}</p>
					) : null}
					{results.map((item, index) => (
						<Card
							key={`${item.job_id}-${item.source}-${index}`}
							className="border-border/60"
						>
							<CardContent className="space-y-4 pt-6">
								<div className="flex flex-wrap gap-2">
									<Badge variant="outline">{humanizeSource(item.source)}</Badge>
									<Badge variant="outline">{item.platform || "unknown"}</Badge>
									<Badge variant="outline">score {item.score.toFixed(2)}</Badge>
									{normalizedMode !== "keyword" ? (
										<Badge variant="secondary">{copy.experimentalMode}</Badge>
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
									<Button asChild variant="outline" size="sm">
										<Link
											href={`/jobs?job_id=${encodeURIComponent(item.job_id)}`}
										>
											{copy.openJobTraceButton}
										</Link>
									</Button>
									<Button asChild variant="outline" size="sm">
										<Link
											href={`/knowledge?job_id=${encodeURIComponent(item.job_id)}`}
										>
											{copy.openKnowledgeCardsButton}
										</Link>
									</Button>
									<Button asChild variant="outline" size="sm">
										<Link
											href={`/feed?item=${encodeURIComponent(item.job_id)}`}
										>
											{copy.openFeedEntryButton}
										</Link>
									</Button>
									{item.source_url ? (
										<Button asChild variant="ghost" size="sm">
											<a
												href={item.source_url}
												target="_blank"
												rel="noreferrer"
											>
												{copy.openSourceButton}
											</a>
										</Button>
									) : null}
								</div>
							</CardContent>
						</Card>
					))}
				</CardContent>
			</Card>
		</div>
	);
}
